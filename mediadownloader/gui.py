from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
import zipfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer, QSize, QSignalBlocker
from PySide6.QtGui import QPixmap, QDesktopServices, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QListWidget, QListWidgetItem, QSplitter, QFileDialog,
    QProgressBar, QMessageBox, QStackedWidget, QSlider, QSizePolicy)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from . import __version__
from .core import Settings, UserError, Cancelled, data_dir, save_selection, public_url, copy_stream
from .appearance import STYLE, app_icon, checkbox_image, line_icon, empty_artwork
from .image_preview import ImagePreview, PortraitFrame
from . import windows_shell
from . import engines
from .updater import validate_package, locations, UpdateError, prepare_helper


class Task(QThread):
    progress = Signal(int, str)
    result = Signal(object)
    error = Signal(str)
    cancelled = Signal(str)

    def __init__(self, action, parent):
        super().__init__(parent)
        self.action = action
        self.cancel = threading.Event()

    def run(self):
        try:
            self.result.emit(self.action(self.cancel, self.progress.emit))
        except Cancelled as e:
            self.cancelled.emit(str(e))
        except (UserError, UpdateError) as e:
            self.error.emit(str(e))
        except OSError:
            self.error.emit("No se pudo acceder a un archivo. Revisá los permisos y el espacio libre de la carpeta.")
        except Exception as e:
            # Extractor exceptions may contain signed media URLs or cookies; don't display them.
            self.error.emit(f"No se pudo completar la operación ({type(e).__name__}). Volvé a intentarlo o actualizá el programa.")


def dropped_link(mime):
    if mime.hasUrls():
        urls = mime.urls()
        if len(urls) != 1:
            return ""
        value = urls[0].toString()
    elif mime.hasText():
        value = mime.text().strip()
    else:
        return ""
    try:
        public_url(value)
    except UserError:
        return ""
    return value


class LinkEdit(QLineEdit):
    link_dropped = Signal(str)

    def dragEnterEvent(self, event):
        if self.isEnabled() and dropped_link(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        value = dropped_link(event.mimeData())
        if self.isEnabled() and value:
            self.link_dropped.emit(value)
            event.acceptProposedAction()
        else:
            event.ignore()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"MediaDownloader · {__version__}")
        self.setMinimumSize(980, 660)
        available = self.screen().availableGeometry()
        self.resize(min(1240, max(980, available.width() - 48)),
                    min(860, max(660, available.height() - 72)))
        self.setStyleSheet(STYLE)
        self.setWindowIcon(app_icon())
        self.setAcceptDrops(True)
        self.settings = Settings.load()
        self.task = None
        self.after_task = None
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

        def button(text, action, name="", tip="", icon=""):
            widget = QPushButton(text)
            widget.setObjectName(name)
            widget.setCursor(Qt.CursorShape.PointingHandCursor)
            widget.clicked.connect(action)
            if icon:
                widget.setIcon(line_icon(icon, "#281738" if name == "primary" else "#c3b9d2"))
                widget.setIconSize(QSize(18, 18))
            if tip:
                widget.setToolTip(tip)
            return widget

        def card(name="card"):
            widget = QWidget()
            widget.setObjectName(name)
            box = QVBoxLayout(widget)
            box.setContentsMargins(16, 14, 16, 14)
            box.setSpacing(10)
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
        header_row.setContentsMargins(22, 12, 22, 12)
        header_row.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(self.windowIcon().pixmap(38, 38))
        logo.setFixedSize(38, 38)
        header_row.addWidget(logo)
        brand_column = QVBoxLayout()
        brand_column.setSpacing(1)
        brand_row = QHBoxLayout()
        brand_row.setSpacing(9)
        brand_row.addWidget(label("MediaDownloader", "brand"))
        brand_row.addWidget(label(__version__, "version"))
        brand_row.addStretch()
        brand_column.addLayout(brand_row)
        brand_column.addWidget(label("Fotos y videos en calidad original", "tagline"))
        header_row.addLayout(brand_column, 1)
        self.session_button = button("Sesión local", self.configure_session, "quiet",
                                     "Administrar la sesión del navegador guardada en esta PC", "user")
        self.update_button = button("Buscar actualizaciones", self.update_program, "quiet", icon="refresh")
        header_row.addWidget(self.session_button)
        header_row.addWidget(self.update_button)
        outer.addWidget(header)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 14, 20, 10)
        layout.setSpacing(10)

        source, source_box = card("sourceCard")
        source_box.setContentsMargins(12, 10, 12, 10)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.url = LinkEdit()
        self.url.setObjectName("sourceInput")
        self.url.setAccessibleName("Enlace de origen")
        self.url.setPlaceholderText("Pegá o arrastrá un enlace de Instagram, TikTok o YouTube…")
        self.url.setToolTip("Pegá un enlace y presioná Enter, o arrastralo desde el navegador para analizarlo.")
        self.url.addAction(line_icon("link"), QLineEdit.ActionPosition.LeadingPosition)
        self.url.link_dropped.connect(self.receive_link)
        self.url.setMinimumWidth(130)
        self.url.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.url.setClearButtonEnabled(True)
        self.analyze_button = button("Analizar enlace", self.analyze, "primary", icon="arrow")
        self.analyze_button.setMinimumWidth(150)
        self.url.returnPressed.connect(self.analyze)
        row.addWidget(self.url, 1)
        row.addWidget(self.analyze_button)
        source_box.addLayout(row)
        layout.addWidget(source)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(14)
        self.content_split = split
        left, column = card()
        left.setMinimumWidth(280)
        left.setMaximumWidth(370)
        row = QHBoxLayout()
        row.addWidget(label("Contenido", "sectionTitle"))
        row.addStretch()
        self.count_label = label("0 elementos", "badge")
        row.addWidget(self.count_label)
        column.addLayout(row)
        self.list = QListWidget()
        self.list.setAccessibleName("Archivos del enlace")
        self.list.setIconSize(QSize(32, 32))
        self.list.setSpacing(3)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        check_path = Path(self.cache.name) / "checked.png"
        checkbox_image().save(str(check_path))
        self.list.setStyleSheet('QListWidget::indicator:checked { image: url("' + check_path.as_posix() + '"); background: transparent; border: none; }')
        self.list.currentRowChanged.connect(self.show_current)
        self.list.itemChanged.connect(self.update_selection_label)
        self.list_stack = QStackedWidget()
        empty = QWidget()
        empty.setObjectName("listEmpty")
        empty_box = QVBoxLayout(empty)
        empty_box.setContentsMargins(12, 12, 12, 12)
        empty_box.setSpacing(10)
        empty_box.addStretch()
        empty_mark = QLabel()
        empty_mark.setPixmap(QPixmap.fromImage(empty_artwork(136)).scaled(
            68, 68, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        empty_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_box.addWidget(empty_mark)
        empty_title = label("Tu próxima descarga", "emptyTitle")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_box.addWidget(empty_title)
        hint = label("Analizá un enlace para elegir\nqué fotos y videos guardar.", "emptyHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        empty_box.addWidget(hint)
        empty_box.addStretch()
        self.list_stack.addWidget(empty)
        self.list_stack.addWidget(self.list)
        column.addWidget(self.list_stack, 1)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.select_all = button("Marcar todos", lambda: self.mark(True), "quiet")
        self.select_none = button("Desmarcar", lambda: self.mark(False), "quiet")
        row.addWidget(self.select_all, 1)
        row.addWidget(self.select_none, 1)
        column.addLayout(row)
        split.addWidget(left)

        right, column = card("previewCard")
        row = QHBoxLayout()
        self.details = label("Vista previa", "sectionTitle")
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setWordWrap(True)
        self.details.setMaximumHeight(40)
        row.addWidget(self.details, 1)
        row.addWidget(label("CALIDAD ORIGINAL", "eyebrow"))
        column.addLayout(row)
        self.stack = QStackedWidget()
        self.image = ImagePreview()
        self.image.setObjectName("previewSurface")
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setWordWrap(True)
        self.image.setMinimumSize(0, 0)
        art_path = Path(self.cache.name) / "preview-empty.png"
        empty_artwork(192).save(str(art_path))
        self.image.setText(
            f'<div><img src="{art_path.as_uri()}" width="88" height="88" /></div>'
            '<p style="font-size: 17px; font-weight: 600; color: #e6dbf5;">Todo empieza con un enlace</p>'
            '<p style="font-size: 12px; color: #a498b3;">Fotos, videos y carruseles.<br />Explorá antes de descargar.</p>'
        )
        self.video = QVideoWidget()
        self.stack.addWidget(self.image)
        self.stack.addWidget(self.video)
        self.portrait = PortraitFrame(self.stack)
        # Small notebooks still keep the destination and download actions on screen.
        self.portrait.setMinimumSize(180, 138)
        column.addWidget(self.portrait, 1)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.errorOccurred.connect(lambda *_: self.status.setText("No se pudo reproducir este códec. Podés guardar el archivo original sin recompresión."))
        row = QHBoxLayout()
        self.preview_button = button("Reintentar", self.preview, "quiet", icon="refresh")
        self.preview_button.hide()
        self.zoom = QSlider(Qt.Orientation.Horizontal)
        self.zoom.setRange(25, 200)
        self.zoom.setValue(80)
        self.zoom.setAccessibleName("Zoom de la imagen")
        self.zoom.setToolTip("100% ajusta la imagen al panel. Arrastrá la foto para moverla al ampliar.")
        self.zoom_label = label("80%")
        self.zoom_label.setFixedWidth(38)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.zoom.valueChanged.connect(self.change_zoom)
        self.zoom_controls = QWidget()
        self.zoom_controls.setObjectName("previewTools")
        zoom_row = QHBoxLayout(self.zoom_controls)
        zoom_row.setContentsMargins(0, 0, 0, 0)
        zoom_row.setSpacing(12)
        zoom_row.addWidget(label("Zoom"))
        zoom_row.addWidget(self.zoom, 1)
        zoom_row.addWidget(self.zoom_label)
        zoom_row.addWidget(button("Ajustar", lambda: self.zoom.setValue(100), "quiet", icon="fit"))
        column.addWidget(self.zoom_controls)
        self.play_button = button("Reproducir / Pausa", self.toggle_play, "quiet", icon="play")
        self.play_button.hide()
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setAccessibleName("Posición del video")
        self.seek.hide()
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.player.positionChanged.connect(self.seek.setValue)
        self.player.durationChanged.connect(lambda duration: self.seek.setRange(0, duration))
        row.addWidget(self.preview_button)
        row.addWidget(self.play_button)
        row.addWidget(self.seek, 1)
        column.addLayout(row)
        split.addWidget(right)
        split.setSizes([310, 890])
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        layout.addWidget(split, 1)

        downloads, download_box = card("downloadActions")
        download_box.setContentsMargins(16, 10, 16, 10)
        download_box.setSpacing(9)
        destination_row = QHBoxLayout()
        destination_row.setSpacing(10)
        destination_row.addWidget(label("GUARDAR EN", "eyebrow"))
        self.folder = QLineEdit(self.settings.destination)
        self.folder.setObjectName("destinationInput")
        self.folder.setAccessibleName("Carpeta de destino")
        self.folder.setReadOnly(True)
        self.folder.setAcceptDrops(False)
        self.folder.setMinimumWidth(130)
        self.folder.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.folder.setPlaceholderText("Elegí una carpeta para tus descargas")
        self.folder_button = button("Elegir carpeta", self.choose_folder, "quiet", icon="folder")
        self.open_button = button("Abrir", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder.text())) if self.folder.text() else None,
                                  "quiet", "Abrir la carpeta de destino", "open")
        destination_row.addWidget(self.folder, 1)
        destination_row.addWidget(self.folder_button)
        destination_row.addWidget(self.open_button)
        download_box.addLayout(destination_row)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.selection_label = label("Sin elementos seleccionados")
        row.addWidget(self.selection_label, 1)
        self.download_one = button("Guardar visible", lambda: self.download("one"), "quiet")
        self.download_selected = button("Guardar selección", lambda: self.download("selected"))
        self.download_all = button("Guardar todos", lambda: self.download("all"))
        self.download_zip = button("Descargar ZIP", lambda: self.download("zip"), "primary", icon="download")
        for widget in (self.download_one, self.download_selected, self.download_all, self.download_zip):
            row.addWidget(widget)
        download_box.addLayout(row)
        layout.addWidget(downloads)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.status = label("Listo. Pegá un enlace para empezar.")
        self.status.setWordWrap(True)
        self.status.setMinimumWidth(160)
        row.addWidget(self.status, 1)
        self.restore_button = button("Recuperar versión anterior", lambda: self.launch_update(None, True), "textButton")
        row.addWidget(self.restore_button)
        self.cancel_button = button("Cancelar", self.cancel, "quiet")
        self.cancel_button.setEnabled(False)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        # A direct layout can shrink to the notebook viewport. A wrapping scroll
        # area treats the preview's preferred height as a minimum and hides actions.
        outer.addWidget(content, 1)
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
        for button in (self.download_selected, self.download_zip):
            button.setEnabled(bool(count) and not self.task)

    def refresh_controls(self, busy):
        for control in self.controls:
            control.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        for button in [self.download_one, self.download_selected, self.download_all,
                       self.download_zip, self.preview_button, self.select_all, self.select_none]:
            button.setEnabled(not busy and bool(self.items))
        self.restore_button.setEnabled(not busy and getattr(sys, "frozen", False)
                                       and locations(Path(sys.executable).parent)[0].is_dir())
        self.update_selection_label()

    def start(self, action, done):
        if self.task:
            return
        if self.preview_task:
            self.preview_task.cancel.set()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.task = Task(action, self)
        self.refresh_controls(True)
        self.task.progress.connect(self.report)
        self.task.result.connect(done)
        self.task.error.connect(self.failed)
        self.task.cancelled.connect(lambda message: self.report(0, message))
        self.task.finished.connect(self.task_finished)
        self.task.start()

    def report(self, value, message):
        self.progress.setRange(0, 0 if value < 0 else 100)
        if value >= 0:
            self.progress.setValue(value)
        self.status.setText(message)

    def failed(self, message):
        self.report(0, message)
        if not self.pending_close:
            QMessageBox.warning(self, "MediaDownloader", message)

    def schedule_after_task(self, action):
        # QMessageBox.exec() runs a nested event loop: finished may arrive while
        # confirmation is still open. Handle both orders explicitly.
        if self.task:
            self.after_task = action
        else:
            QTimer.singleShot(0, action)

    def task_finished(self):
        old, self.task = self.task, None
        old.deleteLater()
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
        self.refresh_controls(False)
        if self.pending_close:
            self.close()
        elif self.after_task:
            action, self.after_task = self.after_task, None
            QTimer.singleShot(0, action)
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

    def receive_link(self, value):
        if self.task or self.pending_close:
            return
        self.url.setText(value)
        self.analyze()

    def dragEnterEvent(self, event):
        if not self.task and not self.pending_close and dropped_link(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        value = dropped_link(event.mimeData())
        if not self.task and not self.pending_close and value:
            self.receive_link(value)
            event.acceptProposedAction()
        else:
            event.ignore()

    def analyzed(self, items):
        self.player.stop(); self.player.setSource(QUrl())
        # Retain only this source's previews. An active worker owns its directory
        # until it finishes; preview_finished removes it if the result is stale.
        active_folder = getattr(self.preview_task, "cache_folder", None)
        if self.preview_task:
            self.preview_task.cancel.set()
        for folder in {path.parent for path in (*self.previews.values(), *self.thumbnails.values())}:
            if folder != active_folder:
                shutil.rmtree(folder, ignore_errors=True)
        self.items = items
        self.preview_generation += 1
        self.previews = {}
        self.thumbnails = {}
        self.preview_failures = set()
        with QSignalBlocker(self.list):
            self.list.clear()
            for item in items:
                row = QListWidgetItem(f"{item.index:03d} · {'Video' if item.kind == 'video' else 'Foto'}")
                row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                row.setCheckState(Qt.CheckState.Checked)
                self.list.addItem(row)
            self.list.setCurrentRow(0)
        self.list_stack.setCurrentIndex(1 if items else 0)
        self.update_selection_label()
        self.show_current(self.list.currentRow())
        self.report(100, f"{len(items)} elemento(s) encontrados. Las previsualizaciones se cargan automáticamente.")
        self.refresh_controls(bool(self.task))
        QTimer.singleShot(0, self.queue_preview)

    def mark(self, selected):
        with QSignalBlocker(self.list):
            for i in range(self.list.count()):
                self.list.item(i).setCheckState(Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked)
        self.update_selection_label()

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
                    with QSignalBlocker(self.list):
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
        task.cache_folder = folder
        task.result.connect(done)
        task.error.connect(error)
        task.finished.connect(self.preview_finished)
        task.start()

    def preview_finished(self):
        old, self.preview_task = self.preview_task, None
        retained = (*self.previews.values(), *self.thumbnails.values())
        if not any(path.parent == old.cache_folder for path in retained):
            shutil.rmtree(old.cache_folder, ignore_errors=True)
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
                path = folder / Path(item.filename).with_suffix(cached.suffix)
                with cached.open("rb") as source, path.open("wb") as target:
                    copy_stream(source, target, cached.stat().st_size, cancel,
                                lambda percent: progress(percent, "Guardando la previsualización original…"))
                shutil.copystat(cached, path)
                return path
            return engines.fetch(item, folder, cancel, progress, cookies)
        folder = self.folder.text()
        self.start(lambda cancel, progress: save_selection(items, folder, mode == "zip", fetch, cancel, progress),
                   lambda files: self.report(100, f"Guardado en {folder}. {len(files)} archivo(s)."))

    def configure_session(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Sesión local opcional")
        dialog.setText("Instagram, TikTok y YouTube pueden exigir sesión incluso para contenido público.\n\n"
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
        from .update_dialog import UpdateDialog
        self.update_dialog = UpdateDialog(self)
        self.update_dialog.exec()

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
            args = [str(temp / helper.name), "--root", str(root), "--parent", str(os.getpid())]
            if restore:
                shutil.copy2(helper, temp / helper.name)
                args += ["--restore"]
            else:
                shutil.copy2(archive, temp / "package.zip")
                prepare_helper(root, temp / 'package.zip', temp / helper.name)
                args += ["--zip", str(temp / "package.zip")]
            subprocess.Popen(args, cwd=temp)
            self.close()
        except (OSError, ValueError, zipfile.BadZipFile, UpdateError) as error:
            self.failed(f"No se pudo iniciar el actualizador. La aplicación sigue abierta. Detalle: {error}")

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
    if '--expected-version' in sys.argv:
        try:
            if sys.argv[sys.argv.index('--expected-version') + 1] != __version__:
                return 3
        except IndexError:
            return 3
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

