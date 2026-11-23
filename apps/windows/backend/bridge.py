"""Desktop transport only. The existing engine and native reader remain unchanged."""
import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'packages' / 'engine'))
from PySide6.QtCore import QObject, Signal, QTimer, QThread
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from dotenv import set_key
import settings
import managed_ai
from app import Studio, STYLE
from knowledge import extract
from audio_input import playback_sources
from account_store import AccountStore
from github_projects import PublicGitHub, ProjectStore, GitHubError, GitHubAuthorizationError, GitHubAccount, plan_repositories, parse_target

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

class GitHubJob(QThread):
    completed = Signal(object)
    progress = Signal(object)
    def __init__(self, target, action, token=None, profile=None, previous=None, snapshots=None):
        super().__init__()
        self.target,self.action,self.token=target,action,token
        self.profile,self.previous,self.snapshots=profile,previous or [],snapshots or []
    def run(self):
        try:
            client=PublicGitHub(token=self.token)
            if self.action=='github-connect':
                self.completed.emit({'value':client.account()})
                return
            if self.action=='github-refresh':
                profile=client.account()
                if profile['id']!=self.profile['id']:raise GitHubError('GitHub account changed. Reconnect GitHub.')
                rows,truncated=client.my_repositories(profile['login'])
                catalog=plan_repositories(rows,self.previous)
                selected=[r for r in catalog if r['selected']]
                self.progress.emit({'catalog':catalog,'truncated':truncated,'message':f'Found {len(catalog)} public repositories. Preparing {len(selected)} projects…'})
                projects=[];failed=[];checked=0
                with ThreadPoolExecutor(max_workers=4) as pool:
                    def sync_project(name):return PublicGitHub(token=self.token).sync(name)
                    futures={pool.submit(sync_project,r['name']):r['name'] for r in selected}
                    for future in as_completed(futures):
                        name=futures[future]
                        try:projects.append(future.result())
                        except GitHubAuthorizationError:raise
                        except GitHubError:
                            failed.append(name)
                            old=next((p for p in self.snapshots if p['name']==name),None)
                            if old:projects.append(old)
                        if self.isInterruptionRequested():
                            for pending in futures:pending.cancel()
                            return
                        checked+=1
                        self.progress.emit({'message':f'Preparing project context · {checked} of {len(selected)} checked'})
                # Keep catalog order stable regardless of request completion order.
                projects.sort(key=lambda p:next(i for i,r in enumerate(catalog) if r['name']==p['name']))
                self.completed.emit({'value':{'catalog':catalog,'projects':projects,'truncated':truncated,'failed':failed}})
                return
            value=client.listing(self.target) if self.action=='github-list' else client.sync(self.target)
            self.completed.emit({'value':value})
        except GitHubError as error:
            self.completed.emit({'error':str(error)})
        except Exception:
            self.completed.emit({'error':'GitHub sync failed. Check your connection and try again.'})

class Bridge(QObject):
    incoming = Signal(dict)
    restored = Signal(object)
    def __init__(self, qt, studio, project_store=None, github_account=None):
        super().__init__()
        self.qt, self.studio, self.last = qt, studio, ''
        self.sources = []
        self.restoring = False
        self.closing = False
        self.projects = project_store or ProjectStore(settings.ENV_PATH.parent / 'github-projects.json')
        self.github_job = None
        self.github_request = None
        self.github_account = github_account or GitHubAccount()
        if self.github_account.profile and self.projects.owner!=self.github_account.profile['id']:
            self.projects.clear()
            self.projects.owner=self.github_account.profile['id']
            self.projects.save()
        self.github_status = ''
        self.github_next_refresh = False
        self.github_connect_token = None
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
        return {'githubConnected': bool(self.github_account.profile), 'githubLogin': (self.github_account.profile or {}).get('login',''), 'githubRepositories': self.projects.catalog if self.github_account.profile else [], 'githubStatus': self.github_status, 'githubTruncated': self.projects.truncated, 'githubProjects': self.projects.public(), 'githubBusy': bool(self.github_job and self.github_job.isRunning()), 'live': s.live, 'paused': s.paused, 'busy': bool(s.workers()),
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
    def launch_github(self, action, ident=None, target=''):
        self.github_request=(ident,action)
        self.github_job=GitHubJob(target,action,
            token=self.github_connect_token if action=='github-connect' else self.github_account.token,
            profile=self.github_account.profile,previous=list(self.projects.catalog),snapshots=list(self.projects.projects))
        self.github_job.completed.connect(self.finish_github)
        self.github_job.progress.connect(self.github_progress)
        self.github_job.finished.connect(self.github_finished)
        self.github_job.start()
        self.publish()

    def github_progress(self, progress):
        if self.closing:return
        self.github_status=progress['message']
        if 'catalog' in progress:
            self.projects.catalog=progress['catalog']
            self.projects.truncated=progress['truncated']
        self.publish()

    def github_finished(self):
        self.github_job.token=None
        self.publish()
        if self.github_next_refresh and not self.closing:
            self.github_next_refresh=False
            self.launch_github('github-refresh')

    def refresh_github(self):
        if self.closing or self.studio.live or not self.github_account.profile or (self.github_job and self.github_job.isRunning()):return
        self.github_status='Fetching your public repositories…'
        self.launch_github('github-refresh')

    def finish_github(self, result):
        if self.closing:return
        ident,action=self.github_request
        error=result.get('error')
        value=None
        try:
            if error:
                self.github_status=error
            elif action=='github-connect':
                profile=result['value']
                self.github_account.connect(self.github_connect_token,profile)
                if self.projects.owner!=profile['id']:self.projects.clear()
                self.projects.owner=profile['id']
                self.projects.save()
                self.github_next_refresh=True
                self.github_status='GitHub connected. Fetching your public repositories…'
                value=self.snapshot()
            elif action=='github-refresh':
                update=result['value']
                self.projects.catalog=update['catalog']
                self.projects.projects=update['projects']
                self.projects.truncated=update['truncated']
                self.projects.save()
                count=len(self.projects.projects)
                self.github_status=f'{len(self.projects.catalog)} public repositories found · {count} projects ready.'
                if update['failed']:self.github_status+=' Some project details could not refresh. Retry Sync projects.'
                value=self.snapshot()
            elif action=='github-sync':
                self.projects.put(result['value'])
                value=self.snapshot()
            else:value=result['value']
        except (ValueError,OSError):
            error='Could not save GitHub connection or projects securely. Check local storage and reconnect.'
            self.github_status=error
        finally:
            if action=='github-connect':self.github_connect_token=None
        if ident is not None:
            emit({'id':ident,**({'error':error} if error else {'result':value})})
        self.publish()

    def shutdown(self):
        self.closing = True
        managed_ai.end_session()
        self.studio.live = False
        self.studio.cancel_pending()
        self.studio.panel.hide()
        if self.github_job and self.github_job.isRunning():self.github_job.requestInterruption()
        if self.studio.workers() or (self.github_job and self.github_job.isRunning()):
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
                    if self.github_job and self.github_job.isRunning():raise ValueError('Wait for GitHub syncing before signing out.')
                    self.github_account.disconnect()
                    self.projects.clear()
                    self.github_status=''
                    managed_ai.sign_out()
                    s.status.setText('Signed out.')
                result = self.snapshot()
            elif action == 'sources':
                if s.live:
                    raise ValueError('End the session before refreshing playback devices.')
                self.sources = playback_sources()
                result = self.snapshot()
            elif action in ('github-connect','github-refresh','github-disconnect'):
                if s.live or (self.github_job and self.github_job.isRunning()):
                    raise ValueError('End the session and wait for syncing before changing GitHub.')
                if action=='github-connect':
                    token=data.get('githubToken')
                    GitHubAccount.validate_token(token)
                    self.github_connect_token=token
                    self.github_status='Verifying your GitHub account…'
                    self.launch_github(action,ident)
                    return
                if action=='github-disconnect':
                    self.github_account.disconnect()
                    self.projects.clear()
                    self.github_status='GitHub disconnected. Local project context cleared.'
                else:
                    if not self.github_account.profile:raise ValueError('Connect your GitHub account first.')
                    self.refresh_github()
                result=self.snapshot()
            elif action in ('github-list', 'github-sync'):
                if s.live or (self.github_job and self.github_job.isRunning()):
                    raise ValueError('End the session and wait for the current sync before updating projects.')
                target=data.get('target','')
                parse_target(target)
                self.github_request=(ident,action)
                self.github_job=GitHubJob(target,action)
                self.github_job.completed.connect(self.finish_github)
                self.github_job.finished.connect(self.publish)
                self.github_job.start()
                self.publish()
                return
            elif action in ('github-toggle','github-remove'):
                if s.live or (self.github_job and self.github_job.isRunning()):
                    raise ValueError('End the session before changing project context.')
                name=data.get('name')
                project=next((p for p in self.projects.projects if p['name']==name),None)
                if self.github_account.profile and action=='github-toggle':
                    row=next((p for p in self.projects.catalog if p['name']==name),None)
                    if not row:raise ValueError('Repository not found in your connected account.')
                    selected=data.get('selected') is True
                    if selected and not row.get('selected') and sum(bool(r.get('selected')) for r in self.projects.catalog)>=10:
                        raise ValueError('Choose up to 10 projects for interview context. Uncheck one first.')
                    row['selected']=selected
                    if project:project['selected']=selected
                    self.projects.save()
                    if selected and not project:self.refresh_github()
                    emit({'id':ident,'result':self.snapshot()})
                    self.publish()
                    return
                if not project:raise ValueError('Project not found.')
                if action=='github-remove':self.projects.projects.remove(project)
                else:project['selected']=data.get('selected') is True
                self.projects.save()
                result=self.snapshot()
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
                # Each session gets a copy of the saved evidence. Refreshes apply next session.
                s.github_documents = self.projects.documents()
                s.consent.setChecked(data.get('consent') is True)
                s.toggle_listen()
                result = self.snapshot()
            elif action == 'pause':
                s.pause_session()
            elif action == 'end':
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
    parser.add_argument('--project-store', type=Path)
    parser.add_argument('--github-account-store', type=Path)
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
    bridge = Bridge(qt, studio, ProjectStore(args.project_store) if args.project_store else None, GitHubAccount(AccountStore(args.github_account_store) if args.github_account_store and sys.platform=='win32' else None))
    if bridge.github_account.profile:QTimer.singleShot(1500,bridge.refresh_github)
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
