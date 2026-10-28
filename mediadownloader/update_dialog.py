"""Online and local updates share the application's existing installer/helper."""
import sys
from pathlib import Path
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox
from . import __version__, update_channel
from .core import data_dir, UserError
from .updater import validate_package


class UpdateDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.info = None
        self.setWindowTitle('Actualizar MediaDownloader')
        self.setStyleSheet('QDialog { background: #16121e; }')
        self.resize(680, 330)
        box = QVBoxLayout(self)
        self.installed = QLabel('Versión instalada: ' + __version__)
        box.addWidget(self.installed)
        self.available = QLabel('Versión disponible: sin consultar')
        box.addWidget(self.available)
        box.addWidget(QLabel('Canal de actualizaciones de GitHub'))
        self.channel = QLineEdit(window.settings.update_channel)
        box.addWidget(self.channel)
        row = QHBoxLayout()
        self.save = QPushButton('Guardar canal'); self.save.clicked.connect(self.save_channel)
        self.check_button = QPushButton('Buscar actualizaciones'); self.check_button.clicked.connect(self.check)
        row.addWidget(self.save); row.addWidget(self.check_button); box.addLayout(row)
        self.message = QLabel('Actualizaciones online habilitadas. Consultá GitHub o elegí un ZIP local.')
        self.message.setWordWrap(True); box.addWidget(self.message)
        self.progress = QLabel(''); box.addWidget(self.progress)
        row = QHBoxLayout()
        self.install = QPushButton('Descargar e instalar'); self.install.setObjectName('primary')
        self.install.clicked.connect(self.download)
        self.local = QPushButton('Instalar ZIP local…'); self.local.clicked.connect(self.local_zip)
        row.addWidget(self.install); row.addWidget(self.local); box.addLayout(row)
        self.cancel_button = QPushButton('Cancelar operación'); self.cancel_button.clicked.connect(window.cancel)
        box.addWidget(self.cancel_button)
        close = QPushButton('Cerrar'); close.clicked.connect(self.reject); box.addWidget(close)
        self.refresh()

    def reject(self):
        if not self.window.task:
            super().reject()

    def closeEvent(self, event):
        if self.window.task:
            event.ignore()
        else:
            super().closeEvent(event)

    def refresh(self):
        busy = bool(self.window.task)
        for widget in (self.channel, self.save, self.check_button, self.local):
            widget.setEnabled(not busy)
        self.install.setEnabled(not busy and bool(self.info and self.info['patch'] and not self.info['up_to_date']))
        self.cancel_button.setEnabled(busy)

    def run(self, action, done):
        if self.window.task:
            return
        self.window.start(action, done)
        self.window.task.error.connect(self.message.setText)
        self.window.task.progress.connect(lambda value, message: self.progress.setText(f'{message} {value}%'))
        self.window.task.finished.connect(self.refresh)
        self.refresh()

    def save_channel(self):
        value = self.channel.text().strip()
        if not update_channel.valid_url(value, channel=True):
            QMessageBox.warning(self, 'Canal inválido', 'Usá una URL HTTPS de GitHub que termine en /latest.json.')
            return False
        old = self.window.settings.update_channel
        self.window.settings.update_channel = value
        try:
            self.window.settings.save()
        except OSError:
            self.window.settings.update_channel = old
            QMessageBox.warning(self, 'Canal', 'No se pudo guardar el canal.')
            return False
        self.info = None; self.refresh()
        return True

    def check(self):
        if not self.save_channel():
            return
        channel = self.window.settings.update_channel
        def done(info):
            self.info = info
            self.available.setText('Versión disponible: ' + info['available'])
            if info['up_to_date']:
                self.message.setText('Ya tenés la última versión.')
            elif info['patch']:
                self.message.setText(f"Actualización {info['installed']} → {info['available']}. Parche de {info['patch']['size'] / 1024**2:.1f} MiB. Se pedirá confirmación antes de instalar.")
            else:
                self.message.setText('No hay un parche directo para esta versión. Instalá primero la transición o un ZIP local compatible.')
        self.run(lambda cancel, progress: update_channel.check(channel, __version__, cancel), done)

    def confirm(self, path, manifest):
        answer = QMessageBox.question(self, 'Instalar actualización',
            f"MediaDownloader {__version__} → {manifest['version']} verificado.\n"
            'Se cerrará el programa, se respaldará la versión actual y se reiniciará. ¿Continuar?')
        if answer == QMessageBox.StandardButton.Yes:
            self.window.after_task = lambda: self.window.launch_update(path)
            self.accept()

    def download(self):
        info = self.info
        if not info or not info['patch']:
            return
        def action(cancel, progress):
            path = update_channel.download(info, data_dir() / 'updates', cancel, progress)
            try:
                manifest = validate_package(path, Path(sys.executable).parent)
                if manifest['schema'] != 2 or manifest['base']['version'] != __version__ or manifest['version'] != info['available']:
                    raise UserError('El ZIP no coincide con las versiones anunciadas por el canal.')
                return path, manifest
            except BaseException:
                path.unlink(missing_ok=True)
                raise
        self.run(action, lambda result: self.confirm(*result))

    def local_zip(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Instalar actualización local', '', 'Actualización (*.zip)')
        if path:
            self.run(lambda cancel, progress: (path, validate_package(path, Path(sys.executable).parent)),
                     lambda result: self.confirm(*result))
