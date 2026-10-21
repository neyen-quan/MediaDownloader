"""Violet desktop identity. All artwork is vector-drawn, including Windows icons."""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QLinearGradient, QIcon, QPixmap


def logo_image(size=256):
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 128, size / 128)
    gradient = QLinearGradient(14, 8, 112, 124)
    gradient.setColorAt(0, QColor("#be9bff"))
    gradient.setColorAt(1, QColor("#7044da"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(2, 2, 124, 124), 30, 30)
    painter.setBrush(QColor("#241438"))
    painter.drawRoundedRect(QRectF(23, 25, 67, 66), 12, 12)
    painter.setPen(QPen(QColor("#eee5ff"), 4, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(QColor("#34204e"))
    painter.drawRoundedRect(QRectF(33, 34, 67, 66), 12, 12)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#eee5ff"))
    play = QPainterPath()
    play.moveTo(49, 49); play.lineTo(49, 75); play.lineTo(70, 62); play.closeSubpath()
    painter.drawPath(play)
    painter.setPen(QPen(QColor("#ffffff"), 7, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawLine(QPointF(90, 63), QPointF(90, 94))
    painter.drawLine(QPointF(79, 83), QPointF(90, 95))
    painter.drawLine(QPointF(90, 95), QPointF(101, 83))
    painter.end()
    return image


def app_icon():
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(logo_image(size)))
    return icon


STYLE = """
QWidget { color: #f1edf9; font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; }
QMainWindow, QWidget#appBody { background: #0e0c13; }
QScrollArea, QScrollArea > QWidget > QWidget { background: #0e0c13; border: none; }
QWidget#header { background: #100e17; border-bottom: 1px solid #2b2439; }
QWidget#card { background: #16121e; border: 1px solid #30273f; border-radius: 14px; }
QWidget#previewSurface { background: #100d17; border: 1px solid #30273f; border-radius: 12px; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 23px; font-weight: 700; letter-spacing: -0.5px; }
QLabel#tagline, QLabel#muted { color: #9e93b1; font-size: 12px; }
QLabel#eyebrow { color: #bc9ce9; font-size: 10px; font-weight: 600; letter-spacing: 1.8px; }
QLabel#sectionTitle { font-size: 21px; font-weight: 600; letter-spacing: -0.4px; }
QLabel#heroTitle { font-size: 28px; font-weight: 600; letter-spacing: -0.6px; }
QLabel#version { color: #c6afeb; border: 1px solid #3e3052; border-radius: 5px; padding: 3px 7px; font-size: 10px; }
QLabel#badge { color: #d2b7ff; background: #251b35; border: 1px solid #403052; border-radius: 12px; padding: 5px 12px; font-size: 11px; }
QLabel#emptyTitle { font-size: 18px; font-weight: 600; color: #dcd0ed; }
QLabel#emptyHint { color: #8c7e9f; font-size: 12px; }
QLineEdit { background: #100d17; border: 1px solid #3b304d; border-radius: 8px; padding: 11px 13px; color: #eee7f9; selection-background-color: #7548b5; }
QLineEdit:focus { border: 1px solid #b28ae9; background: #171020; }
QLineEdit:read-only { color: #b6a7c8; }
QPushButton { background: #20192b; border: 1px solid #433452; border-radius: 8px; padding: 10px 15px; font-weight: 500; color: #e1d4f1; }
QPushButton:hover { background: #30223f; border-color: #8e66b7; }
QPushButton:pressed { background: #3d2b51; }
QPushButton:focus { border-color: #d3adff; }
QPushButton:disabled { color: #736580; background: #1a1522; border-color: #2d2438; }
QPushButton#primary { background: #ba91f4; color: #1a0f2b; border: 1px solid #caa7ff; font-weight: 700; }
QPushButton#primary:hover { background: #cba9ff; }
QPushButton#primary:pressed { background: #a97de8; }
QPushButton#primary:disabled { background: #39284d; border-color: #4a355f; color: #8f76ab; }
QPushButton#quiet { background: transparent; border-color: #3b2f49; color: #bca8d2; padding: 8px 12px; font-size: 12px; }
QPushButton#quiet:hover { background: #241a30; color: #e0c8ff; }
QPushButton#quiet:disabled { color: #655970; border-color: #292232; }
QListWidget { background: #100d17; border: 1px solid #30273f; border-radius: 10px; padding: 7px; outline: none; }
QListWidget::item { background: #1b1525; border: 1px solid #32273f; border-radius: 7px; padding: 4px 7px; margin: 2px; min-height: 32px; font-size: 12px; }
QListWidget::item:hover { background: #251a34; border-color: #634580; }
QListWidget::item:selected { background: #30203f; border: 1px solid #b78ae8; color: #f4eaff; }
QListWidget::indicator { width: 17px; height: 17px; border: 1px solid #6f5885; border-radius: 5px; background: #100d17; margin-right: 10px; }
QListWidget::indicator:checked { background: #b88eee; border-color: #d4b5fc; }
QSplitter::handle { background: #0e0c13; }
QSplitter::handle:horizontal { width: 14px; }
QSplitter::handle:hover { background: #251a33; }
QProgressBar { background: #241b30; border: none; border-radius: 3px; max-height: 5px; min-height: 5px; }
QProgressBar::chunk { background: #b58bf0; border-radius: 3px; }
QSlider::groove:horizontal { height: 4px; background: #382a47; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #ae80ed; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; margin: -5px 0; border-radius: 6px; background: #d8b5ff; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 3px; }
QScrollBar::handle:vertical { background: #51405f; border-radius: 3px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { background: #2b1f39; color: #f0e5ff; border: 1px solid #70528d; padding: 6px; }
QMessageBox { background: #16121e; }
"""
