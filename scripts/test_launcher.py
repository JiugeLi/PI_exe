"""Test launcher extraction with a credential-free placeholder embed."""
import os
from pathlib import Path
import subprocess
import zipfile

root = Path(__file__).resolve().parents[1]
embedded = root / 'launcher/payload.zip'
if embedded.exists():
    raise RuntimeError('A build already owns launcher/payload.zip; finish it before testing.')
try:
    with zipfile.ZipFile(embedded, 'w'):
        pass
    subprocess.run([str(root / '.tools/go/bin/go.exe'), 'test', './launcher'], cwd=root,
                   env=dict(os.environ, GOCACHE=str(root / '.tools/go-cache')), check=True)
finally:
    embedded.unlink(missing_ok=True)
