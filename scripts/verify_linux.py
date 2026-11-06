"""Run on a Linux host in a dedicated disposable acceptance directory."""
import json
import os
from pathlib import Path
import subprocess
import time

EXE = Path(__file__).resolve().parent / 'pi-soloapi-linux-x64'
WORK = EXE.parent / 'Linux 中文 project'
WORK.mkdir(exist_ok=True)
env = dict(os.environ, PATH='/usr/bin:/bin')
for key in ('PI_CODING_AGENT_DIR', 'PI_PACKAGE_DIR', 'NODE_PATH', 'NODE_OPTIONS'):
    env.pop(key, None)


def run(args, timeout=180):
    result = subprocess.run([str(EXE), *args], cwd=WORK, env=env, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'Portable command failed: {args[0]}, exit {result.returncode}; stdout length {len(result.stdout)}, stderr length {len(result.stderr)}')
    return result


print('Checking Linux cold startup and original CLI...', flush=True)
started = time.monotonic()
info = json.loads(run(['--portable-diagnostics']).stdout)
assert info['platform'] == 'linux' and info['arch'] == 'x64'
assert Path(info['cwd']) == WORK
assert Path(info['agentDir']) == WORK / '.pi-portable/agent'
assert info['pi'] == '1.3.0' and info['node'] == 'v24.22.2'
assert info['fullPermissions'] is True
cold_seconds = round(time.monotonic() - started, 2)
started = time.monotonic()
assert json.loads(run(['--portable-diagnostics']).stdout)['runtime'] == info['runtime']
warm_seconds = round(time.monotonic() - started, 2)
assert run(['--version']).stdout.strip() == '1.3.0'
assert 'solo-auto' in run(['--list-models']).stdout
assert '--append-system-prompt' in run(['--help']).stdout
runtime = Path(info['runtime'])
tools_env = dict(env, PATH=str(runtime / 'node/bin') + ':' + str(WORK / '.pi-portable/agent/bin') + ':/usr/bin:/bin')
tools = subprocess.run(['/bin/bash', '-c', 'set -e; node --version; npm --version; rg --version; fd --version'],
                       cwd=WORK, env=tools_env, capture_output=True, text=True, timeout=60)
assert tools.returncode == 0 and 'v24.22.2' in tools.stdout
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
assert set(('read', 'write', 'edit', 'bash')) <= set(events)
report = {'platform': 'linux-x64', 'pi': info['pi'], 'node': info['node'],
          'system': subprocess.check_output(['uname', '-sm'], text=True).strip(),
          'libc': subprocess.check_output(['getconf', 'GNU_LIBC_VERSION'], text=True).strip(),
          'coldSeconds': cold_seconds, 'warmSeconds': warm_seconds,
          'originalToolsExecuted': sorted(set(events)), 'realSoloApiReply': True,
          'unicodeAndSpacesInCwd': True, 'bundledNodeNpmRgFd': True,
          'nodeAndPiNotRequiredOnSystemPath': True}
(EXE.parent / 'acceptance-linux.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
