## Resultados de las pruebas

### results.xml

51 pruebas; 1 fallos; 0 omitidas.


**test_dash_best_video_and_audio_are_muxed_without_reencoding**

<pre>tmp_path = WindowsPath(&#x27;C:/Users/runneradmin/AppData/Local/Temp/pytest-of-runneradmin/pytest-0/test_dash_best_video_and_audio0&#x27;)
monkeypatch = &lt;_pytest.monkeypatch.MonkeyPatch object at 0x0000028C87F2DCD0&gt;

    def test_dash_best_video_and_audio_are_muxed_without_reencoding(tmp_path, monkeypatch):
        executable = os.environ.get(&quot;MEDIADOWNLOADER_TEST_EXE&quot;)
        if executable:
            monkeypatch.setattr(&quot;mediadownloader.engines.engine_command&quot;,
                                lambda engine, args: [executable, &quot;--engine&quot;, engine, *args])
        ffmpeg, ffprobe = shutil.which(&quot;ffmpeg&quot;), shutil.which(&quot;ffprobe&quot;)
        if not ffmpeg or not ffprobe:
            pytest.skip(&quot;FFmpeg no está disponible; la compilación Windows debe ejecutar esta prueba tras instalarlo&quot;)
        served = tmp_path / &quot;served&quot;; served.mkdir()
        subprocess.run([ffmpeg, &quot;-hide_banner&quot;, &quot;-loglevel&quot;, &quot;error&quot;, &quot;-f&quot;, &quot;lavfi&quot;, &quot;-i&quot;,
            &quot;color=c=blue:s=160x90:r=10&quot;, &quot;-f&quot;, &quot;lavfi&quot;, &quot;-i&quot;, &quot;sine=frequency=440:sample_rate=44100&quot;,
            &quot;-t&quot;, &quot;1&quot;, &quot;-map&quot;, &quot;0:v&quot;, &quot;-map&quot;, &quot;1:a&quot;, &quot;-c:v&quot;, &quot;libx264&quot;, &quot;-c:a&quot;, &quot;aac&quot;,
            # Windows FFmpeg resolves fragment templates from cwd, even with an absolute MPD path.
            &quot;-f&quot;, &quot;dash&quot;, &quot;manifest.mpd&quot;], cwd=served, check=True, timeout=30)
        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_GET(self):
                requests_seen.append(self.path)
                super().do_GET()
        requests_seen = []
        server = http.server.ThreadingHTTPServer((&quot;127.0.0.1&quot;, 0), functools.partial(Handler, directory=str(served)))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        monkeypatch.setenv(&quot;NO_PROXY&quot;, &quot;127.0.0.1&quot;)
        try:
            # Instagram&#x27;s inline MPD carries absolute media locations; make the fixture equivalent.
            root = ET.fromstring((served / &quot;manifest.mpd&quot;).read_text())
            ns = &quot;{urn:mpeg:dash:schema:mpd:2011}&quot;
            base = ET.Element(ns + &quot;BaseURL&quot;); base.text = f&quot;http://127.0.0.1:{server.server_port}/&quot;
            root.insert(0, base)
            item = Media(1, &quot;video&quot;, &quot;ytdl:fixture.mp4&quot;, &quot;mkv&quot;, &quot;instagram-dash&quot;,
                         &quot;https://instagram.com/reel/test/&quot;, manifest=ET.tostring(root, encoding=&quot;unicode&quot;))
            try:
                path = fetch(item, tmp_path / &quot;result&quot;, threading.Event(), lambda *_: None)
            except Exception as error:
                error.add_note(&quot;HTTP requests: &quot; + repr(requests_seen))
                error.add_note(&quot;Served files: &quot; + repr([p.name for p in served.iterdir()]))
                log = tmp_path / &quot;result&quot; / &quot;engine.log&quot;
                if log.exists():
                    error.add_note(log.read_text(encoding=&quot;utf-8&quot;, errors=&quot;replace&quot;))
                raise
            probe = subprocess.run([ffprobe, &quot;-v&quot;, &quot;error&quot;, &quot;-show_streams&quot;, &quot;-of&quot;, &quot;json&quot;, str(path)],
                                    capture_output=True, text=True, check=True, timeout=20)
            streams = json.loads(probe.stdout)[&quot;streams&quot;]
            assert {s[&quot;codec_type&quot;] for s in streams} == {&quot;video&quot;, &quot;audio&quot;}
            assert {s[&quot;codec_name&quot;] for s in streams} == {&quot;h264&quot;, &quot;aac&quot;}
            assert next(s for s in streams if s[&quot;codec_type&quot;] == &quot;video&quot;)[&quot;width&quot;] == 160
            # Compare compressed elementary streams by FFmpeg stream hash (no decoder involved).
            def stream_hash(path, selector):
                result = subprocess.run([ffmpeg, &quot;-v&quot;, &quot;error&quot;, &quot;-i&quot;, str(path), &quot;-map&quot;, selector,
                    &quot;-c&quot;, &quot;copy&quot;, &quot;-f&quot;, &quot;streamhash&quot;, &quot;-hash&quot;, &quot;sha256&quot;, &quot;-&quot;],
                    check=True, capture_output=True, text=True, timeout=20)
                return result.stdout.strip().split(&quot;=&quot;)[-1]
&gt;           assert stream_hash(served / &quot;manifest.mpd&quot;, &quot;0:v:0&quot;) == stream_hash(path, &quot;0:v:0&quot;)
E           AssertionError: assert &#x27;d1f81b9cda99...95b8f79cdae4f&#x27; == &#x27;906320b8cc42...9771e0961beec&#x27;
E             
E             - 906320b8cc4288e7c27f845ae178bb6e8859f3d5926858333179771e0961beec
E             + d1f81b9cda999af310174e0083392c0a7689027cfc67c53107b95b8f79cdae4f

tests\test_media_pipeline.py:82: AssertionError</pre>


### Motor DASH de la prueba local

<pre>[info] instagram: Downloading 1 format(s): dash-0+dash-1
[info] Writing video metadata as JSON to: C:\Users\runneradmin\AppData\Local\Temp\pytest-of-runneradmin\pytest-0\test_dash_best_video_and_audio0\result\media.info.json
[dashsegments] Total fragments: 2
[download] Destination: C:\Users\runneradmin\AppData\Local\Temp\pytest-of-runneradmin\pytest-0\test_dash_best_video_and_audio0\result\media.fdash-0.mp4

[download]  50.0% of ~   1.59KiB at    1.39KiB/s ETA Unknown (frag 0/2)MDPROGRESS:50.0%

[download]  25.0% of ~   3.18KiB at    1.39KiB/s ETA Unknown (frag 1/2)MDPROGRESS:25.0%

[download]  93.4% of ~   1.92KiB at    1.39KiB/s ETA Unknown (frag 1/2)MDPROGRESS:93.4%

[download]  65.8% of ~   2.92KiB at    1.39KiB/s ETA Unknown (frag 1/2)MDPROGRESS:65.8%

[download]  63.0% of ~   3.05KiB at    1.39KiB/s ETA Unknown (frag 2/2)MDPROGRESS:63.0%

[download] 100% of    1.92KiB in 00:00:00 at 10.25KiB/s                MDPROGRESS:100.0%

[dashsegments] Total fragments: 2
[download] Destination: C:\Users\runneradmin\AppData\Local\Temp\pytest-of-runneradmin\pytest-0\test_dash_best_video_and_audio0\result\media.fdash-1.m4a

[download]  50.0% of ~   1.49KiB at      0.00B/s ETA Unknown (frag 0/2)MDPROGRESS:50.0%

[download]  25.0% of ~   2.98KiB at      0.00B/s ETA Unknown (frag 1/2)MDPROGRESS:25.0%

[download]  17.4% of ~  10.06KiB at      0.00B/s ETA Unknown (frag 1/2)MDPROGRESS:17.4%

[download]  33.9% of ~  11.06KiB at      0.00B/s ETA Unknown (frag 1/2)MDPROGRESS:33.9%

[download]  59.3% of ~  13.06KiB at      0.00B/s ETA Unknown (frag 1/2)MDPROGRESS:59.3%

[download]  59.0% of ~  17.06KiB at      0.00B/s ETA Unknown (frag 1/2)MDPROGRESS:59.0%

[download]  51.9% of ~  19.38KiB at      0.00B/s ETA Unknown (frag 2/2)MDPROGRESS:51.9%

[download] 100% of   10.06KiB in 00:00:00 at 322.06KiB/s               MDPROGRESS:100.0%

[Merger] Merging formats into &quot;C:\Users\runneradmin\AppData\Local\Temp\pytest-of-runneradmin\pytest-0\test_dash_best_video_and_audio0\result\media.mkv&quot;
Deleting original file C:\Users\runneradmin\AppData\Local\Temp\pytest-of-runneradmin\pytest-0\test_dash_best_video_and_audio0\result\media.fdash-0.mp4 (pass -k to keep)
Deleting original file C:\Users\runneradmin\AppData\Local\Temp\pytest-of-runneradmin\pytest-0\test_dash_best_video_and_audio0\result\media.fdash-1.m4a (pass -k to keep)
[VideoRemuxer] Not remuxing media file &quot;C:\Users\runneradmin\AppData\Local\Temp\pytest-of-runneradmin\pytest-0\test_dash_best_video_and_audio0\result\media.mkv&quot;; already is in target format mkv
</pre>
