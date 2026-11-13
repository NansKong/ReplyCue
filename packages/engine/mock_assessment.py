"""User-selected, in-memory screenshots for mock questions. No background capture."""
import base64
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QPainter, QColor, QPen
from PySide6.QtWidgets import QApplication, QDialog
from cloud import CloudJob
import managed_ai

LANGUAGES = ('Python 3', 'JavaScript', 'TypeScript', 'Java', 'C++', 'SQL')

class RegionPicker(QDialog):
    def __init__(self, screen, pixmap):
        super().__init__()
        self.pixmap, self.selection, self.origin = pixmap, QRect(), None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CrossCursor)
        self.setWindowTitle('ReplyCue — Select a mock question · Esc to cancel')
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.reject)
        self.timeout.start(150000)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 18))
        if not self.selection.isNull():
            painter.setPen(QPen(QColor('#c9f4ac'), 2))
            painter.drawRect(self.selection)
        painter.setPen(QColor('white'))
        painter.drawText(20, 32, 'Drag around ONE mock question, including all options or constraints. Esc cancels.')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            self.selection = QRect(self.origin, event.position().toPoint()).normalized().intersected(self.rect())
            self.update()

    def mouseReleaseEvent(self, event):
        if self.origin is not None and event.button() == Qt.LeftButton:
            self.selection = QRect(self.origin, event.position().toPoint()).normalized().intersected(self.rect())
            if self.selection.width() >= 40 and self.selection.height() >= 40:
                self.accept()
            else:
                self.reject()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()


def capture_region():
    screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
    pixmap = screen.grabWindow(0)
    if pixmap.isNull():
        raise ValueError('Windows could not capture this display. Try another window.')
    picker = RegionPicker(screen, pixmap)
    if picker.exec() != QDialog.Accepted:
        return None
    scale_x, scale_y = pixmap.width() / picker.width(), pixmap.height() / picker.height()
    rect = picker.selection
    crop = pixmap.copy(round(rect.x()*scale_x), round(rect.y()*scale_y),
                       round(rect.width()*scale_x), round(rect.height()*scale_y))
    crop = crop.scaled(2048, 2048, Qt.KeepAspectRatio, Qt.SmoothTransformation) if max(crop.width(), crop.height()) > 2048 else crop
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    if not crop.save(buffer, 'JPEG', 85):
        raise ValueError('Could not prepare the selected image.')
    buffer.close()
    if len(data) > 1500000:
        raise ValueError('Capture a smaller question region.')
    return 'data:image/jpeg;base64,' + base64.b64encode(bytes(data)).decode('ascii')


class MockJob(CloudJob):
    def __init__(self, image, language, question_type):
        super().__init__('', '', '', {}, question='Mock question — ' + question_type)
        self.image, self.language, self.question_type = image, language, question_type
        self.coding_answer = True

    def run(self):
        try:
            if not managed_ai.enabled():
                raise ValueError('Mock screen questions currently require a signed-in ReplyCue account.')
            result = managed_ai.call({'kind': 'mock-assessment', 'image': self.image,
                'language': self.language, 'questionType': self.question_type},
                on_update=lambda text: self.answer.emit(text) if not self.isInterruptionRequested() else None,
                interrupted=self.isInterruptionRequested)
            if not self.isInterruptionRequested():
                self.final_answer = result['text'].strip()
                if not self.final_answer:
                    raise ValueError('No solution was returned. Try a clearer capture.')
                self.answer.emit(self.final_answer)
        except (managed_ai.ManagedError, ValueError) as error:
            self.problem.emit(str(error))
        except Exception:
            self.problem.emit('Mock question analysis failed. Check your connection and try again.')
        finally:
            self.image = None
