"""Desktop transport only. The existing engine and native reader remain unchanged."""
import argparse
import json
import sys
import threading
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'packages' / 'engine'))
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from dotenv import set_key
import settings
import managed_ai
from app import Studio, STYLE
from knowledge import extract
from audio_input import playback_sources
from account_store import AccountStore
from mock_assessment import MockJob, capture_region, LANGUAGES

def emit(value):
    print(json.dumps(value, ensure_ascii=True), flush=True)

class DesktopStudio(Studio):
    def show(self):
        emit({'event': 'show'})
    def hide(self):
        super().hide()
        emit({'event': 'hide'})
    def raise_(self):
        pass
    def activateWindow(self):
        pass

class Bridge(QObject):
    incoming = Signal(dict)
    restored = Signal(object)
    def __init__(self, qt, studio):
        super().__init__()
        self.qt, self.studio, self.last = qt, studio, ''
        self.sources = []
        self.restoring = False
        self.closing = False
        self.mock_image = None
        self.capturing_mock = False
        self.incoming.connect(self.dispatch)
        self.restored.connect(self.finish_restore)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.publish)
        self.timer.start(300)
    def saved_sign_in(self):
        return bool(managed_ai.account_store and managed_ai.account_store.path.is_file())

    def restore_sign_in(self):
        if self.closing or self.restoring or self.studio.live or managed_ai.connected() or not self.saved_sign_in():
            return
        self.restoring = True
        self.studio.status.setText('Restoring your ReplyCue sign-in…')
        self.publish()

        def restore():
            try:
                result = managed_ai.prepare_restore()
            except managed_ai.InvalidRefreshToken:
                result = 'expired'
            except Exception:
                result = None
            if not self.closing:
                self.restored.emit(result)

        threading.Thread(target=restore, daemon=True).start()

    def finish_restore(self, result):
        if self.closing:
            return
        self.restoring = False
        if result == 'expired':
            try:
                managed_ai.sign_out()
                self.studio.status.setText('Your saved session expired. Sign in again to continue.')
            except managed_ai.ManagedError as error:
                self.studio.status.setText(str(error))
        elif result is None:
            self.studio.status.setText('Could not restore sign-in. ReplyCue will retry shortly.')
        else:
            managed_ai.finish_restore(*result)
            self.studio.status.setText('Signed in. Ready when you are.')
        self.publish()

    def snapshot(self):
        s = self.studio
        key, model, stt, groq = settings.configuration()
        placeholders = {'paste_your_token_here', 'your_token_here', 'your_replicate_token', 'your_groq_key'}
        return {'mockMode': getattr(s, 'mock_mode', False), 'live': s.live, 'paused': s.paused, 'busy': bool(s.workers()),
                'status': s.status.text().replace('E:\\teleprompter\\.env', str(settings.ENV_PATH)),
                'records': s.qa_records, 'transcript': s.transcript_view.toPlainText(),
                'overlayVisible': s.panel.isVisible(), 'latencyMs': dict(s.performance),
                'restoringSignIn': self.restoring, 'savedSignIn': self.saved_sign_in(),
                'managed': managed_ai.enabled(), 'remainingMicroUsd': managed_ai.remaining,
                'trialLimitMicroUsd': managed_ai.trial_limit, 'minimumTurnMicroUsd': managed_ai.minimum_turn,
                'aiAvailable': managed_ai.ai_available, 'unlimited': managed_ai.unlimited,
                'remainingTrialMs': managed_ai.remaining_trial_ms(), 'trialLimitMs': managed_ai.trial_limit_ms,
                'configured': managed_ai.connected() if managed_ai.enabled() else bool(key and groq and key not in placeholders and groq not in placeholders),
                'replicateConfigured': bool(key and key not in placeholders),
                'groqConfigured': bool(groq and groq not in placeholders),
                'model': model, 'sttModel': stt, 'configPath': str(settings.ENV_PATH),
                'audioSources': self.sources, 'audioLevel': s.audio_level,
                'audioStatus': s.audio_status}
    def publish(self):
        value = self.snapshot()
        encoded = json.dumps(value)
        if encoded != self.last:
            self.last = encoded
            emit({'event': 'state', 'data': value})
    def capture_mock(self, ident):
        try:
            image = capture_region() if not self.closing else None
            s = self.studio
            self.mock_image = image if not self.closing and s.live and not s.paused and getattr(s, 'mock_mode', False) else None
            emit({'id': ident, 'result': {'image': self.mock_image}})
        except Exception:
            emit({'id': ident, 'error': 'Screen capture failed. Try another display or a smaller region.'})
        finally:
            self.capturing_mock = False
            if not self.closing:
                emit({'event': 'show'})
                self.publish()

    def shutdown(self):
        self.closing = True
        self.mock_image = None
        managed_ai.end_session()
        self.studio.live = False
        self.studio.cancel_pending()
        self.studio.panel.hide()
        if self.studio.workers():
            QTimer.singleShot(100, self.shutdown)
        else:
            self.studio.close()
            self.qt.quit()
    def dispatch(self, message):
        ident = message.get('id')
        try:
            action, data = message.get('action'), message.get('data') or {}
            s = self.studio
            result = None
            if action == 'state':
                result = self.snapshot()
            elif action in ('managed-sign-in', 'managed-sign-out'):
                if self.restoring:
                    raise ValueError('ReplyCue is restoring your sign-in. Try again shortly.')
                if s.live:
                    raise ValueError('End the session before changing accounts.')
                if action == 'managed-sign-in':
                    managed_ai.connect(data.get('idToken'), data.get('refreshToken'))
                    s.status.setText('Signed in. Ready when you are.')
                else:
                    managed_ai.sign_out()
                    s.status.setText('Signed out.')
                result = self.snapshot()
            elif action == 'sources':
                if s.live:
                    raise ValueError('End the session before refreshing playback devices.')
                self.sources = playback_sources()
                result = self.snapshot()
            elif action == 'mock-capture':
                if not s.live or s.paused or not getattr(s, 'mock_mode', False) or s.workers() or self.capturing_mock:
                    raise ValueError('Start or resume a mock session and wait for the current answer.')
                self.mock_image = None
                self.capturing_mock = True
                s.panel.hide()
                emit({'event': 'hide'})
                QTimer.singleShot(400, lambda: self.capture_mock(ident))
                return
            elif action == 'mock-discard':
                self.mock_image = None
            elif action == 'mock-solve':
                if not s.live or s.paused or not getattr(s, 'mock_mode', False) or s.workers() or not self.mock_image:
                    raise ValueError('Capture a question in an active mock session first.')
                language, kind = data.get('language'), data.get('questionType')
                if language not in LANGUAGES or kind not in ('auto', 'coding', 'mcq'):
                    raise ValueError('Choose a valid language and question type.')
                s.job = MockJob(self.mock_image, language, kind)
                self.mock_image = None
                s.job.record_index = len(s.qa_records)
                s.qa_records.append({'question': s.job.question, 'answer': '', 'status': 'Generating'})
                s.refresh_qa()
                s.job.answer.connect(s.show_answer)
                s.job.problem.connect(s.answer_problem)
                s.job.finished.connect(s.answer_finished)
                s.job.start()
                s.state('Reading mock question…')
                s.panel.show_idle()
                result = self.snapshot()
            elif action == 'start':
                if self.restoring:
                    raise ValueError('ReplyCue is restoring your sign-in. Try again shortly.')
                if s.live:
                    raise ValueError('End the current session before starting another.')
                source = data.get('audioSource', -1)
                if type(source) is not int or source < -1:
                    raise ValueError('Choose a valid playback device.')
                s.audio_device_index = None if source == -1 else source
                for field in ('resume', 'jd'):
                    value = data.get(field, '')
                    if not isinstance(value, str) or len(value) > 500000:
                        raise ValueError('Document text is too large.')
                    getattr(s, field).setPlainText(value)
                s.consent.setChecked(data.get('consent') is True)
                mode = data.get('mode', 'interview')
                if mode not in ('interview', 'mock'):
                    raise ValueError('Choose a valid session mode.')
                if mode == 'mock' and not managed_ai.enabled():
                    raise ValueError('Mock mode requires a ReplyCue account.')
                self.mock_image = None
                s.toggle_listen(mock=mode == 'mock')
                if mode == 'mock' and s.live:
                    s.panel.hide()
                    emit({'event': 'show'})
                result = self.snapshot()
            elif action == 'pause':
                s.pause_session()
            elif action == 'end':
                self.mock_image = None
                s.stop_live()
            elif action in ('overlay-expand', 'overlay-collapse'):
                if s.live and s.panel.isVisible():
                    s.panel.set_expanded(action == 'overlay-expand')
            elif action == 'overlay':
                if s.live:
                    s.panel.show()
                    emit({'event': 'hide'})
            elif action == 'import':
                file = Path(data['path'])
                if file.suffix.lower() not in ('.txt', '.pdf', '.docx'):
                    raise ValueError('Choose a TXT, PDF, or DOCX file.')
                result = extract(str(file))
            elif action == 'configure':
                if managed_ai.enabled():
                    raise ValueError('This build uses your ReplyCue account.')
                if s.live:
                    raise ValueError('End the session before updating keys.')
                settings.ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
                settings.ENV_PATH.touch(exist_ok=True)
                for field in ('GROQ_API_KEY', 'REPLICATE_API_TOKEN'):
                    value = data.get(field, '')
                    if not isinstance(value, str) or len(value) > 1024 or any(c in value for c in '\r\n\x00'):
                        raise ValueError('Invalid API key.')
                    if value.strip():
                        set_key(str(settings.ENV_PATH), field, value.strip())
                result = self.snapshot()
            elif action == 'quit':
                QTimer.singleShot(0, self.shutdown)
            else:
                raise ValueError('Unknown action.')
            emit({'id': ident, 'result': result})
            self.publish()
        except Exception as error:
            # Do not echo provider credentials or raw request payloads.
            emit({'id': ident, 'error': str(error) if isinstance(error, ValueError) else 'The action failed. Check the file and try again.'})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--account-store', type=Path)
    parser.add_argument('--audio-self-test', action='store_true')
    args = parser.parse_args()
    if args.audio_self_test:
        from audio_input import TurnBuffer
        import struct
        buffer = TurnBuffer(16000, 1)
        assert buffer.feed(struct.pack('<h', 100) * 8000, 1.0) is None
        output = buffer.idle(1.5)
        assert output and output.startswith(b'RIFF')
        assert buffer.idle(2.0) is None
        from noise_filter import SpeechCleaner
        with SpeechCleaner(48000, 1) as cleaner:
            frames = cleaner.feed(b'\0' * 9600)
        assert sum(len(pcm) for pcm, _ in frames) == 3200
        assert not any(speech for _, speech in frames)
        emit({'audio_buffer_check': 'passed', 'noise_filter_check': 'passed'})
        return 0
    settings.ENV_PATH = Path(args.config).resolve()
    if getattr(sys, 'frozen', False):
        managed_ai.load(Path(sys.executable).resolve().parents[1] / 'ui' / 'managed-config.json')
    else:
        managed_ai.load(Path(__file__).resolve().parents[2] / 'website' / 'public' / 'managed-config.json')
    if managed_ai.enabled() and args.account_store and sys.platform == 'win32':
        managed_ai.account_store = AccountStore(args.account_store)
    qt = QApplication(sys.argv)
    icon_root = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[3] / 'packages' / 'engine'
    qt.setWindowIcon(QIcon(str(icon_root / 'assets' / 'copilot.ico')))
    qt.setQuitOnLastWindowClosed(False)
    qt.setStyle('Fusion')
    qt.setStyleSheet(STYLE)
    studio = DesktopStudio()
    bridge = Bridge(qt, studio)
    def read():
        for line in sys.stdin:
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    bridge.incoming.emit(value)
            except (ValueError, TypeError):
                continue
        bridge.incoming.emit({'action': 'quit'})
    threading.Thread(target=read, daemon=True).start()
    if managed_ai.account_store:
        restore_timer = QTimer(bridge)
        restore_timer.timeout.connect(bridge.restore_sign_in)
        restore_timer.start(15000)
        bridge.restore_sign_in()
    bridge.publish()
    return qt.exec()

if __name__ == '__main__':
    sys.exit(main())
