# One shared bundle, two entry points: a windowed UI and a hidden console worker.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
datas, binaries, hiddenimports = [], [], []
for package in ('gallery_dl', 'yt_dlp'):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports,
             excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtPdf'],
             noarchive=False)
pyz = PYZ(a.pure)
common = dict(exclude_binaries=True, debug=False, strip=False, upx=False,
              icon=str(root / 'build' / 'branding' / 'MediaDownloader.ico'))
gui = EXE(pyz, a.scripts, [], name='MediaDownloader', console=False, **common)
worker = EXE(pyz, a.scripts, [], name='MediaDownloaderEngine', console=True, **common)
coll = COLLECT(gui, worker, a.binaries, a.datas, strip=False, upx=False, name='MediaDownloader')
