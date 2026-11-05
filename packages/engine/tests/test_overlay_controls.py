import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import QApplication, Prompter
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QEnterEvent, QKeyEvent, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QStyle, QStyleOptionSpinBox

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

    def test_stationary_pill_click_still_opens_reader(self):
        QTest.mouseClick(self.panel.chip, Qt.LeftButton)
        self.assertTrue(self.panel.expanded)
        self.assertIsNone(self.panel.drag_origin)

    def test_hover_never_changes_expanded_or_collapsed_size(self):
        panel = self.panel
        for expanded in (False, True, False):
            panel.set_expanded(expanded)
            before = panel.geometry()
            for _ in range(4):
                APP.sendEvent(panel, QEnterEvent(QPointF(10, 10), QPointF(10, 10),
                                                 QPointF(panel.geometry().center())))
                APP.sendEvent(panel, QEvent(QEvent.Leave))
                QTest.mouseMove(panel.auto_read if expanded else panel.chip, QPoint(5, 5))
            QTest.qWait(400)
            self.assertEqual(panel.expanded, expanded)
            self.assertEqual(panel.geometry(), before)

    def test_header_controls_receive_clicks_and_editing_without_dragging(self):
        panel = self.panel
        panel.set_expanded(True)
        before = panel.pos()
        QTest.mouseClick(panel.auto_read, Qt.LeftButton, pos=QPoint(8, panel.auto_read.height()//2))
        self.assertFalse(panel.auto_read.isChecked())
        self.assertIsNone(panel.drag_origin)

        speed = panel.read_pace
        value = speed.value()
        option = QStyleOptionSpinBox()
        speed.initStyleOption(option)
        up = speed.style().subControlRect(QStyle.CC_SpinBox, option, QStyle.SC_SpinBoxUp, speed)
        QTest.mouseClick(speed, Qt.LeftButton, pos=up.center())
        self.assertEqual(speed.value(), value+speed.singleStep())
        speed.setFocus()
        QTest.keyClick(speed, Qt.Key_A, Qt.ControlModifier)
        QTest.keyClicks(speed, '190')
        QTest.keyClick(speed, Qt.Key_Return)
        self.assertEqual(speed.value(), 190)
        self.assertIsNone(panel.drag_origin)
        self.assertEqual(panel.pos(), before)
        self.assertEqual(panel.header.cursor().shape(), Qt.ArrowCursor)
        self.assertEqual(panel.auto_read.cursor().shape(), Qt.PointingHandCursor)

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
        panel.set_expanded(True)
        original = panel.pos()
        slider = panel.font_slider
        self.mouse(slider, QEvent.MouseButtonPress, slider.mapToGlobal(QPoint(5, 5)))
        self.assertIsNone(panel.drag_origin)
        self.assertEqual(panel.pos(), original)
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
