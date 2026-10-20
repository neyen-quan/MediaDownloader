from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer, QSize
from PySide6.QtGui import QPixmap, QDesktopServices, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QListWidget, QListWidgetItem, QSplitter, QFileDialog,
    QProgressBar, QMessageBox, QStackedWidget, QSlider)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from . import __version__
from .core import Settings, UserError, Cancelled, data_dir, save_selection
from . import engines
from .updater import validate_package, locations


class Task(QThread):
    progress = Signal(int, str)
    result = Signal(object)
    error = Signal(str)

    def __init__(self, action, parent):
        super().__init__(parent)
        self.action = action
        self.cancel = threading.Event()

    def run(self):
        try:
            self.result.emit(self.action(self.cancel, self.progress.emit))
        except (UserError, Cancelled) as e:
            self.error.emit(str(e))
        except OSError:
            self.error.emit("No se pudo acceder a un archivo. Revisá los permisos y el espacio libre de la carpeta.")
        except Exception as e:
            # Extractor exceptions may contain signed media URLs or cookies; don't display them.
            self.error.emit(f"No se pudo completar la operación ({type(e).__name__}). Volvé a intentarlo o actualizá el programa.")


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"MediaDownloader · {__version__}")
        self.resize(1080, 740)
        self.settings = Settings.load()
        self.task = None
        self.items = []
        self.cache = tempfile.TemporaryDirectory(prefix="MediaDownloader-preview-")
        self.previews = {}
        self.pending_close = False
        self.pixmap = None
        body = QWidget()
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        title = QLabel("MediaDownloader")
        title.setStyleSheet("font-size: 26px; font-weight: bold; padding: 8px 0;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Instagram y TikTok · conexión directa · archivos originales sin recompresión"))
        row = QHBoxLayout()
        self.url = QLineEdit()
        self.url.setPlaceholderText("Pegá el enlace público de la publicación o del video…")
        self.analyze_button = QPushButton("Analizar")
        self.analyze_button.clicked.connect(self.analyze)
        self.url.returnPressed.connect(self.analyze)
        row.addWidget(self.url, 1); row.addWidget(self.analyze_button)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.folder = QLineEdit(self.settings.destination)
        self.folder.setReadOnly(True)
        self.folder.setPlaceholderText("Elegí dónde guardar tus descargas")
        self.folder_button = QPushButton("Elegir carpeta…")
        self.folder_button.clicked.connect(self.choose_folder)
        self.open_button = QPushButton("Abrir carpeta")
        self.open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder.text())) if self.folder.text() else None)
        row.addWidget(self.folder, 1); row.addWidget(self.folder_button); row.addWidget(self.open_button)
        layout.addLayout(row)
        split = QSplitter()
        left = QWidget(); column = QVBoxLayout(left)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(QLabel("Elementos en orden · marcá los que quieras guardar"))
        self.list = QListWidget()
        self.list.setIconSize(QSize(72, 72))
        self.list.currentRowChanged.connect(self.show_current)
        column.addWidget(self.list)
        row = QHBoxLayout()
        self.select_all = QPushButton("Marcar todos")
        self.select_none = QPushButton("Desmarcar")
        self.select_all.clicked.connect(lambda: self.mark(True))
        self.select_none.clicked.connect(lambda: self.mark(False))
        row.addWidget(self.select_all); row.addWidget(self.select_none)
        column.addLayout(row)
        split.addWidget(left)
        right = QWidget(); column = QVBoxLayout(right)
        self.details = QLabel("Analizá un enlace para ver su contenido.")
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setWordWrap(True)
        column.addWidget(self.details)
        self.stack = QStackedWidget()
        self.image = QLabel("La previsualización aparecerá aquí.")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumSize(300, 240)
        self.image.setStyleSheet("background: #171e29; color: #ddd; border-radius: 8px;")
        self.video = QVideoWidget()
        self.stack.addWidget(self.image); self.stack.addWidget(self.video)
        column.addWidget(self.stack, 1)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.errorOccurred.connect(lambda *_: self.status.setText("No se pudo reproducir este códec. Podés guardar el archivo original sin recompresión."))
        self.preview_button = QPushButton("Cargar previsualización")
        self.preview_button.clicked.connect(self.preview)
        column.addWidget(self.preview_button)
        row = QHBoxLayout()
        self.play_button = QPushButton("▶ / Pausa")
        self.play_button.clicked.connect(self.toggle_play)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.player.positionChanged.connect(self.seek.setValue)
        self.player.durationChanged.connect(lambda duration: self.seek.setRange(0, duration))
        row.addWidget(self.play_button); row.addWidget(self.seek, 1)
        column.addLayout(row)
        split.addWidget(right); split.setSizes([380, 640])
        layout.addWidget(split, 1)
        row = QHBoxLayout()
        self.download_one = QPushButton("Guardar elemento visible")
        self.download_selected = QPushButton("Guardar seleccionados")
        self.download_all = QPushButton("Guardar todos")
        self.download_zip = QPushButton("Seleccionados como ZIP")
        self.download_one.clicked.connect(lambda: self.download("one"))
        self.download_selected.clicked.connect(lambda: self.download("selected"))
        self.download_all.clicked.connect(lambda: self.download("all"))
        self.download_zip.clicked.connect(lambda: self.download("zip"))
        for button in [self.download_one, self.download_selected, self.download_all, self.download_zip]:
            row.addWidget(button)
        layout.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)
        self.status = QLabel("Listo. Solo descargá contenido que tengas derecho a guardar.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.session_button = QPushButton("Sesión local…")
        self.session_button.clicked.connect(self.configure_session)
        self.update_button = QPushButton("Actualizar programa…")
        self.update_button.clicked.connect(self.update_program)
        self.restore_button = QPushButton("Recuperar versión anterior")
        self.restore_button.clicked.connect(lambda: self.launch_update(None, True))
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        row.addWidget(self.session_button); row.addWidget(self.update_button); row.addWidget(self.restore_button)
        row.addStretch(); row.addWidget(self.cancel_button)
        layout.addLayout(row)
        self.controls = [self.url, self.analyze_button, self.folder_button, self.session_button,
                         self.update_button, self.restore_button, self.select_all, self.select_none,
                         self.preview_button, self.download_one, self.download_selected,
                         self.download_all, self.download_zip, self.list]
        self.refresh_controls(False)

    def refresh_controls(self, busy):
        for control in self.controls:
            control.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        for button in [self.download_one, self.download_selected, self.download_all,
                       self.download_zip, self.preview_button, self.select_all, self.select_none]:
            button.setEnabled(not busy and bool(self.items))
        self.restore_button.setEnabled(not busy and getattr(sys, "frozen", False)
                                       and locations(Path(sys.executable).parent)[0].is_dir())

    def start(self, action, done):
        if self.task:
            return
        self.refresh_controls(True)
        self.progress.setValue(0)
        self.task = Task(action, self)
        self.task.progress.connect(self.report)
        self.task.result.connect(done)
        self.task.error.connect(self.failed)
        self.task.finished.connect(self.task_finished)
        self.task.start()

    def report(self, value, message):
        self.progress.setValue(value)
        self.status.setText(message)

    def failed(self, message):
        self.status.setText(message)
        if not self.pending_close:
            QMessageBox.warning(self, "MediaDownloader", message)

    def task_finished(self):
        old, self.task = self.task, None
        old.deleteLater()
        self.refresh_controls(False)
        if self.pending_close:
            self.close()

    def cancel(self):
        if self.task:
            self.task.cancel.set()
            self.status.setText("Cancelando… Las descargas ya guardadas se conservan.")
            self.cancel_button.setEnabled(False)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Carpeta de destino", self.folder.text())
        if folder:
            self.settings.destination = folder
            self.folder.setText(folder)
            try:
                self.settings.save()
            except OSError:
                self.failed("No se pudo recordar la carpeta de destino.")

    def analyze(self):
        if self.task:
            return
        value, cookies = self.url.text(), self.settings.cookies
        self.start(lambda cancel, progress: engines.analyze(value, cookies, cancel, progress), self.analyzed)

    def analyzed(self, items):
        self.player.stop(); self.player.setSource(QUrl())
        self.items = items
        self.previews = {}
        self.list.clear()
        for item in items:
            row = QListWidgetItem(f"{item.index:03d} · {'Video' if item.kind == 'video' else 'Foto'}")
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked)
            self.list.addItem(row)
        self.list.setCurrentRow(0)
        self.report(100, f"{len(items)} elemento(s) encontrados. Elegí uno para previsualizarlo.")
        # Run preview after extraction's QThread has finished and released the busy state.
        QTimer.singleShot(100, self.preview)

    def mark(self, selected):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked)

    def show_current(self, index):
        self.player.stop(); self.player.setSource(QUrl())
        self.stack.setCurrentIndex(0)
        self.pixmap = None
        if not 0 <= index < len(self.items):
            return
        item = self.items[index]
        self.details.setText(f"Elemento {item.index} de {len(self.items)} · {item.kind}\n{item.title[:150]}")
        path = self.previews.get(item.index)
        if path and path.exists():
            if item.kind == "video":
                self.stack.setCurrentIndex(1)
                self.player.setSource(QUrl.fromLocalFile(str(path)))
            else:
                self.pixmap = QPixmap(str(path))
                self.scale_image()
        else:
            self.image.setPixmap(QPixmap())
            self.image.setText("Tocá ‘Cargar previsualización’.\nLos videos se cargan con audio y pueden tardar.")

    def scale_image(self):
        if self.pixmap and not self.pixmap.isNull():
            self.image.setPixmap(self.pixmap.scaled(self.image.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "pixmap"):
            self.scale_image()

    def preview(self):
        index = self.list.currentRow()
        if self.task or not 0 <= index < len(self.items):
            return
        item = self.items[index]
        if item.index in self.previews:
            self.show_current(index)
            return
        cookies = self.settings.cookies
        folder = Path(self.cache.name) / str(len(list(Path(self.cache.name).iterdir())))
        def done(path):
            self.previews[item.index] = path
            if item.kind != "video":
                self.list.item(index).setIcon(QIcon(str(path)))
            self.show_current(index)
            if item.kind != "video" and (not self.pixmap or self.pixmap.isNull()):
                self.image.setText("Este formato no se puede previsualizar en esta PC.\nPodés guardar el archivo original.")
                self.report(100, "Archivo recibido; formato de imagen no compatible con la previsualización de esta PC.")
            else:
                self.report(100, "Previsualización lista. El original se guarda sin recomprimir.")
        self.start(lambda cancel, progress: engines.fetch(item, folder, cancel, progress, cookies), done)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def download(self, mode):
        if self.task or not self.items:
            return
        if not self.folder.text():
            self.choose_folder()
        if not self.folder.text():
            return
        if mode == "all":
            items = self.items[:]
        elif mode == "one":
            index = self.list.currentRow()
            items = [self.items[index]] if index >= 0 else []
        else:
            items = [item for i, item in enumerate(self.items)
                     if self.list.item(i).checkState() == Qt.CheckState.Checked]
        cookies = self.settings.cookies
        def fetch(item, folder, cancel, progress):
            cached = self.previews.get(item.index)
            if cached and cached.exists():
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / item.filename
                shutil.copy2(cached, path)
                return path
            return engines.fetch(item, folder, cancel, progress, cookies)
        folder = self.folder.text()
        self.start(lambda cancel, progress: save_selection(items, folder, mode == "zip", fetch, cancel, progress),
                   lambda files: self.report(100, f"Guardado en {folder}. {len(files)} archivo(s)."))

    def configure_session(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Sesión local opcional")
        dialog.setText("Instagram y TikTok pueden exigir sesión incluso para contenido público.\n\n"
                       "Podés importar un cookies.txt de tu navegador en formato Netscape. Se guarda solo en esta PC, "
                       "en tu perfil de usuario, y se envía únicamente a sus dominios correspondientes. "
                       "El archivo permite usar tu sesión: no lo compartas ni lo incluyas en ZIPs.\n\n"
                       "No evita bloqueos por IP, CAPTCHA, permisos ni vencimiento. No se solicitan contraseñas.")
        load = dialog.addButton("Importar cookies.txt…", QMessageBox.ButtonRole.AcceptRole)
        remove = dialog.addButton("Quitar sesión", QMessageBox.ButtonRole.DestructiveRole)
        dialog.addButton("Cerrar", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        path = data_dir() / "cookies.txt"
        if dialog.clickedButton() == load:
            chosen, _ = QFileDialog.getOpenFileName(self, "Importar sesión local", "", "Cookies (*.txt)")
            if not chosen:
                return
            try:
                engines.validate_cookies(chosen)
                if Path(chosen).resolve() != path.resolve():
                    shutil.copyfile(chosen, path)
                path.chmod(0o600)
                self.settings.cookies = str(path)
                self.settings.save()
                self.status.setText("Sesión local configurada. Volvé a Analizar.")
            except (OSError, UserError) as e:
                self.failed(str(e))
        elif dialog.clickedButton() == remove:
            try:
                path.unlink(missing_ok=True)
                self.settings.cookies = ""
                self.settings.save()
                self.status.setText("Sesión local eliminada.")
            except OSError:
                self.failed("No se pudo eliminar la sesión local.")

    def update_program(self):
        if not getattr(sys, "frozen", False):
            self.failed("Las actualizaciones se aplican al portable de Windows, no a una ejecución del código fuente.")
            return
        chosen, _ = QFileDialog.getOpenFileName(self, "Elegir actualización de MediaDownloader", "", "Actualización (*.zip)")
        if not chosen:
            return
        def validate(cancel, progress):
            progress(0, "Verificando paquete de actualización…")
            manifest = validate_package(chosen)
            return manifest
        def done(manifest):
            answer = QMessageBox.question(self, "Actualizar programa",
                f"Paquete MediaDownloader {manifest['version']} verificado.\n"
                "Instalá únicamente ZIPs de una fuente de confianza.\n"
                "Se cerrará el programa, se guardará una copia anterior y se reiniciará. ¿Continuar?")
            if answer == QMessageBox.StandardButton.Yes:
                QTimer.singleShot(100, lambda: self.launch_update(chosen))
        self.start(validate, done)

    def launch_update(self, archive, restore=False):
        if self.task:
            self.failed("Esperá a que finalice la operación actual.")
            return
        root = Path(sys.executable).parent
        helper = root / "MediaDownloaderUpdater.exe"
        if not helper.exists():
            self.failed("Falta MediaDownloaderUpdater.exe. Extraé nuevamente el ZIP portable completo.")
            return
        if restore and QMessageBox.question(self, "Recuperar versión anterior",
                 "Se reiniciará el programa con la versión anterior. Tus descargas y configuración se conservan. ¿Continuar?") != QMessageBox.StandardButton.Yes:
            return
        try:
            temp = Path(tempfile.mkdtemp(prefix="MediaDownloader-update-"))
            shutil.copy2(helper, temp / helper.name)
            args = [str(temp / helper.name), "--root", str(root), "--parent", str(os.getpid())]
            if restore:
                args += ["--restore"]
            else:
                shutil.copy2(archive, temp / "package.zip")
                args += ["--zip", str(temp / "package.zip")]
            subprocess.Popen(args, cwd=temp)
            self.close()
        except OSError:
            self.failed("No se pudo iniciar el actualizador. Usá una carpeta con permisos de escritura y espacio libre.")

    def closeEvent(self, event):
        if self.task:
            self.pending_close = True
            self.cancel()
            event.ignore()
            return
        self.player.stop(); self.player.setSource(QUrl())
        try:
            self.cache.cleanup()
        except OSError:
            pass
        event.accept()


def main(smoke=False):
    app = QApplication(sys.argv[:1])
    app.setApplicationName("MediaDownloader")
    app.setOrganizationName("MediaDownloader")
    window = Window()
    window.show()
    if smoke:
        # Real Qt window, multimedia objects and extractor entrypoints must initialize.
        import gallery_dl, yt_dlp
        if not gallery_dl or not yt_dlp or not window.isVisible():
            return 1
        QTimer.singleShot(1200, app.quit)
    return app.exec()
