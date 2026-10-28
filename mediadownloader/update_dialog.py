"""Online and local updates share the application's existing installer/helper."""
import sys
import time
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox, QProgressBar
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
        self.bar = QProgressBar()
        self.bar.setRange(0, 100); self.bar.setValue(0)
        self.bar.setStyleSheet('QProgressBar { min-height: 22px; max-height: 22px; border: 1px solid #51405f; border-radius: 5px; text-align: center; background: #241b30; } QProgressBar::chunk { background: #9763df; }')
        box.addWidget(self.bar)
        self.activity = QLabel(''); box.addWidget(self.activity)
        self.started_at = self.last_advance = time.monotonic()
        self.clock = QTimer(self); self.clock.setInterval(1000)
        self.clock.timeout.connect(self.tick)
        row = QHBoxLayout()
        self.install = QPushButton('Descargar e instalar'); self.install.setObjectName('primary')
        self.install.clicked.connect(self.download)
        self.local = QPushButton('Instalar ZIP local…'); self.local.clicked.connect(self.local_zip)
        row.addWidget(self.install); row.addWidget(self.local); box.addLayout(row)
        self.cancel_button = QPushButton('Cancelar operación'); self.cancel_button.clicked.connect(window.cancel)
        box.addWidget(self.cancel_button)
        close = QPushButton('Cerrar'); close.clicked.connect(self.reject); box.addWidget(close)
        self.refresh()

    def report(self, value, message):
        self.last_advance = time.monotonic()
        self.bar.setRange(0, 0 if value < 0 else 100)
        if value >= 0:
            self.bar.setValue(value)
        self.progress.setText(message)
        self.tick()

    def tick(self):
        elapsed = int(time.monotonic() - self.started_at)
        idle = int(time.monotonic() - self.last_advance)
        self.activity.setText(f'Tiempo transcurrido: {elapsed}s' + (f' · Sin avance nuevo hace {idle}s' if idle >= 5 else ''))

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
        self.started_at = self.last_advance = time.monotonic()
        self.report(-1, 'Iniciando operación…')
        self.clock.start()
        self.window.task.error.connect(self.operation_failed)
        self.window.task.progress.connect(self.report)
        self.window.task.finished.connect(self.operation_finished)
        self.refresh()

    def operation_finished(self):
        self.clock.stop()
        self.refresh()
        if self.bar.maximum() == 0:
            self.bar.setRange(0, 100)

    def operation_failed(self, message):
        self.message.setText(message)
        self.progress.setText('Operación detenida: ' + message)
        self.bar.setRange(0, 100); self.bar.setValue(0)

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
        def action(cancel, progress):
            progress(-1, 'Consultando el canal de GitHub…')
            result = update_channel.check(channel, __version__, cancel)
            progress(100, 'Consulta terminada.')
            return result
        self.run(action, done)

    def confirm(self, path, manifest):
        answer = QMessageBox.question(self, 'Instalar actualización',
            f"MediaDownloader {__version__} → {manifest['version']} verificado.\n"
            'Se cerrará el programa, se respaldará la versión actual y se reiniciará. ¿Continuar?')
        if answer == QMessageBox.StandardButton.Yes:
            self.report(-1, 'Iniciando el instalador. Se cerrará MediaDownloader…')
            self.window.schedule_after_task(lambda: self.window.launch_update(path))
            self.accept()

    def download(self):
        info = self.info
        if not info or not info['patch']:
            return
        def action(cancel, progress):
            path = update_channel.download(info, data_dir() / 'updates', cancel, progress)
            try:
                progress(-1, 'Descarga completa. Verificando el ZIP y la instalación…')
                manifest = validate_package(path, Path(sys.executable).parent, progress=progress, cancel=cancel)
                progress(100, 'Paquete verificado. Esperando tu confirmación.')
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
            def action(cancel, progress):
                progress(-1, 'Verificando el ZIP local…')
                manifest = validate_package(path, Path(sys.executable).parent, progress=progress, cancel=cancel)
                progress(100, 'Paquete verificado. Esperando tu confirmación.')
                return path, manifest
            self.run(action, lambda result: self.confirm(*result))
