"""Violet desktop identity. All artwork is vector-drawn, including Windows icons."""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QLinearGradient, QIcon, QPixmap


def checkbox_image():
    image = QImage(40, 40, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#d4bcff"), 2))
    painter.setBrush(QColor("#b998f4"))
    painter.drawRoundedRect(QRectF(2, 2, 36, 36), 9, 9)
    painter.setPen(QPen(QColor("#241536"), 4, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    path = QPainterPath(QPointF(11, 20))
    path.lineTo(17, 26); path.lineTo(29, 13)
    painter.drawPath(path)
    painter.end()
    return image


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


def line_icon(name, color="#c3b9d2"):
    """Small, crisp icons without platform-dependent symbol fonts or network assets."""
    icon = QIcon()
    for mode, ink in ((QIcon.Mode.Normal, color), (QIcon.Mode.Disabled, "#756b83")):
        for size in (20, 40):
            image = QImage(size, size, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.scale(size / 20, size / 20)
            painter.setPen(QPen(QColor(ink), 1.6, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath()
            if name == "folder":
                path.moveTo(2, 6); path.lineTo(2, 4); path.lineTo(8, 4)
                path.lineTo(10, 6); path.lineTo(18, 6); path.lineTo(18, 16)
                path.lineTo(2, 16); path.closeSubpath()
            elif name == "open":
                path.moveTo(11, 3); path.lineTo(17, 3); path.lineTo(17, 9)
                path.moveTo(17, 3); path.lineTo(9, 11)
                path.moveTo(7, 4); path.lineTo(3, 4); path.lineTo(3, 17)
                path.lineTo(16, 17); path.lineTo(16, 13)
            elif name == "download":
                path.moveTo(10, 2); path.lineTo(10, 12)
                path.moveTo(6, 8); path.lineTo(10, 12); path.lineTo(14, 8)
                path.moveTo(3, 13); path.lineTo(3, 17); path.lineTo(17, 17); path.lineTo(17, 13)
            elif name == "arrow":
                path.moveTo(3, 10); path.lineTo(17, 10)
                path.moveTo(12, 5); path.lineTo(17, 10); path.lineTo(12, 15)
            elif name == "refresh":
                path.moveTo(16, 7); path.cubicTo(12, 0, 3, 3, 3, 10)
                path.cubicTo(3, 17, 13, 19, 17, 12)
                path.moveTo(16, 3); path.lineTo(16, 7); path.lineTo(12, 7)
            elif name == "user":
                painter.drawEllipse(QRectF(7, 2, 6, 6))
                path.moveTo(3, 17); path.cubicTo(3, 9, 17, 9, 17, 17)
            elif name == "link":
                path.moveTo(7, 13); path.lineTo(5, 15)
                path.cubicTo(1, 19, -1, 13, 3, 10); path.lineTo(6, 7)
                path.cubicTo(8, 5, 10, 6, 11, 7)
                path.moveTo(9, 13); path.cubicTo(10, 14, 12, 15, 14, 13)
                path.lineTo(17, 10); path.cubicTo(21, 7, 19, 1, 15, 5)
                path.lineTo(13, 7); path.moveTo(7, 11); path.lineTo(13, 9)
            elif name == "fit":
                for x, y, dx, dy in ((3, 3, 4, 4), (17, 3, -4, 4),
                                      (3, 17, 4, -4), (17, 17, -4, -4)):
                    path.moveTo(x, y + dy); path.lineTo(x, y); path.lineTo(x + dx, y)
            elif name == "play":
                path.moveTo(6, 3); path.lineTo(16, 10); path.lineTo(6, 17); path.closeSubpath()
            painter.drawPath(path)
            painter.end()
            icon.addPixmap(QPixmap.fromImage(image), mode)
    return icon


def empty_artwork(size=160):
    """Quiet illustration for empty states, painted at device-independent resolution."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 160, size / 160)
    painter.setPen(Qt.PenStyle.NoPen)
    gradient = QLinearGradient(20, 20, 140, 140)
    gradient.setColorAt(0, QColor("#342646"))
    gradient.setColorAt(1, QColor("#1d1927"))
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(10, 10, 140, 140), 40, 40)
    painter.translate(80, 80)
    painter.rotate(-12)
    painter.setPen(QPen(QColor("#655079"), 2))
    painter.setBrush(QColor("#292034"))
    painter.drawRoundedRect(QRectF(-41, -44, 67, 78), 11, 11)
    painter.rotate(12)
    gradient = QLinearGradient(-20, -30, 40, 50)
    gradient.setColorAt(0, QColor("#4d395f"))
    gradient.setColorAt(1, QColor("#2e233b"))
    painter.setBrush(gradient)
    painter.setPen(QPen(QColor("#a886ce"), 2))
    painter.drawRoundedRect(QRectF(-29, -33, 70, 83), 11, 11)
    painter.setPen(QPen(QColor("#ccb0ed"), 3, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QRectF(11, -18, 11, 11))
    path = QPainterPath(QPointF(-17, 29))
    path.lineTo(-2, 9); path.lineTo(9, 22); path.lineTo(17, 15); path.lineTo(29, 29)
    painter.drawPath(path)
    painter.end()
    return image


STYLE = """
QWidget { color: #eee8f5; font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; }
QMainWindow, QWidget#appBody { background: #100e15; }
QScrollArea, QScrollArea > QWidget > QWidget { background: #100e15; border: none; }
QWidget#header { background: #15121c; border-bottom: 1px solid #2e263a; }
QWidget#card, QWidget#previewCard { background: #1a1621; border: 1px solid #342b40; border-radius: 15px; }
QWidget#sourceCard { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2b2138,stop:1 #1b1723); border: 1px solid #4b375e; border-radius: 13px; }
QWidget#downloadActions { background: #1c1725; border: 1px solid #3b2e49; border-radius: 13px; }
QWidget#previewSurface { background: #120f19; border: 1px solid #31263e; border-radius: 12px; color: #b4a5c4; padding: 10px; }
QWidget#listEmpty { background: #17121f; border: 1px dashed #3b2e49; border-radius: 11px; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 20px; font-weight: 700; letter-spacing: -0.6px; }
QLabel#tagline { color: #9f93af; font-size: 11px; }
QLabel#muted { color: #aa9db9; font-size: 12px; }
QLabel#eyebrow { color: #ad94c5; font-size: 10px; font-weight: 600; letter-spacing: 1.3px; }
QLabel#sectionTitle { font-size: 17px; font-weight: 600; letter-spacing: -0.2px; }
QLabel#heroTitle { font-size: 28px; font-weight: 600; letter-spacing: -0.6px; }
QLabel#version { color: #a590bc; background: #241d30; border: 1px solid #3b2e4c; border-radius: 5px; padding: 2px 6px; font-size: 10px; }
QLabel#badge { color: #ceb5ec; background: #2b2039; border: 1px solid #463255; border-radius: 10px; padding: 4px 9px; font-size: 11px; }
QLabel#emptyTitle { font-size: 15px; font-weight: 600; color: #d9cbe9; }
QLabel#emptyHint { color: #9c8dac; font-size: 12px; }
QLineEdit { background: #120f19; border: 1px solid #40324f; border-radius: 8px; padding: 8px 10px; color: #eee7f9; selection-background-color: #7548b5; }
QLineEdit#sourceInput { min-height: 22px; padding: 7px 10px; font-size: 13px; }
QLineEdit#destinationInput { padding: 6px 10px; border-color: #34293f; }
QLineEdit:focus { border: 1px solid #bd96ee; background: #1a1325; }
QLineEdit:read-only { color: #b9a9ca; }
QPushButton { background: #292033; border: 1px solid #503d61; border-radius: 8px; padding: 9px 13px; font-weight: 500; color: #e5d7f5; }
QPushButton:hover { background: #392849; border-color: #9270b1; }
QPushButton:pressed { background: #49305e; }
QPushButton:focus { border-color: #d9b7ff; }
QPushButton:disabled { color: #897b98; background: #211a2b; border-color: #382c43; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #d0adff,stop:1 #af85ee); color: #281738; border: 1px solid #d2b3ff; font-weight: 700; }
QPushButton#primary:hover { background: #d6b7ff; border-color: #e5ccff; }
QPushButton#primary:pressed { background: #ab82e5; }
QPushButton#primary:disabled { background: #49345f; border-color: #614477; color: #a68cba; }
QPushButton#quiet { background: transparent; border-color: #3d304b; color: #c6b4d9; padding: 7px 10px; font-size: 12px; }
QPushButton#quiet:hover { background: #2e203d; border-color: #74538f; color: #f0dfff; }
QPushButton#quiet:disabled { color: #82738f; border-color: #34293f; }
QPushButton#textButton { background: transparent; border: none; color: #a08db4; padding: 6px 4px; font-size: 11px; }
QPushButton#textButton:hover { color: #e1c5ff; }
QPushButton#textButton:disabled { color: #75677f; }
QListWidget { background: #17121f; border: 1px solid #33283f; border-radius: 10px; padding: 5px; outline: none; }
QListWidget::item { background: #231b2e; border: 1px solid #392b46; border-radius: 8px; padding: 7px 8px; min-height: 33px; font-size: 13px; }
QListWidget::item:hover { background: #30223f; border-color: #74518e; }
QListWidget::item:selected { background: #39264b; border: 1px solid #b78ae8; color: #f4eaff; }
QListWidget::indicator { width: 18px; height: 18px; border: 1px solid #746086; border-radius: 5px; background: #17101e; margin-right: 9px; }
QListWidget::indicator:checked { background: #b88eee; border-color: #d4b5fc; }
QSplitter::handle { background: #100e15; }
QSplitter::handle:hover { background: #30203e; border-radius: 5px; }
QProgressBar { background: #2c2136; border: none; border-radius: 2px; max-height: 3px; min-height: 3px; }
QProgressBar::chunk { background: #c29bf6; border-radius: 2px; }
QSlider::groove:horizontal { height: 4px; background: #40314e; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #b78deb; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; margin: -5px 0; border-radius: 6px; background: #dec2ff; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 3px; }
QScrollBar::handle:vertical { background: #604b72; border-radius: 3px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { background: #2c2039; color: #f0e5ff; border: 1px solid #70528d; padding: 7px; }
QMessageBox { background: #1a1621; }
"""
