"""Render the canonical website favicon into a multi-resolution Windows ICO."""
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def main():
    windows = Path(__file__).resolve().parents[1]
    source = windows.parent / 'website' / 'app' / 'icon.svg'
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise ValueError(f'Invalid favicon: {source}')
    sizes = (16, 20, 24, 32, 48, 64, 128, 256)
    frames = []
    for size in sizes:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, 'PNG'):
            raise RuntimeError('Could not encode the icon')
        frames.append(bytes(buffer.data()))
    offset = 6 + 16 * len(frames)
    entries = []
    for size, frame in zip(sizes, frames):
        entries.append(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0,
                                   1, 32, len(frame), offset))
        offset += len(frame)
    icon = struct.pack('<HHH', 0, 1, len(frames)) + b''.join(entries) + b''.join(frames)
    for output in (windows / 'electron' / 'icon.ico',
                   windows.parents[1] / 'packages' / 'engine' / 'assets' / 'copilot.ico'):
        output.write_bytes(icon)
    print(f'Generated Copilot icon from favicon: {list(sizes)} px')


if __name__ == '__main__':
    main()
