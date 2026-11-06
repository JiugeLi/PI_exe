"""Check the shipped Windows executable with global Node/Pi/Git removed from PATH."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / 'dist/Pi-SoloAPI-Windows-x64.exe'
WORK = ROOT / '.build/acceptance/Windows 中文 project'
WORK.mkdir(parents=True, exist_ok=True)
ORIGINAL = Path.home() / '.pi/agent'
BEFORE = {name: hashlib.sha256((ORIGINAL / name).read_bytes()).hexdigest()
          for name in ('models.json', 'settings.json', 'auth.json')}
env = dict(os.environ)
env['PATH'] = os.path.join(os.environ['SystemRoot'], 'System32') + ';' + os.environ['SystemRoot']
for key in ('PI_CODING_AGENT_DIR', 'PI_PACKAGE_DIR', 'NODE_PATH', 'NODE_OPTIONS'):
    env.pop(key, None)


def run(args, timeout=180):
    result = subprocess.run([str(EXE), *args], cwd=WORK, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if result.returncode:
        # Do not dump arbitrary provider errors or configuration into logs.
        raise RuntimeError(f'Portable command failed: {args[0]}, exit {result.returncode}; stdout length {len(result.stdout)}, stderr length {len(result.stderr)}')
    return result


print('Checking launch and original CLI...', flush=True)
known_runtimes = {p.parent.resolve() for p in (WORK / '.pi-portable/runtime').glob('*/.complete')}
started = time.monotonic()
cold = run(['--portable-diagnostics'])
info = json.loads(cold.stdout)
assert Path(info['cwd']) == WORK
assert Path(info['agentDir']) == WORK / '.pi-portable/agent'
assert info['provider'] == 'soloapi' and info['model'] == 'solo-auto'
assert info['pi'] == '1.3.0' and info['fullPermissions'] is True
assert info['node'] == 'v24.22.2'
first_seconds = round(time.monotonic() - started, 2)
started = time.monotonic()
warm = run(['--portable-diagnostics'])
assert json.loads(warm.stdout)['runtime'] == info['runtime']
warm_seconds = round(time.monotonic() - started, 2)
assert run(['--version']).stdout.strip() == '1.3.0'
assert 'solo-auto' in run(['--list-models']).stdout
assert '--append-system-prompt' in run(['--help']).stdout

runtime = Path(info['runtime'])
node = runtime / 'node/node.exe'
bash = runtime / 'bash/usr/bin/bash.exe'
tool_env = dict(env, PATH=str(bash.parent) + ';' + str(node.parent) + ';' + env['PATH'])
shell = subprocess.run([str(bash), '-c', "set -e; printf 'SHELL_OK\\n'; node --version; npm --version; rg --version; fd --version"],
    cwd=WORK, env=dict(tool_env, PATH=str(WORK / '.pi-portable/agent/bin') + ';' + tool_env['PATH']),
    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
assert shell.returncode == 0 and 'SHELL_OK' in shell.stdout and 'v24.22.2' in shell.stdout, 'Bundled shell/tools failed'

print('Checking real SoloAPI reply and all four original tools...', flush=True)
prompt = ("Run this portable-agent acceptance test in the current working directory only. "
          "Do not inspect configuration, hidden files, credentials or git. "
          "Use the write tool to create portable-acceptance.txt with exactly FIRST_VALUE and a newline. "
          "Use read to check it. Use edit to replace FIRST_VALUE with SECOND_VALUE. "
          "Use bash to execute exactly: printf 'PORTABLE_SHELL_OK\\n'; cat portable-acceptance.txt\n"
          "Then reply with PORTABLE_TEST_OK. Perform all four tools.")
reply = run(['--no-session', '--mode', 'json', '-p', '--tools', 'read,write,edit,bash', prompt], timeout=300)
assert (WORK / 'portable-acceptance.txt').read_text().strip() == 'SECOND_VALUE'
assert 'PORTABLE_TEST_OK' in reply.stdout and 'PORTABLE_SHELL_OK' in reply.stdout
events = []
for line in reply.stdout.splitlines():
    try:
        event = json.loads(line)
        if event.get('type') == 'tool_execution_start':
            events.append(event['toolName'])
    except (ValueError, KeyError):
        pass
assert set(('read', 'write', 'edit', 'bash')) <= set(events), 'Not all original tools executed'
assert BEFORE == {name: hashlib.sha256((ORIGINAL / name).read_bytes()).hexdigest() for name in BEFORE}
report = {'platform': 'windows-x64', 'pi': info['pi'], 'node': info['node'],
          'firstDiagnosticSeconds': first_seconds, 'warmDiagnosticSeconds': warm_seconds,
          'runtimeExtractedThisRun': Path(info['runtime']).resolve() not in known_runtimes,
          'globalNodePiGitRemovedFromPath': True, 'unicodeAndSpacesInCwd': True,
          'originalProfileUnchanged': True, 'realSoloApiReply': True,
          'originalToolsExecuted': sorted(set(events)), 'bundledBashNodeNpmRgFd': True}
(ROOT / 'dist/acceptance-windows.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
