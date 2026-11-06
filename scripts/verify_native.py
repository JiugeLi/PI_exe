"""End-to-end single-file extraction, config generation and native /login tests."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--release-dir', type=Path, required=True)
parser.add_argument('--work-dir', type=Path, required=True)
parser.add_argument('--platform', choices=['windows','linux'], required=True)
parser.add_argument('--private-config', type=Path, required=True)
args = parser.parse_args()
release = args.release_dir.resolve()
root = args.work_dir.resolve()
app, cwd = root / 'app', root / '工作 project'
app.mkdir(parents=True, exist_ok=True)
cwd.mkdir(parents=True, exist_ok=True)
if (cwd / '.pi-portable').exists(): raise RuntimeError('Use a fresh work directory for cold extraction verification.')
binary = 'pi-windows-x64.exe' if args.platform == 'windows' else 'pi-linux-x64'
exe = app / binary
shutil.copyfile(release / binary, exe)
if args.platform == 'linux': exe.chmod(0o700)
env = {k:v for k,v in os.environ.items() if k not in ('PI_PORTABLE_CONFIG','PI_CODING_AGENT_DIR','PI_PACKAGE_DIR','SOLOAPI_API_KEY','SOLOMUX_API_KEY','PI_PORTABLE_API_KEY','NODE_OPTIONS','NODE_PATH')}
def run(options, timeout=240):
    r = subprocess.run([str(exe), *options], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        capture_output=True, encoding='utf-8', errors='replace', timeout=timeout)
    if r.returncode: raise RuntimeError(f'CLI check failed, exit {r.returncode}; stderr length {len(r.stderr)}')
    return r
print('Checking automatic config generation and real extraction progress...', flush=True)
cold = run(['--portable-diagnostics'])
info = json.loads(cold.stdout)
assert info['provider'] == 'solomux' and info['apiKeyConfigured'] is False
assert Path(info['cwd']) == cwd and Path(info['configFile']) == app / 'config.json'
assert json.loads((app / 'config.json').read_text())['apiKey'] == ''
assert (app / 'README.zh-CN.md').exists() and (app / 'README.en.md').exists()
samples = [int(x) for x in re.findall(r'\] +(\d+)%', cold.stderr)]
assert len(samples) >= 2 and samples[0] == 0 and samples[-1] == 100 and samples == sorted(samples)
assert samples.count(100) == 1 and '准备完成' in cold.stderr
assert (Path(info['runtime']) / '.complete').exists()
config = app / 'config.json'
original = config.read_bytes()
edited = json.loads(original); edited['defaultModel'] = 'config-edit-check'
config.write_text(json.dumps(edited))
assert json.loads(run(['--portable-diagnostics']).stdout)['model'] == 'config-edit-check'
assert json.loads(config.read_text())['defaultModel'] == 'config-edit-check'
config.write_bytes(original)
warm = run(['--portable-diagnostics'])
assert not warm.stderr.strip()
assert run(['--version']).stdout.strip() == '1.3.0'
info = json.loads(warm.stdout)
info_file = root / 'info.json'; info_file.write_text(json.dumps(info))
node = Path(info['runtime']) / ('node/node.exe' if args.platform == 'windows' else 'node/bin/node')
print('Checking native SoloMux API-key login and automatic model discovery...', flush=True)
probe = Path(__file__).with_name('verify_native_login.mjs')
r = subprocess.run([str(node), str(probe), str(info_file), str(args.private_config.resolve())], cwd=cwd,
    env=env, stdin=subprocess.DEVNULL, capture_output=True, encoding='utf-8', errors='replace', timeout=90)
if r.returncode:
    # Retain no provider payloads or secrets in logs.
    known = json.loads(args.private_config.read_text(encoding='utf-8-sig'))['apiKey']
    print(r.stderr.replace(known, '[REDACTED]')[:2500])
    raise RuntimeError('Native login probe failed')
login_report = json.loads(r.stdout.strip().splitlines()[-1])
assert json.loads(config.read_text())['apiKey'] == ''
assert json.loads(run(['--portable-diagnostics']).stdout)['provider'] == 'solomux'
print('Checking saved login after restart and original file/shell tools...', flush=True)
prompt = ('Acceptance check. Do not inspect configuration, hidden files, credentials or git. '
          'Use write to create portable-acceptance.txt containing FIRST_VALUE. Use read to check it. '
          'Use edit to replace FIRST_VALUE with SECOND_VALUE. Use bash to run cat portable-acceptance.txt. '
          'Finish with PORTABLE_TEST_OK. Use all four tools.')
reply = run(['--no-session','--mode','json','-p','--tools','read,write,edit,bash',prompt], timeout=240)
assert (cwd / 'portable-acceptance.txt').read_text().strip() == 'SECOND_VALUE'
assert 'PORTABLE_TEST_OK' in reply.stdout
tools = set()
for line in reply.stdout.splitlines():
    try:
        e=json.loads(line)
        if e.get('type')=='tool_execution_start': tools.add(e['toolName'])
    except ValueError: pass
assert {'read','write','edit','bash'} <= tools
report = { 'platform': args.platform, 'autoConfigAndBilingualReadmes': True,
    'configEditPreserved': True, 'coldProgressSamples': len(samples), 'progressMonotonic': True,
    'jsonStdoutClean': True, 'cachedLaunchQuiet': True, **login_report,
    'loginSurvivesRestart': True, 'originalToolsExecuted': sorted(tools), 'realModelReply': True }
(release / ('acceptance-native-'+args.platform+'.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
