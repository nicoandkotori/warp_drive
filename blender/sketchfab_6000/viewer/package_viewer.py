"""Bundle the interactive viewer and its reference stills for offline use."""
from pathlib import Path
import base64

root = Path(__file__).resolve().parent
html = (root / 'index.html').read_text(encoding='utf-8')
for name in ('data.js', 'viewer.js'):
    html = html.replace(f'<script src="{name}"></script>',
                        '<script>' + (root / name).read_text(encoding='utf-8') + '</script>')
for path in root.glob('reference_*.png'):
    html = html.replace(path.name, 'data:image/png;base64,' +
                        base64.b64encode(path.read_bytes()).decode())
target = root.parent / 'galaxy-interactive.html'
target.write_text(html, encoding='utf-8')
print(f'Packaged {target.name}: {target.stat().st_size} bytes')
