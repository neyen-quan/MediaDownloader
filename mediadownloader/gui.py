from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer, QSize
from PySide6.QtGui import QPixmap, QDesktopServices, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QListWidget, QListWidgetItem, QSplitter, QFileDialog,
    QProgressBar, QMessageBox, QStackedWidget, QSlider, QScrollArea, QGridLayout, QSizePolicy)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from . import __version__
from .core import Settings, UserError, Cancelled, data_dir, save_selection
from .appearance import STYLE, app_icon, checkbox_image
from .image_preview import ImagePreview, PortraitFrame
from . import windows_shell
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
        self.resize(1280, 900)
        self.setMinimumSize(980, 760)
        self.setStyleSheet(STYLE)
        self.setWindowIcon(app_icon())
        self.settings = Settings.load()
        self.task = None
        self.items = []
        self.cache = tempfile.TemporaryDirectory(prefix="MediaDownloader-preview-")
        self.previews = {}
        self.thumbnails = {}
        self.preview_task = None
        self.preview_generation = 0
        self.preview_failures = set()
        self.pending_close = False
        self.shell_hwnd = None
        self.pixmap = None

        def label(text, name="muted"):
            widget = QLabel(text)
            widget.setObjectName(name)
            return widget

        def button(text, action, name="", tip=""):
            widget = QPushButton(text)
            widget.setObjectName(name)
            widget.setCursor(Qt.CursorShape.PointingHandCursor)
            widget.clicked.connect(action)
            if tip:
                widget.setToolTip(tip)
            return widget

        def card():
            widget = QWidget()
            widget.setObjectName("card")
            box = QVBoxLayout(widget)
            box.setContentsMargins(14, 12, 14, 12)
            box.setSpacing(8)
            return widget, box

        body = QWidget()
        body.setObjectName("appBody")
        self.setCentralWidget(body)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setObjectName("header")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(18, 8, 18, 8)
        header_row.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(self.windowIcon().pixmap(28, 28))
        logo.setFixedSize(28, 28)
        header_row.addWidget(logo)
        brand_column = QVBoxLayout()
        brand_column.setSpacing(3)
        brand_row = QHBoxLayout()
        brand_row.addWidget(label("MediaDownloader", "brand"))
        brand_row.addWidget(label(__version__, "version"))
        brand_row.addStretch()
        brand_column.addLayout(brand_row)
        header_row.addLayout(brand_column)
        header_row.addStretch()
        header_row.addWidget(label("●  Conexión directa", "badge"))
        self.update_button = button("Actualizar programa ↑", self.update_program, "quiet")
        header_row.addWidget(self.update_button)
        outer.addWidget(header)

        content = QWidget()
        content.setMinimumHeight(650)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 10, 18, 8)
        layout.setSpacing(10)

        source, source_box = card()
        source_box.setContentsMargins(12, 8, 12, 8)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(label("Enlace"))
        self.url = QLineEdit()
        self.url.setPlaceholderText("Pegá un enlace de Instagram o TikTok…")
        self.url.setMinimumWidth(130)
        self.url.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.url.setClearButtonEnabled(True)
        self.analyze_button = button("Analizar enlace →", self.analyze, "primary")
        self.analyze_button.setMinimumWidth(125)
        self.url.returnPressed.connect(self.analyze)
        row.addWidget(self.url, 1)
        row.addWidget(self.analyze_button)
        row.addSpacing(10)
        row.addWidget(label("Guardar en"))
        self.folder = QLineEdit(self.settings.destination)
        self.folder.setReadOnly(True)
        self.folder.setMinimumWidth(130)
        self.folder.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.folder.setPlaceholderText("Elegí una carpeta para tus descargas")
        self.folder_button = button("Carpeta…", self.choose_folder, "quiet")
        self.open_button = button("Abrir ↗", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder.text())) if self.folder.text() else None, "quiet")
        row.addWidget(self.folder, 1)
        row.addWidget(self.folder_button)
        row.addWidget(self.open_button)
        source_box.addLayout(row)
        layout.addWidget(source)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setMinimumHeight(420)
        self.content_split = split
        left, column = card()
        left.setMinimumWidth(275)
        left.setMaximumWidth(380)
        left_column = column
        row = QHBoxLayout()
        row.addWidget(label("02 / CONTENIDO", "eyebrow"))
        row.addStretch()
        self.count_label = label("0 elementos", "badge")
        row.addWidget(self.count_label)
        column.addLayout(row)
        selection_title = label("Elegí qué guardar", "sectionTitle")
        selection_title.setStyleSheet("font-size: 17px;")
        selection_title.setToolTip("El orden original se mantiene en tus archivos.")
        column.addWidget(selection_title)
        self.list = QListWidget()
        self.list.setIconSize(QSize(32, 32))
        check_path = Path(self.cache.name) / "checked.png"
        checkbox_image().save(str(check_path))
        self.list.setStyleSheet('QListWidget::indicator:checked { image: url("' + check_path.as_posix() + '"); background: transparent; border: none; }')
        self.list.currentRowChanged.connect(self.show_current)
        self.list.itemChanged.connect(self.update_selection_label)
        self.list_stack = QStackedWidget()
        empty = QWidget()
        empty.setObjectName("previewSurface")
        empty_box = QVBoxLayout(empty)
        empty_box.setSpacing(12)
        empty_box.addStretch()
        empty_mark = label("▧", "emptyTitle")
        empty_mark.setStyleSheet("font-size: 42px; color: #87659f;")
        empty_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_box.addWidget(empty_mark)
        empty_title = label("Tu próxima referencia", "emptyTitle")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_box.addWidget(empty_title)
        hint = label("Pegá un enlace y analizalo.\nSus fotos y videos aparecerán acá.", "emptyHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        empty_box.addWidget(hint)
        empty_box.addStretch()
        self.list_stack.addWidget(empty)
        self.list_stack.addWidget(self.list)
        column.addWidget(self.list_stack, 1)
        row = QHBoxLayout()
        self.select_all = button("Marcar todos", lambda: self.mark(True), "quiet")
        self.select_none = button("Desmarcar", lambda: self.mark(False), "quiet")
        row.addWidget(self.select_all)
        row.addWidget(self.select_none)
        row.addStretch()
        column.addLayout(row)
        split.addWidget(left)

        right, column = card()
        row = QHBoxLayout()
        self.details = label("Previsualización", "sectionTitle")
        self.details.setStyleSheet("font-size: 16px;")
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setWordWrap(True)
        self.details.setMaximumHeight(38)
        row.addWidget(self.details, 1)
        row.addWidget(label("Original intacto", "badge"))
        column.addLayout(row)
        self.stack = QStackedWidget()
        self.image = ImagePreview("Tu contenido, en primer plano.\n\nAnalizá un enlace para ver la previsualización.")
        self.image.setObjectName("previewSurface")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumSize(0, 0)
        self.image.setStyleSheet("QLabel { background: #100d17; color: #9d89b2; border: 1px solid #4a355f; border-radius: 10px; padding: 2px; }")
        self.video = QVideoWidget()
        self.stack.addWidget(self.image)
        self.stack.addWidget(self.video)
        self.portrait = PortraitFrame(self.stack)
        column.addWidget(self.portrait, 1)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.errorOccurred.connect(lambda *_: self.status.setText("No se pudo reproducir este códec. Podés guardar el archivo original sin recompresión."))
        row = QHBoxLayout()
        self.preview_button = button("Reintentar", self.preview, "quiet")
        self.preview_button.hide()
        self.zoom = QSlider(Qt.Orientation.Horizontal)
        self.zoom.setRange(25, 200)
        self.zoom.setValue(80)
        self.zoom.setToolTip("100% ajusta la imagen al panel. Arrastrá la foto para moverla al ampliar.")
        self.zoom_label = label("80%")
        self.zoom.valueChanged.connect(self.change_zoom)
        self.zoom_controls = QWidget()
        zoom_row = QHBoxLayout(self.zoom_controls)
        zoom_row.setContentsMargins(0, 0, 0, 0)
        zoom_row.addWidget(label("Zoom"))
        zoom_row.addWidget(self.zoom, 1)
        zoom_row.addWidget(self.zoom_label)
        zoom_row.addWidget(button("Ajustar", lambda: self.zoom.setValue(100), "quiet"))
        column.addWidget(self.zoom_controls)
        self.play_button = button("▶ / Pausa", self.toggle_play, "quiet")
        self.play_button.hide()
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.hide()
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.player.positionChanged.connect(self.seek.setValue)
        self.player.durationChanged.connect(lambda duration: self.seek.setRange(0, duration))
        row.addWidget(self.preview_button)
        row.addWidget(self.play_button)
        row.addWidget(self.seek, 1)
        column.addLayout(row)
        split.addWidget(right)
        split.setSizes([300, 880])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        layout.addWidget(split, 1)

        downloads, download_box = card()
        download_box.setContentsMargins(20, 13, 20, 13)
        row = QHBoxLayout()
        selection_column = QVBoxLayout()
        selection_column.setSpacing(4)
        self.selection_label = label("Sin elementos seleccionados")
        selection_column.addWidget(self.selection_label)
        download_box.addLayout(selection_column)
        self.download_one = button("Guardar visible", lambda: self.download("one"), "quiet")
        self.download_selected = button("Guardar selección", lambda: self.download("selected"))
        self.download_all = button("Guardar todos", lambda: self.download("all"))
        self.download_zip = button("Descargar ZIP ↓", lambda: self.download("zip"), "primary")
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, widget in enumerate((self.download_one, self.download_selected, self.download_all, self.download_zip)):
            grid.addWidget(widget, i // 2, i % 2)
        download_box.addLayout(grid)
        download_box.setContentsMargins(0, 6, 0, 0)
        downloads.setObjectName("downloadActions")
        left_column.addWidget(downloads)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        row = QHBoxLayout()
        self.status = label("Listo para tu próximo enlace.")
        self.status.setWordWrap(True)
        row.addWidget(self.status, 1)
        self.cancel_button = button("Cancelar", self.cancel, "quiet")
        self.cancel_button.setEnabled(False)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        footer = QHBoxLayout()
        self.session_button = button("Sesión local…", self.configure_session, "quiet")
        self.restore_button = button("Recuperar versión anterior", lambda: self.launch_update(None, True), "quiet")
        footer.addWidget(self.session_button)
        footer.addWidget(self.restore_button)
        footer.addStretch()
        layout.addLayout(footer)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self.controls = [self.url, self.analyze_button, self.folder_button, self.session_button,
                         self.update_button, self.restore_button, self.select_all, self.select_none,
                         self.preview_button, self.download_one, self.download_selected,
                         self.download_all, self.download_zip, self.list]
        self.refresh_controls(False)

    def update_selection_label(self, *_):
        count = sum(self.list.item(i).checkState() == Qt.CheckState.Checked
                    for i in range(self.list.count()))
        self.selection_label.setText(f"{count} de {len(self.items)} seleccionados" if self.items
                                     else "Sin elementos seleccionados")
        self.count_label.setText(f"{len(self.items)} elemento{'s' if len(self.items) != 1 else ''}")

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
        if self.preview_task:
            self.preview_task.cancel.set()
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
        else:
            self.queue_preview()

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
        self.preview_generation += 1
        self.previews = {}
        self.thumbnails = {}
        self.preview_failures = set()
        self.list.clear()
        for item in items:
            row = QListWidgetItem(f"{item.index:03d} · {'Video' if item.kind == 'video' else 'Foto'}")
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked)
            self.list.addItem(row)
        self.list_stack.setCurrentIndex(1 if items else 0)
        self.update_selection_label()
        self.list.setCurrentRow(0)
        self.report(100, f"{len(items)} elemento(s) encontrados. Las previsualizaciones se cargan automáticamente.")
        self.refresh_controls(bool(self.task))
        QTimer.singleShot(0, self.queue_preview)

    def mark(self, selected):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked)

    def show_current(self, index):
        self.player.stop(); self.player.setSource(QUrl())
        self.stack.setCurrentIndex(0)
        self.pixmap = None
        self.image.set_image(None)
        self.image.setText("")
        self.preview_button.hide()
        if not 0 <= index < len(self.items):
            return
        item = self.items[index]
        self.portrait.set_ratio(9 / 16 if item.kind == "video" else 3 / 4)
        self.zoom_controls.setVisible(item.kind != "video")
        self.play_button.setVisible(item.kind == "video")
        self.seek.setVisible(item.kind == "video")
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
            failed = (item.index, "full") in self.preview_failures
            self.image.setText("No se pudo cargar la previsualización. Podés reintentar." if failed
                               else "Cargando previsualización…" + ("\nEl video con audio puede tardar." if item.kind == "video" else ""))
            self.preview_button.setVisible(failed)
        QTimer.singleShot(0, self.queue_preview)

    def scale_image(self):
        if self.pixmap and not self.pixmap.isNull():
            self.portrait.set_ratio(self.pixmap.width() / self.pixmap.height())
            self.image.set_image(self.pixmap)

    def change_zoom(self, value):
        self.zoom_label.setText(f"{value}%")
        self.image.set_zoom(value)

    def preview(self):
        index = self.list.currentRow()
        if not 0 <= index < len(self.items):
            return
        self.preview_failures.discard((self.items[index].index, "full"))
        self.show_current(index)

    def queue_preview(self):
        # Independent background queue: selecting/checking/saving stays responsive.
        # New selections take priority when the current request completes.
        if self.task or self.preview_task or self.pending_close or not self.items:
            return
        current = self.list.currentRow()
        candidates = []
        if 0 <= current < len(self.items):
            candidates.append((self.items[current], "full"))
        candidates.extend((item, "full" if item.kind != "video" else "thumb") for item in self.items)
        for item, kind in candidates:
            cached = self.previews if kind == "full" else self.thumbnails
            if item.index not in cached and (item.index, kind) not in self.preview_failures:
                if kind == "thumb" and not item.thumbnail:
                    continue
                break
        else:
            return
        generation = self.preview_generation
        cookies = self.settings.cookies
        folder = Path(self.cache.name) / uuid.uuid4().hex
        def action(cancel, progress):
            if kind == "full":
                return engines.fetch(item, folder, cancel, progress, cookies)
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / "thumbnail.jpg"
            engines.direct_download(item.thumbnail, path, cancel, progress, cookies, item.source)
            return path
        def done(path):
            if generation != self.preview_generation or self.pending_close:
                return
            (self.previews if kind == "full" else self.thumbnails)[item.index] = path
            index = self.items.index(item)
            if kind == "thumb" or item.kind != "video":
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    self.list.item(index).setIcon(QIcon(pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio,
                                                                    Qt.TransformationMode.SmoothTransformation)))
            if kind == "full" and index == self.list.currentRow():
                self.show_current(index)
                if item.kind != "video" and (not self.pixmap or self.pixmap.isNull()):
                    self.image.setText("Este formato no se puede previsualizar en esta PC.\nPodés guardar el archivo original.")
        def error(message):
            if generation != self.preview_generation or task.cancel.is_set():
                return
            self.preview_failures.add((item.index, kind))
            if kind == "full" and self.items[self.list.currentRow()] is item:
                self.show_current(self.list.currentRow())
                self.status.setText(message)
        task = self.preview_task = Task(action, self)
        task.result.connect(done)
        task.error.connect(error)
        task.finished.connect(self.preview_finished)
        task.start()

    def preview_finished(self):
        old, self.preview_task = self.preview_task, None
        old.deleteLater()
        if self.pending_close:
            self.close()
        else:
            self.queue_preview()

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
        if self.task or self.preview_task:
            self.pending_close = True
            self.cancel()
            if self.preview_task:
                self.preview_task.cancel.set()
            event.ignore()
            return
        self.player.stop(); self.player.setSource(QUrl())
        try:
            self.cache.cleanup()
        except OSError:
            pass
        if self.shell_hwnd is not None:
            try:
                windows_shell.clear_window(self.shell_hwnd)
            except OSError:
                pass
            self.shell_hwnd = None
        event.accept()


def main(smoke=False):
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Neyen.MediaDownloader.Desktop")
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setWindowIcon(app_icon())
    app.setApplicationName("MediaDownloader")
    app.setOrganizationName("MediaDownloader")
    window = Window()
    shell_info = {}
    if sys.platform == "win32" and getattr(sys, "frozen", False) and app.platformName() == "windows":
        try:
            window.shell_hwnd = int(window.winId())
            shell_info = windows_shell.configure_window(window.shell_hwnd, sys.executable)
        except OSError:
            window.status.setText("No se pudo registrar el acceso de la barra de tareas. Volvé a abrir el programa.")
    window.show()
    if smoke:
        if "--shell-report" in sys.argv:
            import json
            report_path = Path(sys.argv[sys.argv.index("--shell-report") + 1])
            report_path.write_text(json.dumps(shell_info), encoding="utf-8")
            if not shell_info:
                return 2
        # Real Qt window, multimedia objects and extractor entrypoints must initialize.
        import gallery_dl, yt_dlp
        if not gallery_dl or not yt_dlp or not window.isVisible():
            return 1
        QTimer.singleShot(1200, app.quit)
    result = app.exec()
    window.close()
    return result
