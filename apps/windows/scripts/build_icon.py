"""Render the canonical ReplyCue logo into a multi-resolution Windows ICO."""
from pathlib import Path
from PIL import Image


def main():
    windows = Path(__file__).resolve().parents[1]
    source = windows.parents[1] / 'assets' / 'ReplyCue-logo.png'
    if not source.exists():
        source = windows.parent / 'website' / 'public' / 'icon-512x512.png'
    if not source.exists():
        raise FileNotFoundError(f'Could not find icon source at {source}')

    im = Image.open(source).convert('RGBA')
    sizes = [(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    for output in (
        windows / 'electron' / 'icon.ico',
        windows.parents[1] / 'packages' / 'engine' / 'assets' / 'copilot.ico',
    ):
        output.parent.mkdir(parents=True, exist_ok=True)
        im.save(output, format='ICO', sizes=sizes)
    print(f'Generated Windows and engine icons from {source.name}: {[s[0] for s in sizes]} px')


if __name__ == '__main__':
    main()
