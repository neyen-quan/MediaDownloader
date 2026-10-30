"""Local state and download primitives. No Qt dependency."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

APP_ID = "MediaDownloader"


class UserError(Exception):
    pass


class Cancelled(UserError):
    def __init__(self):
        super().__init__("Operación cancelada.")


def check_cancel(cancel):
    if cancel.is_set():
        raise Cancelled()


def public_url(value: str) -> tuple[str, str]:
    try:
        u = urlsplit(value.strip())
        host = (u.hostname or "").lower()
        if u.scheme != "https" or u.username or u.password or u.port not in (None, 443):
            raise ValueError()
    except ValueError:
        raise UserError("Pegá un enlace HTTPS público de Instagram o TikTok.") from None
    path = u.path
    if host in {"instagram.com", "www.instagram.com", "m.instagram.com"}:
        post = re.fullmatch(r"/(?:[A-Za-z0-9_.]{1,30}/)?(p|reel|reels|tv)/([A-Za-z0-9_-]+)/?", path)
        if path.startswith('/stories/'):
            post = None  # /stories/p/123 is a story, never the post /p/123.
        story = re.fullmatch(r"/stories/([A-Za-z0-9_.]{1,30})(?:/[0-9]+)?/?", u.path)
        highlight = re.fullmatch(r"/stories/highlights/[0-9]+/?", u.path)
        if not post and not highlight and not (story and story[1].lower() not in {"me", "highlights"}):
            raise UserError("Usá el enlace de una publicación, reel, carrusel o historia de Instagram.")
        # Account-prefixed share URLs identify the same post by shortcode.
        # Remove that prefix and img_index so the engine enumerates the full set.
        if post:
            kind = 'reel' if post[1] == 'reels' else post[1]
            path = f'/{kind}/{post[2]}/'
        if post or story or highlight:
            host = "www.instagram.com"
        platform = "instagram"
    elif host in {"www.tiktok.com", "tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}:
        if not u.path.strip("/"):
            raise UserError("El enlace de TikTok debe apuntar a un video.")
        platform = "tiktok"
    else:
        raise UserError("Solo se admiten enlaces públicos de Instagram y TikTok.")
    # Tracking query parameters are not needed by extractors (including share links).
    return platform, urlunsplit(("https", host, path, "", ""))


def data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    path = base / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Settings:
    destination: str = ""
    cookies: str = ""
    update_channel: str = "https://github.com/neyen-quan/MediaDownloader/releases/latest/download/latest.json"

    @classmethod
    def load(cls, path=None):
        path = path or data_dir() / "settings.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in raw.items() if k in {"destination", "cookies", "update_channel"} and isinstance(v, str)})
        except (OSError, ValueError, TypeError, AttributeError):
            return cls()

    def save(self, path=None):
        path = path or data_dir() / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="settings-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, ensure_ascii=False)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)


@dataclass
class Media:
    index: int
    kind: str
    url: str
    ext: str
    engine: str
    source: str
    thumbnail: str = ""
    title: str = ""
    selector: str = ""
    manifest: str = ""

    @property
    def filename(self):
        ext = self.ext.lower().lstrip(".")
        if not re.fullmatch(r"[a-z0-9]{1,8}", ext):
            ext = "mp4" if self.kind == "video" else "jpg"
        return f"{self.index:03d}_{self.kind}.{ext}"


def unique_path(folder: Path, name: str):
    target = folder / name
    stem, suffix = target.stem, target.suffix
    i = 1
    while target.exists():
        target = folder / f"{stem} ({i}){suffix}"
        i += 1
    return target


def publish_file(source: Path, folder: Path, name: str):
    """Reserve the destination exclusively, so existing downloads are never replaced."""
    folder.mkdir(parents=True, exist_ok=True)
    while True:
        target = unique_path(folder, name)
        try:
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            break
        except FileExistsError:
            continue
    try:
        os.replace(source, target)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


def save_selection(items, folder, as_zip, fetch, cancel, progress):
    """fetch(item, working_directory, cancel, progress) -> complete local file."""
    items = sorted(items, key=lambda m: m.index)
    if not items:
        raise UserError("Seleccioná al menos un elemento.")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    completed = []
    # Same filesystem for atomic final moves.
    with tempfile.TemporaryDirectory(prefix=".MediaDownloader-", dir=folder) as temp:
        temp = Path(temp)
        paths = []
        for position, item in enumerate(items):
            check_cancel(cancel)
            def report(percent, message):
                progress(int((position + percent / 100) * 100 / len(items)), message)
            path = fetch(item, temp / str(item.index), cancel, report)
            paths.append((item, path))
            if not as_zip:
                check_cancel(cancel)
                completed.append(publish_file(path, folder, item.filename))
        if as_zip:
            archive = temp / "selected.zip"
            # Media is already compressed. ZIP_STORED avoids wasted recompression.
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as z:
                for item, path in paths:
                    check_cancel(cancel)
                    z.write(path, item.filename)
            check_cancel(cancel)
            completed.append(publish_file(archive, folder, "MediaDownloader.zip"))
    progress(100, f"Guardados {len(items)} elemento(s).")
    return completed

