"""Direct platform extractors; heavy extraction runs in a cancellable child process."""
from __future__ import annotations

import http.cookiejar
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from .core import Media, UserError, check_cancel, public_url

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def engine_command(engine, args):
    if getattr(sys, "frozen", False):
        worker = Path(sys.executable).with_name("MediaDownloaderEngine.exe")
        if os.name == "nt":
            if not worker.is_file():
                raise UserError("Falta el motor de descarga. Extraé nuevamente el ZIP portable completo.")
            return [str(worker), "--engine", engine, *args]
        return [sys.executable, "--engine", engine, *args]
    if engine == "instagram-dash":
        return [sys.executable, str(Path(__file__).resolve().parents[1] / "main.py"), "--engine", engine, *args]
    return [sys.executable, "-m", {"gallery-dl": "gallery_dl", "yt-dlp": "yt_dlp"}[engine], *args]


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=CREATE_NO_WINDOW)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


def run_engine(engine, args, cancel, timeout=180):
    # Files avoid pipe deadlocks on large playlists and don't expose session tokens in logs.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(engine_command(engine, args), stdout=stdout, stderr=stderr,
                                   creationflags=CREATE_NO_WINDOW, start_new_session=os.name != "nt")
        started = time.monotonic()
        try:
            while process.poll() is None:
                check_cancel(cancel)
                if time.monotonic() - started > timeout:
                    raise UserError("La plataforma tardó demasiado. Intentá otra vez o usá una sesión local.")
                cancel.wait(0.1)
            stdout.seek(0)
            raw = stdout.read(32 * 1024 * 1024)
            if process.returncode:
                stderr.seek(0)
                error = stderr.read(16000).decode("utf-8", "replace").lower()
                if any(s in error for s in ("proxyerror", "tunnel connection failed", "proxy connection")):
                    raise UserError("La red o el proxy bloqueó el acceso a la plataforma. Revisá los destinos permitidos o la conexión de esta PC.")
                if any(s in error for s in ("login", "cookies", "401", "403", "429", "challenge", "sign in")):
                    raise UserError("La plataforma bloqueó el acceso o requiere una sesión. Probá más tarde o cargá cookies locales en ‘Sesión local’.")
                raise UserError("El motor no pudo obtener este contenido. Puede estar eliminado, ser privado o requerir actualizar el programa.")
            return raw.decode("utf-8")
        finally:
            if process.poll() is None:
                stop_process(process)
            process.wait()


def gallery_items(raw, source):
    result = []
    expected = 0
    received = 0
    story = urlsplit(source).path.startswith("/stories/")
    for message in json.loads(raw):
        if isinstance(message, list) and len(message) == 2 and message[0] == -1:
            error = (str(message[1].get("error", "")) + " " + str(message[1].get("message", ""))).lower()
            if "proxy" in error or "tunnel" in error:
                raise UserError("La red o el proxy bloqueó el acceso a Instagram. Revisá los destinos permitidos o la conexión de esta PC.")
            if any(term in error for term in ("login", "401", "403", "challenge", "sign in", "authentication", "authorization", "cookies")):
                raise UserError("Instagram pidió iniciar sesión o rechazó la sesión importada. Renová las cookies locales e intentá otra vez.")
            if "429" in error or "rate limit" in error:
                raise UserError("Instagram limitó temporalmente las consultas. Esperá antes de volver a analizar.")
            if story and any(term in error for term in ("notfound", "not found", "404")):
                raise UserError("La historia ya no está disponible o tu cuenta no puede verla. Comprobá el enlace en Instagram con la misma cuenta.")
            raise UserError("Instagram no permitió analizar toda la publicación. Puede requerir una sesión local o una actualización del motor.")
        if isinstance(message, list) and message and message[0] == 2:
            meta = message[-1]
            if isinstance(meta, dict):
                expected = max(expected, int(meta.get("count") or 0))
            continue
        if not isinstance(message, list) or len(message) < 3 or message[0] != 3:
            continue
        url, meta = message[1:3]
        received += 1
        expected = max(expected, int(meta.get("count") or 0))
        # gallery-dl counts the optional music track in post.count, even when
        # audio=false suppresses its URL. Enumerate it (dump-json downloads no
        # media) and include it in validation, but show only photos and videos.
        if meta.get("audio_url"):
            continue
        ext = str(meta.get("extension", Path(urlsplit(url).path).suffix.lstrip(".") or "jpg"))
        video = ext.lower() in {"mp4", "webm", "mov", "mkv", "m4v"}
        # gallery-dl emits every carousel entry in the platform's original order.
        manifest = meta.get("_ytdl_manifest_data", "")
        engine = "instagram-dash" if video and manifest else "gallery-dl"
        if url.startswith("ytdl:") and not manifest:
            raise UserError("Instagram no entregó el manifiesto del video. Actualizá el programa para evitar descargar una calidad incompleta.")
        result.append(Media(len(result) + 1, "video" if video else "foto", url,
                            "mkv" if engine == "instagram-dash" else ext,
                            engine, source, meta.get("display_url", ""),
                            str(meta.get("description", ""))[:200], manifest=manifest))
    if not result:
        if story:
            raise UserError("No hay historias disponibles para ese enlace. Pueden haber vencido, haber sido eliminadas o no ser visibles para tu cuenta.")
        raise UserError("Instagram no entregó archivos. Puede exigir iniciar sesión incluso para publicaciones públicas.")
    if expected and received != expected:
        raise UserError(f"Instagram devolvió el contenido incompleto: {received} de {expected} archivos, incluida su pista musical si existe. Probá más tarde o renová la sesión local.")
    return result


def ytdlp_items(raw, source):
    info = json.loads(raw)
    entries = info.get("entries") if info.get("_type") in {"playlist", "multi_video"} else [info]
    result = []
    for entry in entries or []:
        if not entry:
            continue
        result.append(Media(len(result) + 1, "video", source, "mkv", "yt-dlp", source,
                            entry.get("thumbnail") or "", str(entry.get("title") or "Video")[:200],
                            str(entry.get("id") or "")))
    if not result:
        raise UserError("No se encontraron videos disponibles.")
    return result


def analyze(value, cookies, cancel, progress):
    platform, source = public_url(value)
    progress(0, "Consultando directamente a la plataforma…")
    jar = validate_cookies(cookies) if cookies else None
    if platform == "instagram":
        if urlsplit(source).path.startswith("/stories/"):
            if jar is None or not any(
                cookie.name == "sessionid" and cookie.value
                # Netscape exports use 0 or a blank expiry for session cookies.
                and (cookie.expires in (None, 0) or not cookie.is_expired())
                and cookie.domain.lstrip(".").lower() == "instagram.com" for cookie in jar
            ):
                raise UserError("Para descargar historias, importá una sesión vigente de Instagram desde ‘Sesión local’. Usá una cuenta que pueda ver esa historia.")
            progress(0, "Consultando historias disponibles con tu sesión local…")
        args = ["--ignore-config", "--no-input", "--dump-json", "-o", "extractor.instagram.videos=true",
                "-o", "output.private=true",
                "-o", "extractor.instagram.previews=false", "-o", "extractor.instagram.audio=true",
                "-o", "extractor.instagram.order-files=asc",
                "-o", "extractor.instagram.user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"]
        if cookies:
            args += ["--cookies", cookies]
        # Do not silently replace a failed carousel extraction with a partial video-only result.
        # yt-dlp is used for video delivery, while gallery-dl owns complete IG enumeration.
        return gallery_items(run_engine("gallery-dl", [*args, source], cancel), source)
    args = ["--ignore-config", "--dump-single-json", "--skip-download", "--no-warnings", "--socket-timeout", "25"]
    if cookies:
        args += ["--cookies", cookies]
    return ytdlp_items(run_engine("yt-dlp", [*args, source], cancel), source)


def validate_cookies(path):
    try:
        jar = http.cookiejar.MozillaCookieJar(path)
        jar.load(ignore_discard=True, ignore_expires=True)
    except (OSError, http.cookiejar.LoadError):
        raise UserError("El archivo de sesión debe ser cookies.txt en formato Netscape. No se necesitan contraseñas.") from None
    return jar


def session(cookies=""):
    client = requests.Session()
    client.headers["User-Agent"] = "Mozilla/5.0"
    if cookies:
        client.cookies.update(validate_cookies(cookies))
    return client


def direct_download(url, path, cancel, progress, cookies="", referer=""):
    if urlsplit(url).scheme != "https":
        raise UserError("La plataforma devolvió un enlace de descarga inseguro.")
    try:
        with session(cookies) as client, client.get(url, headers={"Referer": referer},
                stream=True, timeout=(15, 35)) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type.startswith("text/") or "application/json" in content_type:
                raise UserError("La plataforma devolvió una página de acceso en lugar del archivo. Volvé a Analizar o cargá una sesión local.")
            total = int(response.headers.get("Content-Length", 0))
            received = 0
            with path.open("wb") as f:
                for block in response.iter_content(256 * 1024):
                    check_cancel(cancel)
                    f.write(block)
                    received += len(block)
                    progress(min(99, int(received * 100 / total)) if total else 0,
                             f"Descargando {received / 1048576:.1f} MB…")
            if not received or total and received != total:
                raise UserError("La descarga llegó incompleta. Volvé a intentarlo.")
    except requests.RequestException:
        raise UserError("No se pudo descargar. Revisá la conexión; si el enlace venció, volvé a Analizar. Puede requerir sesión local.") from None


def ffmpeg_location():
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).parent)
    return None


def fetch(item, folder, cancel, progress, cookies=""):
    folder.mkdir(parents=True, exist_ok=True)
    if item.engine == "gallery-dl":
        path = folder / item.filename
        direct_download(item.url, path, cancel, progress, cookies, item.source)
        progress(100, "Descarga completa.")
        return path
    # A separate process makes extraction, fragment downloads and muxing cancellable.
    args = ["--ignore-config", "--no-warnings", "--newline", "--socket-timeout", "25",
            "--progress-template", "download:MDPROGRESS:%(progress._percent_str)s",
            "--retries", "3", "--fragment-retries", "3", "--no-part",
            "-f", "bv*+ba/b", "--merge-output-format", "mkv", "--remux-video", "mkv",
            "--write-info-json", "-o", str(folder / "media.%(ext)s")]
    if cookies:
        args += ["--cookies", cookies]
    if ffmpeg_location():
        args += ["--ffmpeg-location", ffmpeg_location()]
    if item.selector:
        args += ["--match-filter", f"id = '{item.selector}'"]
    progress(0, "Descargando la mejor calidad y el audio…")
    # yt-dlp's progress goes to a small file to avoid blocking; parsed while the process runs.
    engine = "yt-dlp"
    command_args = [*args, item.source]
    if item.engine == "instagram-dash":
        request = folder / "dash-request.json"
        request.write_text(json.dumps({"manifest": item.manifest, "folder": str(folder),
                                       "cookies": cookies, "ffmpeg": ffmpeg_location()}), encoding="utf-8")
        engine, command_args = "instagram-dash", [str(request)]
    log = folder / "engine.log"
    with log.open("wb") as output:
        proc = subprocess.Popen(engine_command(engine, command_args), stdout=output,
                                stderr=output, creationflags=CREATE_NO_WINDOW,
                                start_new_session=os.name != "nt")
        started = time.monotonic()
        try:
            while proc.poll() is None:
                check_cancel(cancel)
                if time.monotonic() - started > 3600:
                    raise UserError("La descarga superó una hora. Intentá otra vez.")
                # Do not share the writer's file offset: read through a separate descriptor on disk
                # is not portable for TemporaryFile. Report bytes in output media instead.
                size = sum(p.stat().st_size for p in folder.glob("media.*") if p.is_file())
                with log.open("rb") as log_reader:
                    log_reader.seek(max(0, log.stat().st_size - 4000))
                    matches = re.findall(rb"MDPROGRESS:\s*([\d.]+)%", log_reader.read())
                percent = min(99, int(float(matches[-1]))) if matches else 0
                progress(percent, f"Descargando y combinando sin recompresión: {size / 1048576:.1f} MB…")
                cancel.wait(0.25)
            if proc.returncode:
                raise UserError("No se pudo obtener el video con audio. Volvé a Analizar, cargá una sesión local o actualizá el programa.")
        finally:
            if proc.poll() is None:
                stop_process(proc)
            proc.wait()
    paths = list(folder.glob("media.mkv"))
    if len(paths) != 1 or not paths[0].stat().st_size:
        raise UserError("El motor no generó un video completo.")
    metadata = json.loads((folder / "media.info.json").read_text(encoding="utf-8"))
    # Reject silent video rather than presenting it as a successful TikTok download.
    formats = metadata.get("requested_formats") or [metadata]
    if "tiktok.com" in urlsplit(item.source).netloc and not any(f.get("acodec") and f["acodec"] != "none" for f in formats):
        raise UserError("La plataforma no entregó una pista de audio para este video.")
    progress(100, "Video y audio guardados sin recompresión.")
    return paths[0]


def download_instagram_dash(request_file):
    """Use the actual DASH representation list exposed by Instagram, not an upscaled copy."""
    import xml.etree.ElementTree as ET
    import yt_dlp
    request = json.loads(Path(request_file).read_text(encoding="utf-8"))
    def progress(data):
        total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
        if total:
            print(f"MDPROGRESS:{data.get('downloaded_bytes', 0) * 100 / total:.1f}%", flush=True)
    options = {"format": "bv*+ba/b", "outtmpl": str(Path(request["folder"]) / "media.%(ext)s"),
               "merge_output_format": "mkv", "writeinfojson": True,
               "socket_timeout": 25, "retries": 3, "progress_hooks": [progress],
               "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mkv"}]}
    if request.get("cookies"):
        options["cookiefile"] = request["cookies"]
    if request.get("ffmpeg"):
        options["ffmpeg_location"] = request["ffmpeg"]
    with yt_dlp.YoutubeDL(options) as ydl:
        extractor = ydl.get_info_extractor("Generic")
        formats, subtitles = extractor._parse_mpd_formats_and_subtitles(
            ET.fromstring(request["manifest"]), mpd_id="dash")
        for fmt in formats:
            fmt["http_headers"] = {"User-Agent": "Mozilla/5.0"}
        ydl.process_ie_result({"id": "instagram", "title": "Instagram", "extractor": "instagram",
                               "formats": formats, "subtitles": subtitles}, download=True)
    return 0

