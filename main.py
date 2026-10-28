"""Frozen executable also dispatches isolated engine child processes."""
import sys


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--engine":
        engine = sys.argv[2]
        sys.argv = [engine, *sys.argv[3:]]
        if engine == "gallery-dl":
            import gallery_dl
            gallery_dl.main()
        elif engine == "yt-dlp":
            import yt_dlp
            yt_dlp.main()
        elif engine == "instagram-dash":
            from mediadownloader.engines import download_instagram_dash
            return download_instagram_dash(sys.argv[1])
        else:
            return 2
        return 0
    from mediadownloader.gui import main as gui_main
    return gui_main("--smoke-test" in sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())

