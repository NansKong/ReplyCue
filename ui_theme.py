"""Presentation-only palette and component styling."""
from pathlib import Path

_assets = Path(__file__).resolve().parent / 'assets'
STYLE = '''
QWidget { color: #e9eeee; font-family: "Segoe UI"; font-size: 13px; }
QMainWindow, QWidget#appShell { background: #15191d; }
QWidget#workspace { background: #181d21; }
QFrame#sidebar { background: #111619; border-right: 1px solid #252c30; }
QLabel { background: transparent; }
QLabel#wordmark { font-size: 25px; font-weight: 600; color: #e4f4ee; padding-bottom: 6px; }
QLabel#eyebrow, QLabel#muted { font-size: 10px; color: #8d9c9e; letter-spacing: 1px; }
QLabel#title { font-size: 28px; font-weight: 600; color: #f0f5f3; padding: 3px 0; }
QLabel#sideNote { color: #879897; font-size: 12px; line-height: 1.5; padding: 10px 4px; }
QLabel#previewBadge { color: #9bcbb8; font-size: 11px; background: #1b2926; border: 1px solid #2b4038; border-radius: 9px; padding: 7px 9px; }
QLabel#privacyNote { color: #8d9d9e; font-size: 10px; }
QLabel#statusMessage { color: #a7b6b8; background: #1b2227; border: 1px solid #293238; border-radius: 10px; padding: 10px 12px; font-size: 11px; }
QTabWidget::pane { border: none; }
QTextEdit { background: #20272d; color: #e3eae9; border: 1px solid #354048; border-radius: 14px; padding: 18px; font-size: 15px; selection-background-color: #365c52; selection-color: #ffffff; }
QTextEdit:focus { border: 1px solid #8dc6b2; }
QPushButton { background: #252e34; border: 1px solid #3b474e; border-radius: 9px; padding: 9px 14px; color: #dfe7e7; }
QPushButton:hover { background: #303e43; border-color: #617a78; }
QPushButton:pressed { background: #1c282c; border-color: #9bcbb8; }
QPushButton:focus { border: 1px solid #b7e1d2; }
QPushButton:disabled { color: #657370; border-color: #28332f; background: #20282a; }
QPushButton#primary { background: #bce9d8; color: #142e25; font-size: 14px; font-weight: 600; padding: 12px 18px; border: 1px solid #c7f2e1; border-radius: 11px; }
QPushButton#primary:hover { background: #d1f5e7; }
QPushButton#primary:pressed { background: #a2d5c1; }
QPushButton#navigation { text-align: left; padding: 10px 12px; background: transparent; border: 1px solid transparent; color: #9fadae; }
QPushButton#navigation:hover { background: #20292c; color: #e7efed; }
QPushButton#navigation:checked { background: #263831; color: #cef1e3; border-color: #344c42; }
QCheckBox { spacing: 9px; color: #dbe6e2; }
QCheckBox::indicator { width: 15px; height: 15px; border-radius: 4px; border: 1px solid #6e8380; background: #20292b; }
QCheckBox::indicator:hover { border-color: #b0d8c7; }
QCheckBox::indicator:checked { background: #bce9d8; border: 1px solid #bce9d8; image: url(CHECK_ASSET); }
QCheckBox::indicator:disabled { background: #303a39; border-color: #50605b; }
QCheckBox:disabled { color: #75817d; }
QWidget#overlayBody QPushButton { font-size: 11px; padding: 5px 8px; border-radius: 8px; background: #283136; border-color: #3b494e; }
QWidget#overlayBody QPushButton:hover { background: #354440; border-color: #80a99a; }
QWidget#overlayBody QPushButton#brand { color: #bfe7d8; background: #243832; border-color: #385349; }
QWidget#overlayBody QPushButton#endSession { color: #d4b7b7; background: #322a2d; border-color: #493b40; }
QWidget#overlayBody QLabel { font-size: 11px; color: #b4c3c3; }
QWidget#overlayBody QLabel#muted { font-size: 10px; color: #a3c1b5; letter-spacing: 0px; }
QWidget#overlayBody QLabel#question { font-size: 12px; color: #a6bab8; padding: 3px 0; }
QPushButton#chip { background: transparent; border: none; color: #c0e7d8; font-size: 12px; font-weight: 500; }
QPushButton#chip:hover { color: #eefff7; }
QSpinBox { background: #252f32; border: 1px solid #42544f; border-radius: 7px; padding: 4px 15px 4px 4px; selection-background-color: #42645b; color: #dcece5; font-size: 11px; }
QSpinBox:focus { border-color: #bce9d8; }
QSpinBox:disabled { color: #71827a; background: #252c2c; border-color: #3a4340; }
QSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 15px; border: none; border-top-right-radius: 6px; background: #34413e; }
QSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 15px; border: none; border-bottom-right-radius: 6px; background: #34413e; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #4a6359; }
QSpinBox::up-arrow { image: url(UP_ASSET); width: 7px; height: 5px; }
QSpinBox::down-arrow { image: url(DOWN_ASSET); width: 7px; height: 5px; }
QSlider::groove:horizontal { background: #455651; height: 3px; border-radius: 1px; }
QSlider::sub-page:horizontal { background: #a0cebb; border-radius: 1px; }
QSlider::handle:horizontal { background: #d0eddf; border: 1px solid #9cc6b6; width: 10px; margin: -5px 0; border-radius: 6px; }
QSlider::handle:horizontal:hover { background: #f0fff8; border-color: #e1fff0; }
QSlider::handle:horizontal:pressed { background: #8fc4af; }
QSlider:disabled { background: transparent; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 4px 0; }
QScrollBar::handle:vertical { background: #576c65; border-radius: 3px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #8eb5a4; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QToolTip { background: #293834; color: #ecf8f0; border: 1px solid #567166; padding: 7px; }
'''
for token, name in [('CHECK_ASSET','check.svg'),('UP_ASSET','up.svg'),('DOWN_ASSET','down.svg')]:
    STYLE = STYLE.replace(token, (_assets / name).as_posix())
