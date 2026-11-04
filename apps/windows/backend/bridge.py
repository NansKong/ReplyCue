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
    def __init__(self, qt, studio):
        super().__init__()
        self.qt, self.studio, self.last = qt, studio, ''
        self.sources = []
        self.incoming.connect(self.dispatch)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.publish)
        self.timer.start(300)
    def snapshot(self):
        s = self.studio
        key, model, stt, groq = settings.configuration()
        placeholders = {'paste_your_token_here', 'your_token_here', 'your_replicate_token', 'your_groq_key'}
        return {'live': s.live, 'paused': s.paused, 'busy': bool(s.workers()),
                'status': s.status.text().replace('E:\\teleprompter\\.env', str(settings.ENV_PATH)),
                'records': s.qa_records, 'transcript': s.transcript_view.toPlainText(),
                'managed': managed_ai.enabled(), 'remainingMicroUsd': managed_ai.remaining,
                'trialLimitMicroUsd': managed_ai.trial_limit, 'minimumTurnMicroUsd': managed_ai.minimum_turn,
                'aiAvailable': managed_ai.ai_available,
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
    def shutdown(self):
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
                if s.live:
                    raise ValueError('End the session before changing accounts.')
                if action == 'managed-sign-in':
                    managed_ai.connect(data.get('idToken'), data.get('refreshToken'))
                else:
                    managed_ai.disconnect()
                result = self.snapshot()
            elif action == 'sources':
                if s.live:
                    raise ValueError('End the session before refreshing playback devices.')
                self.sources = playback_sources()
                result = self.snapshot()
            elif action == 'start':
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
                s.toggle_listen()
                result = self.snapshot()
            elif action == 'pause':
                s.pause_session()
            elif action == 'end':
                s.stop_live()
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
        emit({'audio_buffer_check': 'passed'})
        return 0
    settings.ENV_PATH = Path(args.config).resolve()
    if getattr(sys, 'frozen', False):
        managed_ai.load(Path(sys.executable).resolve().parents[1] / 'ui' / 'managed-config.json')
    else:
        managed_ai.load(Path(__file__).resolve().parents[2] / 'website' / 'public' / 'managed-config.json')
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
    bridge.publish()
    return qt.exec()

if __name__ == '__main__':
    sys.exit(main())
