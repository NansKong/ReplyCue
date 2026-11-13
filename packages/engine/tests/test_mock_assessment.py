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

    def test_desktop_bridge_requires_review_and_preserves_solution_history(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'apps' / 'windows' / 'backend'))
        from bridge import Bridge, DesktopStudio
        from PySide6.QtTest import QTest
        studio=DesktopStudio()
        events=[]
        with patch('bridge.emit',side_effect=events.append), patch.object(studio,'ready',return_value=True), patch('managed_ai.enabled',return_value=True), patch('managed_ai.begin_session'), patch('managed_ai.end_session'), patch.object(studio,'start_capture') as audio, patch('bridge.capture_region',return_value='data:image/jpeg;base64,fixture'), patch('managed_ai.call',return_value={'text':'Question: Which algorithm?\n\nB: Binary search. The input is sorted.'}) as provider:
            bridge=Bridge(APP,studio)
            bridge.dispatch({'id':1,'action':'start','data':{'mode':'mock','consent':True}})
            self.assertTrue(studio.live and studio.mock_mode)
            bridge.dispatch({'id':2,'action':'mock-capture'})
            QTest.qWait(550)
            provider.assert_not_called()
            self.assertTrue(bridge.mock_image)
            bridge.dispatch({'id':3,'action':'mock-solve','data':{'language':'Python 3','questionType':'mcq'}})
            for _ in range(100):
                APP.processEvents(); QTest.qWait(10)
                if studio.qa_records and studio.qa_records[0]['status']=='Complete':break
            self.assertEqual(studio.qa_records[0]['status'],'Complete')
            self.assertIn('Binary search',studio.panel.reader.toPlainText())
            self.assertIsNone(bridge.mock_image)
            provider.assert_called_once()
            audio.assert_not_called()
            bridge.dispatch({'id':4,'action':'end'})
            bridge.dispatch({'id':5,'action':'mock-solve','data':{'language':'Python 3','questionType':'mcq'}})
            self.assertIn('error',events[-1])
            provider.assert_called_once()
            bridge.timer.stop()
            for worker in studio.workers():worker.wait(2000)
            studio.close()

    def test_picker_has_cancel_timeout(self):
        pix=QPixmap(300,200)
        picker=RegionPicker(APP.primaryScreen(),pix)
        self.assertTrue(picker.timeout.isActive())
        self.assertEqual(picker.timeout.interval(),150000)
        picker.reject()
        picker.close()

if __name__ == '__main__': unittest.main()
