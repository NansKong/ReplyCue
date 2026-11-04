import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import QApplication, Prompter
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtTest import QTest

APP = QApplication.instance() or QApplication([])


class Preferences:
    def __init__(self):
        self.values = {}
        self.synced = False

    def value(self, key):
        return self.values.get(key)

    def setValue(self, key, value):
        self.values[key] = value

    def sync(self):
        self.synced = True


class OverlayControlsTests(unittest.TestCase):
    def setUp(self):
        self.preferences = Preferences()
        self.panel = Prompter(preferences=self.preferences)
        self.panel.animation.setDuration(0)
        self.panel.show_idle()
        self.addCleanup(self.panel.close)

    def mouse(self, widget, kind, pointer, buttons=Qt.LeftButton):
        local = widget.mapFromGlobal(pointer)
        event = QMouseEvent(kind, QPointF(local), QPointF(pointer),
                            Qt.NoButton if kind == QEvent.MouseMove else Qt.LeftButton,
                            buttons, Qt.NoModifier)
        return self.panel.eventFilter(widget, event)

    def test_shortcuts_are_explicit_and_repeat_safe(self):
        panel = self.panel
        for key, expanded in [(Qt.Key_M, True), (Qt.Key_M, True),
                              (Qt.Key_N, False), (Qt.Key_N, False)]:
            APP.sendEvent(panel, QKeyEvent(QEvent.KeyPress, key, Qt.ShiftModifier))
            self.assertEqual(panel.expanded, expanded)
            self.assertEqual(panel.geometry(), panel.target(expanded))
        self.assertFalse(panel.hover_open)

    def test_stationary_pill_click_still_opens_reader(self):
        QTest.mouseClick(self.panel.chip, Qt.LeftButton)
        self.assertTrue(self.panel.expanded)
        self.assertIsNone(self.panel.drag_origin)

    def test_hover_peek_closes_on_leave_but_pinned_reader_stays(self):
        panel = self.panel
        with patch('app.QCursor.pos', return_value=panel.geometry().center()):
            panel.peek()
        self.assertTrue(panel.expanded)
        self.assertTrue(panel.hover_open)
        with patch('app.QCursor.pos', return_value=QPoint(-10000, -10000)):
            panel.end_peek()
        self.assertFalse(panel.expanded)
        with patch('app.QCursor.pos', return_value=panel.geometry().center()):
            panel.peek()
        panel.set_expanded(True)
        with patch('app.QCursor.pos', return_value=QPoint(-10000, -10000)):
            panel.end_peek()
        self.assertTrue(panel.expanded)
        self.assertFalse(panel.hover_open)

    def test_explicit_collapse_blocks_hover_until_pointer_leaves(self):
        panel = self.panel
        panel.set_expanded(True)
        with patch('app.QCursor.pos', return_value=panel.target(False).center()):
            panel.set_expanded(False)
            panel.peek()
        self.assertTrue(panel.hover_blocked)
        self.assertFalse(panel.expanded)
        panel.leaveEvent(QEvent(QEvent.Leave))
        self.assertFalse(panel.hover_blocked)
        with patch('app.QCursor.pos', return_value=panel.geometry().center()):
            panel.peek()
        self.assertTrue(panel.expanded)

    def test_drag_moves_pill_without_expanding_and_restores_position(self):
        panel = self.panel
        start = panel.geometry().center()
        destination = start + QPoint(80, 140)
        self.mouse(panel.chip, QEvent.MouseButtonPress, start)
        self.assertTrue(self.mouse(panel.chip, QEvent.MouseMove, destination))
        self.assertTrue(self.mouse(panel.chip, QEvent.MouseButtonRelease,
                                   destination, Qt.NoButton))
        self.assertFalse(panel.expanded)
        self.assertTrue(self.preferences.synced)
        self.assertEqual(panel.anchor, self.preferences.value('position'))
        anchor = QPoint(panel.anchor)
        panel.set_expanded(True)
        self.assertEqual(panel.x()+panel.width()//2, anchor.x())
        self.assertEqual(panel.geometry().top(), anchor.y())
        panel.set_expanded(False)
        self.assertEqual(panel.geometry().top(), anchor.y())
        restored = Prompter(preferences=self.preferences)
        self.addCleanup(restored.close)
        self.assertEqual(restored.geometry(), panel.geometry())

    def test_grip_drag_keeps_controls_and_reader_interactive(self):
        panel = self.panel
        panel.set_expanded(True, hover=True)
        original = panel.pos()
        slider = panel.font_slider
        self.mouse(slider, QEvent.MouseButtonPress, slider.mapToGlobal(QPoint(5, 5)))
        self.assertIsNone(panel.drag_origin)
        self.assertEqual(panel.pos(), original)
        self.assertFalse(panel.hover_open)
        start = panel.drag_handle.mapToGlobal(QPoint(8, 8))
        self.mouse(panel.drag_handle, QEvent.MouseButtonPress, start)
        self.mouse(panel.drag_handle, QEvent.MouseMove, start + QPoint(0, 100))
        self.mouse(panel.drag_handle, QEvent.MouseButtonRelease,
                   start + QPoint(0, 100), Qt.NoButton)
        self.assertEqual(panel.y(), original.y()+100)
        self.assertTrue(panel.expanded)
        self.assertIsNone(panel.drag_origin)

    def test_drag_cannot_leave_overlay_outside_available_screen(self):
        panel = self.panel
        screen = panel.screen().availableGeometry()
        panel.drag_to(QPoint(-100000, -100000), screen.center())
        self.assertTrue(screen.contains(panel.geometry()))
        panel.drag_to(QPoint(100000, 100000), screen.center())
        self.assertTrue(screen.contains(panel.geometry()))


if __name__ == '__main__':
    unittest.main()
