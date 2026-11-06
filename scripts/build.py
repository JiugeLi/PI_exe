"""Build personal, offline-runtime Pi executables. Never prints credentials."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / '.build'
TOOLS = ROOT / '.tools'
DIST = ROOT / 'dist'
HOME = Path.home()
PI = Path(os.environ['APPDATA']) / 'npm/node_modules/@earendil-works/pi-coding-agent'
PROFILE = HOME / '.pi/agent'
GIT = Path('C:/Program Files/Git')
NODE_VERSION = 'v24.22.2'
GO_VERSION = 'go1.27.3'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str, target: Path, expected: str | None = None) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and (expected is None or digest(target.read_bytes()) == expected):
        return target
    print('Download:', url, flush=True)
    subprocess.run(['curl.exe', '-4', '--fail', '--location', '--retry', '3', '--retry-all-errors', '--silent',
                    '--show-error', '--connect-timeout', '30', '--max-time', '600',
                    '--output', str(target) + '.part', url], check=True)
    part = target.with_name(target.name + '.part')
    data = part.read_bytes()
    if expected and digest(data) != expected:
        raise RuntimeError('Download checksum mismatch: ' + target.name)
    part.replace(target)
    return target


def checked_node(platform: str) -> Path:
    base = f'https://nodejs.org/dist/{NODE_VERSION}/'
    name = f'node-{NODE_VERSION}-' + ('win-x64.zip' if platform == 'windows' else 'linux-x64.tar.xz')
    with urllib.request.urlopen(base + 'SHASUMS256.txt', timeout=60) as response:
        sums = dict(line.split()[::-1] for line in response.read().decode().splitlines())
    return download(base + name, BUILD / 'downloads' / name, sums[name])


def ensure_go() -> Path:
    go = TOOLS / 'go/bin/go.exe'
    if go.exists():
        return go
    with urllib.request.urlopen('https://go.dev/dl/?mode=json&include=all', timeout=60) as response:
        releases = json.load(response)
    release = next(item for item in releases if item['version'] == GO_VERSION)
    archive = next(item for item in release['files'] if item['os'] == 'windows' and item['arch'] == 'amd64' and item['kind'] == 'archive')
    src = download('https://go.dev/dl/' + archive['filename'], BUILD / 'downloads' / archive['filename'], archive['sha256'])
    with zipfile.ZipFile(src) as bundle:
        bundle.extractall(TOOLS)
    return go


def imports(file: Path) -> list[str]:
    """Read PE import table to include the MSYS DLL closure, without third-party tools."""
    b = file.read_bytes()
    pe = struct.unpack_from('<I', b, 0x3c)[0]
    sections_count = struct.unpack_from('<H', b, pe + 6)[0]
    optional_size = struct.unpack_from('<H', b, pe + 20)[0]
    optional = pe + 24
    magic = struct.unpack_from('<H', b, optional)[0]
    data_dir = optional + (112 if magic == 0x20b else 96)
    import_rva = struct.unpack_from('<I', b, data_dir + 8)[0]
    sections = []
    for index in range(sections_count):
        offset = optional + optional_size + index * 40
        virtual_size, virtual_addr, raw_size, raw_addr = struct.unpack_from('<IIII', b, offset + 8)
        sections.append((virtual_addr, max(virtual_size, raw_size), raw_addr))
    def rva(value: int) -> int:
        for address, size, raw in sections:
            if address <= value < address + size:
                return value - address + raw
        raise ValueError('Unknown PE section')
    if not import_rva:
        return []
    offset = rva(import_rva)
    result = []
    while any(b[offset:offset + 20]):
        name = rva(struct.unpack_from('<I', b, offset + 12)[0])
        result.append(b[name:b.index(b'\0', name)].decode())
        offset += 20
    return result


def bash_files() -> list[Path]:
    names = ('bash sh cat chmod cp cut date diff dirname du echo env expr find grep head '
             'ls mkdir mv printf pwd readlink realpath rm rmdir sed sleep sort tail tee '
             'timeout touch tr uname uniq wc which xargs basename base64 cygpath').split()
    pending = [GIT / 'usr/bin' / (name + '.exe') for name in names]
    result: dict[str, Path] = {}
    while pending:
        file = pending.pop()
        if file.name.lower() in result:
            continue
        if not file.exists():
            raise RuntimeError('Missing bundled shell tool: ' + file.name)
        result[file.name.lower()] = file
        for name in imports(file):
            dependency = GIT / 'usr/bin' / name
            if dependency.exists():
                pending.append(dependency)
    return sorted(result.values())


def profile() -> dict[str, bytes]:
    source = json.loads((PROFILE / 'models.json').read_text(encoding='utf-8-sig'))
    provider = source['providers']['soloapi']
    key = provider.get('apiKey', '')
    if not key or key.startswith(('!', '$')):
        raise RuntimeError('Personal build requires a resolved SoloAPI key in the local profile.')
    # Copy only the intended gateway, never unrelated auth, sessions or skills.
    store = json.loads((PROFILE / 'models-store.json').read_text(encoding='utf-8-sig'))
    solo = store['soloapi']
    if not any(m['id'] == 'solo-auto' and m.get('provider') == 'soloapi' for m in solo['models']):
        raise RuntimeError('Missing provider-qualified default model in cached catalog.')
    encode = lambda obj: (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode()
    return {
        'models.json': encode({'providers': {'soloapi': provider}}),
        'models-store.json': encode({'soloapi': solo}),
        'settings.json': encode({'defaultProvider': 'soloapi', 'defaultModel': 'solo-auto', 'defaultThinkingLevel': 'medium'}),
        'auth.json': b'{}\n',
        'extensions/soloapi-models.ts': (PROFILE / 'extensions/soloapi-models.ts').read_bytes(),
    }


def write_entry(bundle: zipfile.ZipFile, name: str, data: bytes, executable: bool = False) -> None:
    info = zipfile.ZipInfo(name, (2026, 11, 6, 0, 0, 0))
    info.create_system = 3
    info.external_attr = ((stat.S_IFREG | (0o700 if executable else 0o600)) << 16)
    info.compress_type = zipfile.ZIP_DEFLATED
    bundle.writestr(info, data, compresslevel=9)


def node_entries(bundle: zipfile.ZipFile, archive: Path, platform: str) -> None:
    if platform == 'windows':
        with zipfile.ZipFile(archive) as node:
            for entry in node.infolist():
                if entry.is_dir():
                    continue
                relative = entry.filename.split('/', 1)[1]
                write_entry(bundle, 'node/' + relative, node.read(entry), relative.endswith('.exe'))
    else:
        with tarfile.open(archive, 'r:xz') as node:
            members = {item.name: item for item in node.getmembers()}
            for entry in members.values():
                if entry.isdir():
                    continue
                relative = entry.name.split('/', 1)[1]
                if entry.issym():
                    # Preserve npm/npx entrypoints with tiny relocatable shell wrappers.
                    if relative in ('bin/npm', 'bin/npx', 'bin/corepack'):
                        body = ('#!/bin/sh\nexec "$(dirname "$0")/node" "$(dirname "$0")/' + entry.linkname + '" "$@"\n').encode()
                        write_entry(bundle, 'node/' + relative, body, True)
                    continue
                stream = node.extractfile(entry)
                if stream:
                    write_entry(bundle, 'node/' + relative, stream.read(), bool(entry.mode & 0o111))


def linux_tools(bundle: zipfile.ZipFile) -> None:
    assets = [
        ('https://github.com/BurntSushi/ripgrep/releases/download/15.2.0/ripgrep-15.2.0-x86_64-unknown-linux-musl.tar.gz', 'rg'),
        ('https://github.com/sharkdp/fd/releases/download/v10.5.0/fd-v10.5.0-x86_64-unknown-linux-musl.tar.gz', 'fd'),
    ]
    for url, binary in assets:
        file = download(url, BUILD / 'downloads' / url.rsplit('/', 1)[1])
        with tarfile.open(file, 'r:gz') as archive:
            entry = next(item for item in archive.getmembers() if item.name.endswith('/' + binary))
            write_entry(bundle, 'tools/' + binary, archive.extractfile(entry).read(), True)
            for item in archive.getmembers():
                if item.isfile() and 'LICENSE' in item.name.upper():
                    write_entry(bundle, f'licenses/{binary}/' + Path(item.name).name, archive.extractfile(item).read())


def payload(platform: str, personal: dict[str, bytes]) -> Path:
    target = BUILD / ('payload-' + platform + '.zip')
    archive = checked_node(platform)
    print('Packing original Pi + runtime:', platform, flush=True)
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for file in sorted(PI.rglob('*')):
            if file.is_file():
                relative = file.relative_to(PI).as_posix()
                # Windows-installed pi-tui already includes all Linux native modules.
                write_entry(bundle, 'pi/' + relative, file.read_bytes(), file.suffix in ('.node', '.sh'))
        write_entry(bundle, 'bootstrap.mjs', (ROOT / 'runtime/bootstrap.mjs').read_bytes())
        for name, data in personal.items():
            write_entry(bundle, 'provision/' + name, data)
        node_entries(bundle, archive, platform)
        if platform == 'windows':
            for file in bash_files():
                write_entry(bundle, 'bash/usr/bin/' + file.name, file.read_bytes(), True)
            write_entry(bundle, 'licenses/git-for-windows.txt', (GIT / 'LICENSE.txt').read_bytes())
            for name in ('rg.exe', 'fd.exe'):
                write_entry(bundle, 'tools/' + name, (PROFILE / 'bin' / name).read_bytes(), True)
        else:
            linux_tools(bundle)
    print('Payload MiB:', round(target.stat().st_size / 1024**2, 2), flush=True)
    return target


def main() -> None:
    for folder in (BUILD, TOOLS, DIST):
        folder.mkdir(exist_ok=True)
    go = ensure_go()
    personal = profile()
    pi_version = json.loads((PI / 'package.json').read_text())['version']
    if pi_version != '1.3.0':
        raise RuntimeError('Revalidate the runtime bootstrap before changing the Pi version.')
    manifest = {'pi': pi_version, 'node': NODE_VERSION, 'go': GO_VERSION, 'artifacts': []}
    embedded = ROOT / 'launcher/payload.zip'
    try:
        for platform in ('windows', 'linux'):
            source = payload(platform, personal)
            shutil.copyfile(source, embedded)
            filename = 'Pi-SoloAPI-Windows-x64.exe' if platform == 'windows' else 'pi-soloapi-linux-x64'
            output = DIST / filename
            env = dict(os.environ, GOOS=platform, GOARCH='amd64', CGO_ENABLED='0', GOCACHE=str(TOOLS / 'go-cache'))
            subprocess.run([str(go), 'build', '-trimpath', '-ldflags=-s -w', '-o', str(output), './launcher'], cwd=ROOT, env=env, check=True)
            record = {'file': filename, 'bytes': output.stat().st_size, 'sha256': digest(output.read_bytes()), 'payloadSha256': digest(source.read_bytes())}
            manifest['artifacts'].append(record)
            print(filename, round(record['bytes'] / 1024**2, 2), 'MiB', flush=True)
    finally:
        embedded.unlink(missing_ok=True)
    (DIST / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
