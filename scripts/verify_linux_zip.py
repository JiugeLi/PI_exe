"""Run beside a Linux release ZIP and a private test config on a Linux host."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

root = Path(__file__).resolve().parent
with zipfile.ZipFile(root / 'Pi-SoloAPI-Linux-x64.zip') as bundle:
    bundle.extractall(root)
release = root / 'Pi-SoloAPI-Linux-x64'
exe = release / 'pi-soloapi-linux-x64'
exe.chmod(0o700)
work = release / 'Linux 中文 project'
work.mkdir(exist_ok=True)
env = {k:v for k,v in os.environ.items() if k.lower() not in ('http_proxy','https_proxy','all_proxy')}
env.pop('PI_PORTABLE_CONFIG', None)
env.pop('SOLOAPI_API_KEY', None)
def diagnostics():
    return json.loads(subprocess.check_output([str(exe), '--portable-diagnostics'], cwd=work,
                     env=env, stdin=subprocess.DEVNULL, text=True, timeout=180))
public = release / 'pi.config.json'
original = public.read_bytes()
assert json.loads(original)['apiKey'] == ''
info = diagnostics()
assert info['apiKeyConfigured'] is False and Path(info['configFile']) == public
edited = json.loads(original)
edited.update(apiKey='test-config-marker', defaultModel='linux-config-edit-check')
public.write_text(json.dumps(edited))
changed = diagnostics()
assert changed['model'] == 'linux-config-edit-check' and changed['apiKeyConfigured']
assert 'test-config-marker' not in (work / '.pi-portable/agent/models.json').read_text()
public.write_bytes(original)
private = root / 'pi.private.json'
private.chmod(0o600)
env['PI_PORTABLE_CONFIG'] = str(private)
shutil.copyfile(root / 'verify_linux.py', release / 'verify_linux.py')
subprocess.run([sys.executable, str(release / 'verify_linux.py')], env=env, stdin=subprocess.DEVNULL, check=True)
report = json.loads((release / 'acceptance-linux.json').read_text())
report.update(zipExtractedAndVerified=True, blankKeyReleaseConfig=True,
              siblingConfigEditApplied=True, privateConfigOverrideVerified=True,
              proxyEnvironment='unset for this acceptance run')
(root / 'acceptance-linux.json').write_text(json.dumps(report, indent=2) + '\n')
