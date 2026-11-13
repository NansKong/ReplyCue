"""Windows live interview copilot: setup, playback transcription and answer overlay."""
import ctypes
import time
import os
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QPoint, QRect, QPropertyAnimation, QEasingCurve, QTimer, Signal, QEvent, QSettings
from PySide6.QtGui import QColor, QPainter, QPen, QLinearGradient, QFont
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QSlider, QMainWindow, QFileDialog, QTabWidget, QLineEdit, QCheckBox, QSpinBox, QFrame, QButtonGroup)
from knowledge import extract, retrieve
from turn_detection import required_silence
import re
from cloud import AudioCapture, CloudJob, TranscriptionJob
from settings import configuration
import managed_ai

READ_START_DELAY = 7.0


def trim_transcript_overlap(previous, current):
    before, after = previous.split(), current.split()
    normalize = lambda word: word.casefold().strip('.,!?;:')
    for count in range(min(8, len(before), len(after)), 0, -1):
        if list(map(normalize, before[-count:])) == list(map(normalize, after[:count])):
            return ' '.join(after[count:])
    return current


class Prompter(QWidget):
    pauseRequested = Signal()
    stopRequested = Signal()
    setupRequested = Signal()
    historyRequested = Signal()
    def __init__(self, preferences=None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.expanded = False
        self.preferences = preferences if preferences is not None else QSettings('ReplyCue', 'Overlay')
        saved_position = self.preferences.value('position')
        self.anchor = saved_position if isinstance(saved_position, QPoint) else None
        self.drag_origin = None
        self.dragging = False
        self.drag_targets = ()
        self.protected = False
        self.closing = False
        self.history_mode = False
        self.live_text = ''
        self.live_question = ''
        self.history_text = ''
        self.live_scroll_position = 0
        self.setWindowTitle('Interview Copilot')
        self.body = QWidget(self)
        self.body.setObjectName('overlayBody')
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)
        self.header = QWidget(self.body)
        top = QHBoxLayout(self.header)
        top.setContentsMargins(0, 0, 0, 0)
        self.drag_handle = QLabel('⠿')
        self.drag_handle.setFixedSize(26, 26)
        self.drag_handle.setAlignment(Qt.AlignCenter)
        self.drag_handle.setAccessibleName('Move overlay')
        self.drag_handle.setToolTip('Drag to move the overlay')
        top.addWidget(self.drag_handle)
        brand = QPushButton('History')
        brand.setToolTip('Browse all questions and suggested answers in this session')
        brand.clicked.connect(self.historyRequested.emit)
        self.history_button = brand
        brand.setObjectName('brand')
        top.addWidget(brand)
        top.addStretch()
        self.auto_read = QCheckBox('Auto')
        self.auto_read.setChecked(True)
        self.auto_read.setToolTip('Automatically scroll the answer at your reading pace')
        top.addWidget(self.auto_read)
        self.read_pace = QSpinBox()
        self.read_pace.setRange(80, 260)
        self.read_pace.setValue(160)
        self.read_pace.setSingleStep(10)
        self.read_pace.setSuffix(' wpm')
        self.read_pace.setFixedWidth(88)
        self.read_pace.setAlignment(Qt.AlignCenter)
        self.read_pace.setAccessibleName('Automatic reading speed')
        self.read_pace.setToolTip('Reading pace in words per minute')
        top.addWidget(self.read_pace)
        self.mode = QLabel('LISTENING')
        self.mode.setObjectName('muted')
        top.addWidget(self.mode)
        self.fold = QPushButton('⌃')
        self.fold.setFixedSize(28, 26)
        self.fold.setStyleSheet('padding: 0; font-size: 16px;')
        self.fold.clicked.connect(self.toggle)
        self.fold.setToolTip('Collapse · Shift+N')
        self.fold.setAccessibleName('Collapse overlay (Shift+N)')
        top.addWidget(self.fold)
        layout.addWidget(self.header)
        self.question = QLabel('Waiting for the interviewer’s question…')
        self.question.setWordWrap(True)
        self.question.setObjectName('question')
        self.question.setMaximumHeight(38)
        self.question.setToolTip('Detected question')
        layout.addWidget(self.question)
        self.reader = QTextEdit()
        self.reader.setReadOnly(True)
        self.reader.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.reader.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.reader, 1)
        controls = QHBoxLayout()
        self.pause_button = QPushButton('Pause')
        self.pause_button.setToolTip('Pause meeting capture and automatic answers')
        self.pause_button.clicked.connect(self.pauseRequested.emit)
        controls.addWidget(self.pause_button)
        setup = QPushButton('Setup')
        setup.setToolTip('Pause and return to session setup')
        setup.clicked.connect(self.setupRequested.emit)
        controls.addWidget(setup)
        end = QPushButton('End')
        end.setObjectName('endSession')
        end.setToolTip('End this session and return to setup')
        end.clicked.connect(self.stopRequested.emit)
        controls.addWidget(end)
        controls.addStretch()
        controls.addWidget(QLabel('Glass'))
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(35, 100)
        self.opacity.setValue(90)
        self.opacity.setFixedWidth(62)
        self.opacity.setAccessibleName('Panel opacity')
        self.opacity.setToolTip('Panel opacity — text stays clear')
        self.opacity.valueChanged.connect(lambda value: self.update())
        controls.addWidget(self.opacity)
        controls.addSpacing(8)
        controls.addWidget(QLabel('Aa'))
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(14, 34)
        self.font_slider.setSingleStep(1)
        self.font_slider.setPageStep(2)
        self.font_slider.setFixedWidth(84)
        self.font_slider.setAccessibleName('Answer text size')
        self.font_slider.setToolTip('Text size · drag for 1-pixel steps')
        self.font_slider.setValue(20)
        self.font_value = QLabel('20px')
        self.font_value.setFixedWidth(34)
        controls.addWidget(self.font_slider)
        controls.addWidget(self.font_value)
        self.font_slider.valueChanged.connect(self.set_font_size)
        layout.addLayout(controls)
        self.font_size = 20
        self.change_font(0)
        self.chip = QPushButton('●  Listening    ⌄', self)
        self.chip.setObjectName('chip')
        self.chip.clicked.connect(self.toggle)
        self.chip.setToolTip('Click or Shift+M to expand · Shift+N to collapse · Drag to move')
        self.animation = QPropertyAnimation(self, b'geometry', self)
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.finished.connect(self.finished)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.scroll)
        self.scroll_position = 0.0
        self.scroll_suspended = False
        self.read_after = 0.0
        self.last_scroll_time = time.monotonic()
        self.reader.viewport().installEventFilter(self)
        self.reader.verticalScrollBar().sliderPressed.connect(self.manual_scroll)
        self.reader.verticalScrollBar().sliderReleased.connect(self.manual_scroll)
        self.body.hide()
        self.setGeometry(self.target(False))
        self.drag_targets = (self.chip, self.drag_handle)
        for widget in self.findChildren(QWidget):
            widget.installEventFilter(self)
        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.PointingHandCursor)
        self.header.setCursor(Qt.ArrowCursor)
        self.auto_read.setCursor(Qt.PointingHandCursor)
        self.read_pace.setCursor(Qt.ArrowCursor)
        for widget in self.drag_targets:
            widget.setCursor(Qt.OpenHandCursor)

    def target(self, expanded):
        screen = QApplication.screenAt(self.anchor) if self.anchor is not None else self.screen()
        screen = (screen or QApplication.primaryScreen()).availableGeometry()
        width = min(560 if expanded else 240, screen.width()-24)
        height = min(270, screen.height()-32) if expanded else 38
        anchor = self.anchor or QPoint(screen.x()+screen.width()//2, screen.y()+10)
        x = max(screen.left()+8, min(anchor.x()-width//2, screen.right()-width-7))
        y = max(screen.top()+8, min(anchor.y(), screen.bottom()-height-7))
        return QRect(x, y, width, height)

    def drag_to(self, position, pointer):
        screen = (QApplication.screenAt(pointer) or self.screen()).availableGeometry()
        x = max(screen.left()+8, min(position.x(), screen.right()-self.width()-7))
        y = max(screen.top()+8, min(position.y(), screen.bottom()-self.height()-7))
        self.move(x, y)
        self.anchor = QPoint(x+self.width()//2, y)

    def ensure_protection(self):
        if sys.platform != 'win32':
            return False
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user.GetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
        affinity = ctypes.c_uint()
        handle = int(self.winId())
        accepted = user.SetWindowDisplayAffinity(handle, 0x11)
        readback = user.GetWindowDisplayAffinity(handle, ctypes.byref(affinity))
        self.protected = bool(accepted and readback and affinity.value == 0x11)
        return self.protected

    def reveal(self, text):
        if not self.ensure_protection():
            return False
        self.live_text = text
        if self.history_mode:
            return True
        self.live_question = self.question.text()
        old = self.reader.toPlainText()
        new_answer = not old or not text.startswith(old)
        if new_answer:
            self.read_after = time.monotonic() + READ_START_DELAY
            self.scroll_position = 0.0
        position = self.reader.verticalScrollBar().value()
        if text.startswith(old) and old:
            cursor = self.reader.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(text[len(old):])
        else:
            self.reader.setPlainText(text)
        self.reader.verticalScrollBar().setValue(0 if new_answer else position)
        self.show()
        if not self.expanded:
            self.set_expanded(True)
        elif not self.timer.isActive():
            self.last_scroll_time = time.monotonic()
            self.timer.start()
        return True

    def toggle(self):
        self.set_expanded(not self.expanded)

    def set_expanded(self, expanded):
        if self.expanded == expanded:
            return
        self.animation.stop()
        self.expanded = expanded
        self.timer.stop()

        self.chip.hide()
        # Reveal text only after expansion completes, avoiding clipped text while morphing.
        self.body.hide()
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(self.target(self.expanded))
        self.animation.start()

    def finished(self):
        self.body.setVisible(self.expanded)
        self.chip.setVisible(not self.expanded)
        if self.expanded:
            self.last_scroll_time = time.monotonic()
            if self.live_text and not self.history_mode and self.reader.verticalScrollBar().value() == 0:
                self.read_after = self.last_scroll_time + READ_START_DELAY
            self.timer.start()

    def resizeEvent(self, event):
        self.body.setGeometry(self.rect())
        self.chip.setGeometry(self.rect())
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bounds = self.rect().adjusted(1, 1, -1, -1)
        fill = QLinearGradient(0, 0, 0, self.height())
        fill.setColorAt(0, QColor(35, 39, 44, round(self.opacity.value()*2.55)))
        fill.setColorAt(1, QColor(19, 23, 27, round(self.opacity.value()*2.45)))
        p.setBrush(fill)
        p.setPen(QPen(QColor(220, 237, 235, 48), 1))
        p.drawRoundedRect(bounds, 20, 20)
        p.setPen(QPen(QColor(233, 255, 249, 28), 1))
        p.drawLine(26, 2, self.width()-26, 2)

    def update_history(self, text):
        self.history_text = text
        if self.history_mode:
            position = self.reader.verticalScrollBar().value()
            self.reader.setPlainText(text or 'No questions yet. Start a session and ask a question.')
            self.reader.verticalScrollBar().setValue(position)

    def toggle_history(self):
        if not self.ensure_protection():
            return
        self.history_mode = not self.history_mode
        self.history_button.setText('Live' if self.history_mode else 'History')
        self.auto_read.setEnabled(not self.history_mode)
        self.read_pace.setEnabled(not self.history_mode)
        if self.history_mode:
            self.live_scroll_position = self.reader.verticalScrollBar().value()
            self.question.setText('Session history · suggested answers, not spoken responses')
            self.reader.setPlainText(self.history_text or 'No questions yet. Start a session and ask a question.')
            self.reader.verticalScrollBar().setValue(self.reader.verticalScrollBar().maximum())
        else:
            self.question.setText(self.live_question or 'Waiting for the interviewer’s question…')
            self.reader.setPlainText(self.live_text)
            self.reader.verticalScrollBar().setValue(self.live_scroll_position)
            delay = READ_START_DELAY if self.live_scroll_position == 0 else 1.0
            self.read_after = time.monotonic() + delay
            self.scroll_position = float(self.reader.verticalScrollBar().value())
        self.show()
        if not self.expanded:
            self.toggle()

    def manual_scroll(self):
        self.read_after = max(self.read_after, time.monotonic()+4.0)

    def eventFilter(self, watched, event):
        kind = event.type()
        if (kind == QEvent.MouseButtonPress and event.button() == Qt.LeftButton
                and watched in self.drag_targets):
            self.drag_origin = (event.globalPosition().toPoint(), self.pos())
            self.dragging = False
        if watched in self.drag_targets and self.drag_origin is not None:
            pointer, origin = self.drag_origin
            if kind == QEvent.MouseMove and event.buttons() & Qt.LeftButton:
                delta = event.globalPosition().toPoint() - pointer
                if self.dragging or delta.manhattanLength() >= QApplication.startDragDistance():
                    self.animation.stop()
                    self.dragging = True
                    watched.setCursor(Qt.ClosedHandCursor)
                    self.chip.setDown(False)
                    self.drag_to(origin+delta, event.globalPosition().toPoint())
                    return True
            if kind == QEvent.MouseButtonRelease:
                dragged = self.dragging
                self.drag_origin = None
                self.dragging = False
                watched.setCursor(Qt.OpenHandCursor)
                if dragged:
                    self.chip.setDown(False)
                    self.preferences.setValue('position', self.anchor)
                    self.preferences.sync()
                    return True
        if watched is self.reader.viewport() and kind == QEvent.Wheel:
            self.manual_scroll()
        return super().eventFilter(watched, event)

    def scroll(self):
        now = time.monotonic()
        delta = min(0.1, now-self.last_scroll_time)
        self.last_scroll_time = now
        bar = self.reader.verticalScrollBar()
        if (not self.expanded or not self.body.isVisible() or self.scroll_suspended
                or self.history_mode or not self.auto_read.isChecked() or now < self.read_after or bar.isSliderDown()):
            self.scroll_position = float(bar.value())
            return
        words = max(1, len(self.reader.toPlainText().split()))
        pixels_per_word = self.reader.document().size().height()/words
        self.scroll_position = min(float(bar.maximum()), self.scroll_position + pixels_per_word*self.read_pace.value()/60*delta)
        bar.setValue(round(self.scroll_position))

    def set_font_size(self, value):
        position = self.reader.verticalScrollBar().value()
        self.font_size = max(14, min(34, int(value)))
        self.font_value.setText(f'{self.font_size}px')
        if self.font_slider.value() != self.font_size:
            self.font_slider.setValue(self.font_size)
            return
        self.reader.setStyleSheet(f'QTextEdit {{ background: transparent; border: none; padding: 0; font-size: {self.font_size}px; }}')
        font = QFont('Segoe UI')
        font.setPixelSize(self.font_size)
        self.reader.setFont(font)
        self.reader.document().setDefaultFont(font)
        self.reader.verticalScrollBar().setValue(position)

    def change_font(self, delta):
        self.set_font_size(self.font_size + delta)

    def set_state(self, text):
        self.mode.setText(text.upper())
        self.chip.setText('●  '+text+'    ⌄')

    def show_idle(self):
        self.animation.stop()
        self.expanded = False
        self.setGeometry(self.target(False))
        self.finished()
        self.show()

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.ShiftModifier and event.key() in (Qt.Key_M, Qt.Key_N):
            self.set_expanded(event.key() == Qt.Key_M)
        elif event.key() == Qt.Key_Escape and self.expanded:
            self.set_expanded(False)
        else:
            super().keyPressEvent(event)


class Studio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Interview Copilot · Session setup')
        self.resize(980, 740)
        self.setMinimumSize(860, 660)
        self.panel = Prompter()
        self.capture = self.stt_job = self.job = None
        self.retired = []
        self.live = False
        self.paused = False
        self.trial_timer = QTimer(self)
        self.trial_timer.timeout.connect(self.check_trial)
        self.trial_timer.start(500)
        self.audio_device_index = None
        self.audio_level = 0
        self.audio_status = 'Choose the same playback device as your meeting.'
        self.history, self.audio_queue, self.fragments = [], [], []
        self.performance = {}
        self.pending_questions = []
        self.session_memory = []
        self.qa_records = []
        self.turn_timer = QTimer(self)
        self.turn_timer.setSingleShot(True)
        self.turn_timer.setInterval(650)
        self.turn_timer.timeout.connect(self.finish_turn)
        self.speech_active = False
        self.reader_worker = None
        self.performance = {}
        self.last_speech_at = None
        self.reader_queue = []
        self.reader_hold = QTimer(self)
        self.reader_hold.setSingleShot(True)
        self.reader_hold.timeout.connect(self.show_next_answer)
        self.panel.pauseRequested.connect(self.pause_session)
        self.panel.stopRequested.connect(self.stop_live)
        self.panel.setupRequested.connect(self.open_setup)
        self.panel.historyRequested.connect(self.panel.toggle_history)
        root = QWidget()
        root.setObjectName('appShell')
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(192)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 26, 16, 22)
        side.setSpacing(8)
        wordmark = QLabel('◉  copilot')
        wordmark.setObjectName('wordmark')
        side.addWidget(wordmark)
        edition = QLabel('INTERVIEW WORKSPACE')
        edition.setObjectName('eyebrow')
        side.addWidget(edition)
        side.addSpacing(34)
        nav_title = QLabel('YOUR SESSION')
        nav_title.setObjectName('eyebrow')
        side.addWidget(nav_title)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = []
        for label in ['Your background', 'The role', 'Transcript', 'Q&&A history']:
            button = QPushButton(label)
            button.setObjectName('navigation')
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            self.nav_group.addButton(button)
            self.nav_buttons.append(button)
            side.addWidget(button)
        side.addStretch()
        side_note = QLabel('STAY PRESENT\n\nListen first.\nLet the context help.\nAnswer in your own voice.')
        side_note.setObjectName('sideNote')
        side_note.setWordWrap(True)
        side.addWidget(side_note)
        side.addSpacing(16)
        preview = QLabel('●  Windows preview')
        preview.setObjectName('previewBadge')
        side.addWidget(preview)
        shell.addWidget(sidebar)
        workspace = QWidget()
        workspace.setObjectName('workspace')
        shell.addWidget(workspace, 1)
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(32, 30, 32, 24)
        layout.setSpacing(14)
        eyebrow = QLabel('PREPARE YOUR SESSION')
        eyebrow.setObjectName('muted')
        layout.addWidget(eyebrow)
        title = QLabel('Ready for the conversation.')
        title.setObjectName('title')
        layout.addWidget(title)
        description = QLabel('Bring your experience and the role together. Your assistant will follow the conversation, one question at a time.')
        description.setWordWrap(True)
        layout.addWidget(description)
        self.tabs = QTabWidget()
        self.resume, self.jd, self.transcript_view = QTextEdit(), QTextEdit(), QTextEdit()
        self.resume.setPlaceholderText('Your experience, in your words.\n\nPaste your resume here, or import a document below. Review the extracted text before starting.')
        self.jd.setPlaceholderText('What does this role call for?\n\nPaste or import the job description. Your experience and the role’s requirements stay separate.')
        self.transcript_view.setReadOnly(True)
        self.transcript_view.setPlaceholderText('Heard meeting turns appear here during the session. Nothing is saved automatically.')
        for widget, label in [(self.resume, 'Your background'), (self.jd, 'The role'), (self.transcript_view, 'Session transcript')]:
            self.tabs.addTab(widget, label)
        self.qa_view = QTextEdit()
        self.qa_view.setReadOnly(True)
        self.qa_view.setPlaceholderText('Questions and suggested answers stay here for this session. Scroll up to revisit earlier exchanges.')
        self.tabs.addTab(self.qa_view, 'Q&A history')
        self.tabs.tabBar().hide()
        for index, button in enumerate(self.nav_buttons):
            button.clicked.connect(lambda checked=False, i=index: self.tabs.setCurrentIndex(i))
        self.tabs.currentChanged.connect(lambda i: self.nav_buttons[i].setChecked(True))
        self.nav_buttons[0].setChecked(True)
        layout.addWidget(self.tabs, 1)
        imports = QHBoxLayout()
        for label, kind in [('Import resume', 'Resume'), ('Import job description', 'Job description')]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, k=kind: self.import_document(k))
            imports.addWidget(button)
        imports.addStretch()
        layout.addLayout(imports)
        provider = QLabel('TXT, DOCX & text PDF  ·  Review imported text before your session')
        provider.setObjectName('muted')
        layout.addWidget(provider)
        self.consent = QCheckBox('Allow cloud processing for this session')
        self.consent.setToolTip('Playback audio goes to Groq; interview context goes to Replicate/Gemini. Provider limits and charges apply.')
        self.consent.toggled.connect(lambda enabled: None if enabled else self.stop_live())
        layout.addWidget(self.consent)
        privacy = QLabel('Audio → Groq  ·  Context → Replicate / Gemini  ·  Provider limits and charges apply')
        privacy.setObjectName('privacyNote')
        privacy.setWordWrap(True)
        layout.addWidget(privacy)
        self.listen = QPushButton('Start session  ↗')
        self.listen.setObjectName('primary')
        self.listen.clicked.connect(self.toggle_listen)
        layout.addWidget(self.listen)
        self.status = QLabel('Ready for setup. Whole-device playback is captured, including other apps.\nScreen-sharing compatibility will be tested separately.')
        self.status.setWordWrap(True)
        self.status.setObjectName('statusMessage')
        layout.addWidget(self.status)
        for button in self.findChildren(QPushButton):
            button.setCursor(Qt.PointingHandCursor)

    def state(self, label):
        self.panel.set_state(label)
        self.status.setText(label)

    def ready(self):
        try:
            key, model, stt, groq = configuration()
        except Exception:
            self.status.setText('Could not read E:\\teleprompter\\.env. Check that it is a UTF-8 text file.')
            return False
        placeholders = {'paste_your_token_here', 'your_token_here', 'your_replicate_token', 'your_groq_key'}
        missing = []
        if not key or key in placeholders:
            missing.append('REPLICATE_API_TOKEN')
        if not groq or groq in placeholders:
            missing.append('GROQ_API_KEY')
        if managed_ai.enabled() and not managed_ai.connected():
            self.status.setText("Sign in to your ReplyCue account first.")
            return False
        if missing and not managed_ai.enabled():
            self.status.setText('Missing '+', '.join(missing)+' in E:\\teleprompter\\.env. Save the file and click Start session again; no restart needed.')
            return False
        if not self.consent.isChecked():
            self.status.setText('Both API keys are loaded. Tick the cloud-processing checkbox above Start session, then click Start session again.')
            self.consent.setFocus()
            return False
        if not managed_ai.enabled() and (not model or not stt):
            self.status.setText('An answer or transcription model is missing in .env.')
            return False
        if not self.panel.ensure_protection():
            self.status.setText('Windows could not initialize the overlay. This is unrelated to your API keys.')
            return False
        return True

    def workers(self):
        return [w for w in [self.capture, self.stt_job, self.job]+self.retired if w and w.isRunning()]

    def toggle_listen(self, mock=False):
        if self.live:
            self.stop_live()
            return
        if self.workers():
            self.status.setText('Previous session is stopping. Try again shortly.')
            return
        if not self.ready():
            return
        try:
            managed_ai.begin_session()
        except managed_ai.ManagedError as error:
            self.status.setText(str(error))
            return
        self.live, self.paused = True, False
        self.mock_mode = mock
        self.history, self.audio_queue, self.fragments = [], [], []
        self.pending_questions = []
        self.session_memory = []
        self.qa_records = []
        self.transcript_view.clear()
        self.qa_view.clear()
        self.panel.history_mode = False
        self.panel.history_button.setText('History')
        self.panel.auto_read.setEnabled(True)
        self.panel.read_pace.setEnabled(True)
        self.panel.live_text = ''
        self.panel.live_question = ''
        self.panel.update_history('')
        self.documents = {'Resume': self.resume.toPlainText(), 'Job description': self.jd.toPlainText()}
        self.panel.scroll_suspended = False
        self.panel.reader.clear()
        self.panel.question.setText('Waiting for the interviewer’s question…')
        self.panel.pause_button.setText('Pause')
        self.panel.show_idle()
        self.state('Listening')
        self.listen.setText('End session')
        if not self.mock_mode:
            self.start_capture()
        else:
            self.state('Mock assessment ready')
            self.panel.question.setText('Capture a mock question from the workspace.')
        self.hide()

    def start_capture(self):
        self.audio_level = 0
        self.last_speech_at = None
        self.capture = AudioCapture(self.audio_device_index)
        self.speech_active = False
        self.capture.turn.connect(self.audio_turn)
        self.capture.speaking.connect(self.speech_changed)
        self.capture.silence.connect(self.capture_silence)
        self.capture.state.connect(self.capture_status)
        self.capture.level.connect(self.capture_level)
        self.capture.problem.connect(self.cloud_problem)
        self.capture.finished.connect(self.capture_finished)
        self.capture.start()

    def capture_silence(self, seconds):
        if self.sender() is self.capture and self.live and not self.paused:
            self.last_speech_at = time.monotonic() - seconds

    def speech_changed(self, active):
        if self.sender() is not self.capture or not self.live or self.paused:
            return
        self.speech_active = active
        if active:
            self.last_speech_at = time.monotonic()
            self.turn_timer.stop()
        else:
            self.process_audio()

    def capture_level(self, value):
        if self.sender() is self.capture:
            self.audio_level = value

    def capture_status(self, message):
        if self.sender() is not self.capture or not self.live or self.paused:
            return
        self.audio_status = message
        if not self.panel.live_text and not self.panel.history_mode:
            self.panel.question.setText(message)
            self.panel.question.setToolTip(message)
        if not (self.stt_job and self.stt_job.isRunning()) and not (self.job and self.job.isRunning()):
            self.status.setText(message)
            if not self.panel.live_text:
                quiet = message.startswith(('No playback', 'No speech'))
                self.panel.mode.setText('NO SPEECH' if quiet else 'LISTENING')
                self.panel.chip.setText('●  Waiting for speech    ⌄' if quiet else '●  Listening    ⌄')

    def capture_finished(self):
        if self.live and not self.paused:
            self.cloud_problem('Playback capture ended. Check the audio device and restart the session.')

    def check_trial(self):
        if not self.live or self.paused or not managed_ai.enabled():
            return
        issue = managed_ai.session_issue()
        if managed_ai.remaining_trial_ms() == 0:
            issue = 'Your one-hour trial has ended. View plan options in your ReplyCue profile.'
        if issue:
            self.pause_session()
            self.state(issue)

    def pause_session(self):
        if not self.live:
            return
        if self.paused:
            if self.workers():
                self.state('Finishing paused requests…')
                return
            try:
                managed_ai.begin_session()
            except managed_ai.ManagedError as error:
                self.state(str(error))
                return
            self.paused = False
            self.panel.scroll_suspended = False
            self.panel.last_scroll_time = time.monotonic()
            self.panel.pause_button.setText('Pause')
            self.state('Listening')
            if self.panel.expanded:
                self.panel.timer.start()
            if not getattr(self, 'mock_mode', False):
                self.start_capture()
            else:
                self.state('Mock assessment ready')
        else:
            self.paused = True
            self.cancel_pending()
            self.panel.pause_button.setText('Resume')
            self.state('Paused')
            managed_ai.end_session()

    def cancel_pending(self):
        self.panel.scroll_suspended = True
        self.panel.timer.stop()
        self.turn_timer.stop()
        self.reader_hold.stop()
        self.reader_queue.clear()
        self.reader_worker = None
        self.audio_queue.clear()
        self.fragments.clear()
        self.pending_questions = []
        for worker in self.workers():
            worker.requestInterruption()

    def stop_live(self):
        managed_ai.end_session()
        self.live = False
        self.paused = False
        self.mock_mode = False
        self.cancel_pending()
        self.listen.setText('Start session  ↗')
        self.panel.hide()
        self.show()
        self.state('Session ended')

    def open_setup(self):
        if self.live and not self.paused:
            self.pause_session()
        self.show()
        self.raise_()
        self.activateWindow()

    def cloud_problem(self, message):
        sender = self.sender()
        if sender and hasattr(sender, 'isInterruptionRequested') and sender.isInterruptionRequested():
            return
        self.stop_live()
        self.status.setText(message)

    def audio_turn(self, audio):
        if not self.live or self.paused:
            return
        if len(self.audio_queue) >= 8:
            self.cloud_problem('Transcription is falling behind. Session stopped without silently dropping questions. Check connection and restart.')
            return
        self.turn_timer.stop()
        self.audio_queue.append(audio)
        self.process_audio()

    def process_audio(self):
        if not self.live or self.paused or (self.stt_job and self.stt_job.isRunning()):
            return
        if not self.audio_queue:
            if self.fragments:
                if self.speech_active:
                    return
                self.finish_turn()
            elif not (self.job and self.job.isRunning()):
                self.state('Listening')
            return
        _, _, model, key = configuration()
        self.stt_job = TranscriptionJob(self.audio_queue.pop(0), key, model)
        self.stt_job.transcript.connect(self.transcribed)
        self.stt_job.problem.connect(self.cloud_problem)
        self.stt_job.finished.connect(self.process_audio)
        self.stt_job.start()
        self.state('Understanding…')

    def transcribed(self, text):
        if not self.live or self.paused or self.sender().isInterruptionRequested():
            return
        if self.fragments:
            text = trim_transcript_overlap(self.fragments[-1], text)
        if not text.strip():
            return
        elapsed = getattr(self.sender(), 'elapsed_ms', None)
        if elapsed is not None:
            self.performance['transcription_ms'] = elapsed
        self.history.append(text)
        # Retain heard turns for the entire current session; older turns are retrieved on demand.
        self.transcript_view.insertPlainText(text+'\n\n')
        self.fragments.append(text)
        # Keep the current answer intact. New speech is buffered for the next turn.

    def finish_turn(self):
        if not self.live or self.paused or self.speech_active or not self.fragments:
            return
        if self.audio_queue or (self.stt_job and self.stt_job.isRunning()):
            return
        question = ' '.join(self.fragments)
        if self.last_speech_at is not None:
            delay = required_silence(question) - (time.monotonic() - self.last_speech_at)
            if delay > 0:
                self.turn_timer.start(max(10, round(delay * 1000)))
                return
        if self.last_speech_at is not None:
            self.performance['question_endpoint_ms'] = round((time.monotonic()-self.last_speech_at)*1000)
        self.fragments.clear()
        self.pending_questions.append(question)
        self.generate_pending()

    def generate_pending(self):
        if not self.live or self.paused or not self.pending_questions:
            return
        if self.job and self.job.isRunning():
            return
        question = self.pending_questions.pop(0)
        key, model, stt, groq = configuration()
        self.job = CloudJob(key, model, stt, self.documents, question=question, history=list(self.history), groq_key=groq, session_memory=list(self.session_memory))
        self.job.record_index = len(self.qa_records)
        self.qa_records.append({'question': question, 'answer': '', 'status': 'Generating'})
        self.refresh_qa()
        self.job.answer.connect(self.show_answer)
        self.job.problem.connect(self.answer_problem)
        self.job.finished.connect(self.answer_finished)
        self.job.start()
        self.state('Thinking…')

    def refresh_qa(self):
        text = '\n\n────────────────────\n\n'.join(
            f"QUESTION {i+1}\n{record['question']}\n\nSUGGESTED ANSWER · {record['status']}\n{record['answer'] or 'Waiting for an answer…'}"
            for i, record in enumerate(self.qa_records))
        bar = self.qa_view.verticalScrollBar()
        position = bar.value()
        at_bottom = position >= bar.maximum()-4
        self.qa_view.setPlainText(text)
        bar.setValue(bar.maximum() if at_bottom else position)
        self.panel.update_history(text)

    def record_answer(self, worker, text=None, status=None):
        index = getattr(worker, 'record_index', -1)
        if 0 <= index < len(self.qa_records):
            record = self.qa_records[index]
            if text is not None:
                record['answer'] = text
            if status:
                record['status'] = status
            self.refresh_qa()

    def answer_problem(self, message):
        sender = self.sender()
        if sender and sender.isInterruptionRequested():
            return
        if not self.live:
            return
        self.record_answer(sender, status='Error — '+message)
        managed_ai.end_session()
        self.paused = True
        self.cancel_pending()
        self.panel.pause_button.setText('Resume')
        self.state('Answer unavailable · paused')
        self.status.setText(message)
        if not self.panel.live_text:
            self.panel.reveal(message+'\n\nSession paused. Use Setup to check configuration, or Resume to try again.')

    def answer_finished(self):
        worker = self.sender()
        if worker:
            started = getattr(worker, 'started_at', None)
            if started is not None:
                self.performance['answer_complete_ms'] = round((time.monotonic()-started)*1000)
                if worker.first_text_at is not None:
                    self.performance['answer_first_text_ms'] = round((worker.first_text_at-started)*1000)
                if worker.first_display_at is not None:
                    self.performance['answer_first_display_ms'] = round((worker.first_display_at-started)*1000)
            final = getattr(worker, 'final_answer', '')
            if not worker.isInterruptionRequested() and final and final != 'NO_QUESTION':
                self.record_answer(worker, final, 'Complete')
                if self.live and not self.paused:
                    if getattr(self, 'mock_mode', False):
                        # A new on-screen mock question supersedes the previous solution.
                        self.reader_hold.stop()
                        self.reader_queue.clear()
                        self.reader_worker = None
                        self.panel.reader.clear()
                        self.panel.live_text = ''
                        self.panel.question.setText(worker.question)
                        self.panel.reveal(final)
                        self.hold_reader(final)
                    elif self.reader_worker is worker:
                        self.panel.reveal(final)
                        self.hold_reader(final)
                    else:
                        self.reader_queue.append((worker.question, final))
                    if not self.reader_hold.isActive():
                        self.show_next_answer()
            elif worker.isInterruptionRequested():
                self.record_answer(worker, status='Interrupted — partial suggestion')
            elif final == 'NO_QUESTION':
                self.record_answer(worker, 'No interview question detected in this turn.', 'Skipped')
        if worker and worker is self.job and not worker.isInterruptionRequested() and worker.final_answer and worker.final_answer != 'NO_QUESTION':
            self.session_memory.append({'question': worker.question, 'suggested_answer': worker.final_answer})
        if self.live and not self.paused:
            self.state('Mock assessment ready' if getattr(self, 'mock_mode', False) else 'Listening')
            self.generate_pending()

    def show_answer(self, text):
        if not self.live or self.paused or self.sender() is not self.job or self.sender().isInterruptionRequested():
            return
        self.record_answer(self.sender(), text, 'Generating')
        self.preview_answer(self.sender(), text)

    def preview_answer(self, worker, text):
        if getattr(worker, 'coding_answer', False):
            return
        if self.reader_worker is worker:
            if not self.panel.history_mode:
                self.panel.reveal(text)
            return
        if (self.panel.history_mode or self.reader_queue or self.reader_hold.isActive()
                or self.panel.reader.verticalScrollBar().isSliderDown()
                or (self.panel.live_text and time.monotonic() < self.panel.read_after)):
            return
        complete = list(re.finditer(r'[.!?](?=\s|$)', text))
        if not complete:
            return
        first_text = text[:complete[-1].end()]
        self.reader_worker = worker
        self.panel.live_text = ''
        self.panel.reader.clear()
        self.panel.live_question = worker.question[:140]
        self.panel.question.setText(self.panel.live_question)
        if not self.panel.reveal(first_text):
            self.cloud_problem('Answer panel unavailable. Session stopped.')
            return
        worker.first_display_at = time.monotonic()
        self.hold_reader(first_text)

    def hold_reader(self, text):
        reading_seconds = READ_START_DELAY + 60 * len(text.split()) / self.panel.read_pace.value()
        self.reader_hold.start(round(1000 * max(4, min(45, reading_seconds))))

    def show_next_answer(self):
        if not self.live or self.paused or not self.reader_queue:
            return
        if self.panel.live_text and not self.panel.history_mode:
            remaining = self.panel.read_after - time.monotonic()
            if remaining > 0 or self.panel.reader.verticalScrollBar().isSliderDown():
                self.reader_hold.start(max(200, round(remaining * 1000)))
                return
        question, text = self.reader_queue.pop(0)
        self.panel.live_question = question[:140]
        self.panel.live_scroll_position = 0
        if not self.panel.history_mode:
            self.panel.reader.clear()
            self.panel.question.setText(self.panel.live_question)
        if not self.panel.reveal(text):
            self.cloud_problem('Answer panel unavailable. Session stopped.')
            return
        self.reader_worker = None
        self.hold_reader(text)

    def import_document(self, kind):
        filename, _ = QFileDialog.getOpenFileName(self, 'Import '+kind, '', 'Documents (*.txt *.pdf *.docx)')
        if filename:
            try:
                target = self.resume if kind == 'Resume' else self.jd
                target.setPlainText(extract(filename))
                self.tabs.setCurrentWidget(target)
                self.status.setText('Review extracted text. Changes apply to the next session.')
            except Exception as error:
                self.status.setText('Import failed: '+str(error))

    def closeEvent(self, event):
        managed_ai.end_session()
        if self.workers():
            self.live = False
            self.cancel_pending()
            event.ignore()
            self.status.setText('Stopping background work before closing…')
            QTimer.singleShot(250, self.close)
            return
        self.panel.timer.stop()
        self.panel.close()
        super().closeEvent(event)


from ui_theme import STYLE


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    studio = Studio()
    studio.panel.change_font(0)
    if '--check' in sys.argv:
        assert studio.panel.ensure_protection(), 'Capture exclusion unavailable'
        studio.panel.setGeometry(studio.panel.target(True))
        studio.panel.reader.setPlainText('A clearer thought. A calmer delivery.')
        studio.panel.expanded = True
        studio.panel.finished()
        app.processEvents()
        print('Qt initialized; native capture-exclusion readback passed.')
        studio.close()
    else:
        studio.show()
        sys.exit(app.exec())
