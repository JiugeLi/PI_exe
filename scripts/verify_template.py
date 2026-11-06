"""Check that the shipped template works after filling only apiKey."""
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
work = root / '.build/acceptance/ZIP 工作 project'
exe = root / '.build/acceptance/ZIP release/Pi-SoloAPI-Windows-x64/Pi-SoloAPI-Windows-x64.exe'
config = json.loads((root / 'config/pi.config.example.json').read_text())
config['apiKey'] = json.loads((root / 'private/pi.config.json').read_text(encoding='utf-8-sig'))['apiKey']
filename = work / '.pi-portable/tmp/template-only-test.json'
filename.write_text(json.dumps(config))
try:
    env = dict(os.environ, PI_PORTABLE_CONFIG=str(filename))
    env.pop('SOLOAPI_API_KEY', None)
    result = subprocess.run([str(exe), '--no-session', '-p', 'Reply exactly TEMPLATE_CONFIG_OK. Do not use tools.'],
                            cwd=work, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                            encoding='utf-8', errors='replace', timeout=90)
    assert result.returncode == 0 and 'TEMPLATE_CONFIG_OK' in result.stdout, 'Template-only real model check failed'
finally:
    filename.unlink(missing_ok=True)
report_path = root / 'dist/acceptance-windows.json'
report = json.loads(report_path.read_text())
report['templatePlusKeyRealReply'] = True
report_path.write_text(json.dumps(report, indent=2) + '\n')
print('Public template with only apiKey filled: real model reply passed')
