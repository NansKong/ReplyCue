"""Scoped, in-memory question capture during an explicitly started mock session."""
import base64
import json
import re
import unicodedata
from difflib import SequenceMatcher
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRect, Qt, QTimer
from PySide6.QtGui import QCursor, QPainter, QColor, QPen, QImage
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


def capture_region(on_selected=None):
    screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
    pixmap = screen.grabWindow(0)
    if pixmap.isNull():
        raise ValueError('Windows could not capture this display. Try another window.')
    picker = RegionPicker(screen, pixmap)
    if picker.exec() != QDialog.Accepted:
        return None
    scale_x, scale_y = pixmap.width() / picker.width(), pixmap.height() / picker.height()
    rect = picker.selection
    if on_selected:
        on_selected(screen, QRect(rect), QRect(screen.geometry()))
    crop = pixmap.copy(round(rect.x()*scale_x), round(rect.y()*scale_y),
                       round(rect.width()*scale_x), round(rect.height()*scale_y))
    return encode_image(crop)


def encode_image(crop):
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


def capture_scope(scope):
    screen, rect, geometry = scope
    if screen not in QApplication.screens() or screen.geometry() != geometry:
        raise ValueError('The selected display changed. Select the question area again.')
    pixmap = screen.grabWindow(0)
    if pixmap.isNull():
        raise ValueError('Windows could not read the selected display.')
    sx, sy = pixmap.width()/geometry.width(), pixmap.height()/geometry.height()
    crop = pixmap.copy(round(rect.x()*sx), round(rect.y()*sy), round(rect.width()*sx), round(rect.height()*sy))
    gray = crop.toImage().scaled(96, 64, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).convertToFormat(QImage.Format_Grayscale8)
    fingerprint = bytes(gray.constBits())[:gray.sizeInBytes()]
    return crop, fingerprint


class StableQuestion:
    """Local debounce and duplicate suppression; no network or screen access."""
    def __init__(self):
        self.candidate = self.submitted = None
        self.since = 0
        self.last_request = -100
        self.seen_frames = []

    @staticmethod
    def different(a, b):
        if a is None or b is None or len(a) != len(b):
            return True
        differences = [abs(x-y) for x,y in zip(a,b)]
        return sum(differences)/len(a) > 1.5 or sum(d >= 24 for d in differences)/len(a) > .015

    def observe(self, fingerprint, now):
        if self.different(fingerprint, self.candidate):
            self.candidate, self.since = fingerprint, now
            return False
        return (now-self.since >= 1 and now-self.last_request >= 12 and
                self.different(fingerprint, self.submitted) and
                all(self.different(fingerprint, previous) for previous in self.seen_frames))

    def submitted_now(self, fingerprint, now):
        self.submitted, self.last_request = fingerprint, now
        self.seen_frames.append(fingerprint)
        self.seen_frames = self.seen_frames[-80:]


def parse_question(text):
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip(), flags=re.I)
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get('question'), str) or len(data['question'].strip()) < 8:
        return None
    if data.get('details') is None:
        data['details'] = ''
    if data.get('options') is None:
        data['options'] = []
    if not isinstance(data.get('options', []), list) or not all(isinstance(x, str) for x in data.get('options', [])):
        return None
    if not isinstance(data.get('details', ''), str):
        return None
    data = {'question': data['question'].strip(), 'options': data.get('options', []), 'details': data.get('details', '')}
    encoded = json.dumps(data, ensure_ascii=False)
    return encoded if len(encoded.encode('utf-8')) <= 24000 else None


def question_key(text):
    data = json.loads(text)
    stem = re.sub(r'^question\s*\d+\s*(?:of\s*\d+)?\s*[:.)-]?\s*', '', data['question'], flags=re.I)
    return ' '.join(unicodedata.normalize('NFKC', stem + ' ' + ' '.join(data['options']) + ' ' + data['details']).casefold().split())


def question_seen(key, previous):
    numbers = re.findall(r'\d+(?:\.\d+)?', key)
    return any(key == item or (numbers == re.findall(r'\d+(?:\.\d+)?', item) and
               SequenceMatcher(None, key, item, autojunk=False).ratio() >= .97) for item in previous)


class MockJob(CloudJob):
    def __init__(self, image, language, question_type, seen_questions=()):
        super().__init__('', '', '', {}, question='Mock solution')
        self.image, self.language, self.question_type = image, language, question_type
        self.seen_questions = tuple(seen_questions)
        self.question_key = None
        self.coding_answer = True

    def run(self):
        try:
            if not managed_ai.enabled():
                raise ValueError('Mock screen questions currently require a signed-in ReplyCue account.')
            result = managed_ai.call({'kind': 'mock-inspect', 'image': self.image,
                'language': self.language, 'questionType': self.question_type},
                on_update=lambda text: None, interrupted=self.isInterruptionRequested)
            self.image = None
            extracted = parse_question(result.get('text', ''))
            if self.isInterruptionRequested():
                return
            if not extracted:
                self.final_answer = 'NO_QUESTION'
                return
            key = question_key(extracted)
            if question_seen(key, self.seen_questions):
                self.final_answer = 'NO_QUESTION'
                return
            result = managed_ai.call({'kind': 'mock-solution', 'question': extracted, 'language': self.language},
                on_update=lambda text: self.answer.emit(text) if not self.isInterruptionRequested() else None,
                interrupted=self.isInterruptionRequested)
            if not self.isInterruptionRequested():
                self.final_answer = result['text'].strip()
                if self.final_answer and self.final_answer != 'NO_QUESTION':
                    self.question_key = key
                    self.answer.emit(self.final_answer)
                elif not self.final_answer:
                    raise ValueError('No solution was returned. Try a clearer question area.')
        except (managed_ai.ManagedError, ValueError) as error:
            self.problem.emit(str(error))
        except Exception:
            self.problem.emit('Mock question analysis failed. Check your connection and try again.')
        finally:
            self.image = None
