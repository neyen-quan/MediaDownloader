"""Paint images without feeding their dimensions back into the Qt layout."""
from PySide6.QtCore import Qt, QSize, QPointF, QRectF
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class PortraitFrame(QWidget):
    """A bounded portrait viewport; media size never changes the outer layout."""
    def __init__(self, child):
        super().__init__()
        self.child = child
        child.setParent(self)
        self.ratio = 3 / 4
        self.setMinimumSize(230, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self):
        return QSize(390, 520)

    def set_ratio(self, ratio):
        self.ratio = max(9 / 16, min(3 / 4, ratio))
        self.place_child()

    def place_child(self):
        width = min(self.width(), int(self.height() * self.ratio))
        height = min(self.height(), int(width / self.ratio))
        self.child.setGeometry((self.width() - width) // 2, (self.height() - height) // 2, width, height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.place_child()


class ImagePreview(QLabel):
    def __init__(self, text=""):
        super().__init__(text)
        self.source = None
        self.zoom = 80
        self.offset = QPointF()
        self.drag_position = None
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

    def sizeHint(self):
        return QSize(360, 260)

    def minimumSizeHint(self):
        return QSize(0, 0)

    def set_image(self, pixmap):
        self.source = pixmap
        self.offset = QPointF()
        self.update()

    def set_zoom(self, value):
        self.zoom = value
        self.offset = QPointF()
        self.update()

    def image_rect(self):
        if self.source is None or self.source.isNull():
            return QRectF()
        area = self.contentsRect().adjusted(12, 12, -12, -12)
        ratio = min(area.width() / self.source.width(), area.height() / self.source.height())
        size = self.source.size().toSizeF() * (ratio * self.zoom / 100)
        center = QPointF(area.center()) + self.offset
        return QRectF(center.x() - size.width() / 2, center.y() - size.height() / 2,
                      size.width(), size.height())

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.source is not None and not self.source.isNull():
            painter = QPainter(self)
            painter.setClipRect(self.contentsRect().adjusted(2, 2, -2, -2))
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(self.image_rect(), self.source, QRectF(self.source.rect()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.source is not None:
            self.drag_position = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_position is not None:
            self.offset += event.position() - self.drag_position
            self.drag_position = event.position()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)
