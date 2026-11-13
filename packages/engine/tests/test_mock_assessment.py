import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import QApplication, Studio
from mock_assessment import MockJob, RegionPicker
from PySide6.QtGui import QPixmap
APP = QApplication.instance() or QApplication([])

class MockTests(unittest.TestCase):
    def test_mock_session_and_resume_never_open_audio(self):
        studio = Studio()
        with patch.object(studio, 'ready', return_value=True), patch('managed_ai.begin_session'), patch('managed_ai.end_session'), patch.object(studio, 'start_capture') as audio:
            studio.toggle_listen(mock=True)
            self.assertTrue(studio.live and studio.mock_mode)
            self.assertEqual(studio.qa_records, [])
            studio.pause_session()
            self.assertTrue(studio.paused)
            studio.pause_session()
            self.assertFalse(studio.paused)
            audio.assert_not_called()
            studio.stop_live()
        studio.close()

    def test_mock_result_and_image_cleanup(self):
        job = MockJob('data:image/jpeg;base64,fixture', 'Python 3', 'mcq')
        answers=[]
        job.answer.connect(answers.append)
        with patch('managed_ai.enabled', return_value=True), patch('managed_ai.call', return_value={'text':'B: binary search. The input is sorted.'}) as call:
            job.run()
            self.assertEqual(call.call_args.args[0]['kind'], 'mock-assessment')
            self.assertEqual(call.call_args.args[0]['questionType'], 'mcq')
            self.assertEqual(job.final_answer, answers[-1])
            self.assertIsNone(job.image)

    def test_provider_error_clears_image(self):
        from managed_ai import ManagedError
        job=MockJob('private pixels','SQL','coding')
        errors=[]
        job.problem.connect(errors.append)
        with patch('managed_ai.enabled',return_value=True),patch('managed_ai.call',side_effect=ManagedError('Trial ended')):
            job.run()
        self.assertIsNone(job.image)
        self.assertEqual(errors,['Trial ended'])

    def test_selected_region_is_cropped_and_encoded_without_writing_a_file(self):
        from types import SimpleNamespace
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QImage
        from PySide6.QtWidgets import QDialog
        import base64
        from mock_assessment import capture_region
        pix=QPixmap(800,600)
        pix.fill('white')
        screen=SimpleNamespace(grabWindow=lambda _:pix, geometry=lambda:QRect(0,0,400,300))
        def select(picker):
            picker.selection=QRect(10,20,100,80)
            return QDialog.Accepted
        with patch('mock_assessment.QApplication.screenAt',return_value=screen), patch.object(RegionPicker,'exec',select):
            result=capture_region()
        image=QImage.fromData(base64.b64decode(result.split(',')[1]))
        self.assertEqual((image.width(),image.height()),(200,160))
        self.assertTrue(result.startswith('data:image/jpeg;base64,'))

    def test_desktop_bridge_automatically_solves_after_area_selection(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'apps' / 'windows' / 'backend'))
        from bridge import Bridge, DesktopStudio
        from PySide6.QtTest import QTest
        studio=DesktopStudio()
        events=[]
        with patch('bridge.emit',side_effect=events.append), patch.object(studio,'ready',return_value=True), patch('managed_ai.enabled',return_value=True), patch('managed_ai.begin_session'), patch('managed_ai.end_session'), patch.object(studio,'start_capture') as audio, patch('bridge.capture_region',return_value='data:image/jpeg;base64,fixture'), patch('managed_ai.call',return_value={'text':'Question: Which algorithm?\n\nB: Binary search. The input is sorted.'}) as provider:
            bridge=Bridge(APP,studio)
            bridge.dispatch({'id':1,'action':'start','data':{'mode':'mock','consent':True,'language':'Python 3','questionType':'mcq'}})
            self.assertTrue(studio.live and studio.mock_mode)
            for _ in range(100):
                APP.processEvents(); QTest.qWait(10)
                if studio.qa_records and studio.qa_records[0]['status']=='Complete':break
            self.assertEqual(studio.qa_records[0]['status'],'Complete')
            self.assertIn('Binary search',studio.panel.reader.toPlainText())
            self.assertIsNone(bridge.mock_image)
            provider.assert_called_once()
            audio.assert_not_called()
            # A completed new question must not sit behind the old reading hold.
            studio.reader_hold.start(45000)
            provider.return_value={'text':'Second solution: C. The new question has a different answer.'}
            bridge.start_mock_answer('data:image/jpeg;base64,next-fixture')
            for _ in range(100):
                APP.processEvents(); QTest.qWait(10)
                if studio.qa_records[-1]['status']=='Complete':break
            self.assertIn('Second solution',studio.panel.reader.toPlainText())
            self.assertEqual(len(studio.qa_records),2)
            self.assertEqual(provider.call_count,2)
            # Paused and ended sessions never capture pixels or call the provider.
            studio.paused=True
            bridge.mock_scope=('fake scope',)
            with patch('bridge.capture_scope') as pixels:
                bridge.watch_mock()
                pixels.assert_not_called()
                studio.paused=False
                bridge.dispatch({'id':4,'action':'end'})
                bridge.watch_mock()
                pixels.assert_not_called()
            self.assertEqual(provider.call_count,2)
            bridge.timer.stop(); bridge.mock_timer.stop()
            for worker in studio.workers():worker.wait(2000)
            studio.close()

    def test_stability_and_duplicate_suppression(self):
        from mock_assessment import StableQuestion
        watcher=StableQuestion()
        first=bytes([10])*6144
        second=bytes([100])*6144
        self.assertFalse(watcher.observe(first,0))
        self.assertFalse(watcher.observe(first,.5))
        self.assertTrue(watcher.observe(first,1.1))
        watcher.submitted_now(first,1.1)
        self.assertFalse(watcher.observe(first,20))
        # A single blinking caret pixel does not count as a new question.
        self.assertFalse(watcher.observe(bytes([255])+first[1:],21))
        self.assertFalse(watcher.observe(second,22))
        self.assertTrue(watcher.observe(second,23.1))
        watcher.submitted_now(second,23.1)
        self.assertFalse(watcher.observe(second,40))

    def test_changes_must_settle_and_requests_have_a_cooldown(self):
        from mock_assessment import StableQuestion
        watcher=StableQuestion()
        a,b,c=(bytes([v])*6144 for v in (0,100,200))
        self.assertFalse(watcher.observe(a,0))
        self.assertFalse(watcher.observe(b,.6))
        self.assertFalse(watcher.observe(c,1.2))
        self.assertTrue(watcher.observe(c,2.3))
        watcher.submitted_now(c,2.3)
        self.assertFalse(watcher.observe(a,3))
        self.assertFalse(watcher.observe(a,4.2))
        self.assertTrue(watcher.observe(a,7.4))

    def test_picker_has_cancel_timeout(self):
        pix=QPixmap(300,200)
        picker=RegionPicker(APP.primaryScreen(),pix)
        self.assertTrue(picker.timeout.isActive())
        self.assertEqual(picker.timeout.interval(),150000)
        picker.reject()
        picker.close()

if __name__ == '__main__': unittest.main()
