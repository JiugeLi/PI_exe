"""Audit exact ZIP contents and embedded runtime against private credentials."""
import hashlib
import json
import mmap
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
markers = []
private_config = ROOT / 'private/pi.config.json'
if private_config.exists():
    private = json.loads(private_config.read_text(encoding='utf-8-sig'))
    if private.get('apiKey'):
        markers.append(private['apiKey'].encode())
    for key, value in private.get('headers', {}).items():
        if any(word in key.lower() for word in ('authorization', 'token', 'key')) and len(value) > 10:
            markers.append(value.encode())


def no_credentials(data):
    assert all(marker not in data for marker in markers), 'Private credential found in release input'


manifest = json.loads((DIST / 'manifest.json').read_text())
assert manifest['credentialFree'] is True
for record in manifest['artifacts']:
    assert hashlib.sha256((DIST / record['file']).read_bytes()).hexdigest() == record['sha256']
for platform, binary, folder in [
    ('windows', 'Pi-SoloAPI-Windows-x64.exe', 'Pi-SoloAPI-Windows-x64'),
    ('linux', 'pi-soloapi-linux-x64', 'Pi-SoloAPI-Linux-x64'),
]:
    payload_path = ROOT / '.build' / ('payload-' + platform + '.zip')
    payload = payload_path.read_bytes()
    binary_record = next(x for x in manifest['artifacts'] if x['file'] == binary)
    assert hashlib.sha256(payload).hexdigest() == binary_record['payloadSha256']
    with (DIST / binary).open('rb') as executable, mmap.mmap(executable.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
        assert mapped.find(payload) >= 0, 'Executable does not embed the audited payload'
    with zipfile.ZipFile(payload_path) as bundle:
        assert 'provision/models.json' not in bundle.namelist()
        assert json.loads(bundle.read('provision/auth.json')) == {}
        for item in bundle.infolist():
            no_credentials(bundle.read(item))
    with zipfile.ZipFile(DIST / (folder + '.zip')) as release:
        expected = {folder + '/' + name for name in [binary, 'pi.config.json', 'README.md', 'SHA256SUMS.txt']}
        assert set(release.namelist()) == expected
        config = json.loads(release.read(folder + '/pi.config.json'))
        assert config['apiKey'] == '' and 'headers' not in config
        for item in release.infolist():
            no_credentials(release.read(item))
        for line in release.read(folder + '/SHA256SUMS.txt').decode().splitlines():
            checksum, name = line.split('  ', 1)
            assert hashlib.sha256(release.read(folder + '/' + name)).hexdigest() == checksum
        if platform == 'linux':
            assert (release.getinfo(folder + '/' + binary).external_attr >> 16) & 0o100
report = {'credentialFree': True, 'blankKeyTemplates': True, 'zipContentsAndChecksumsVerified': True,
          'bothEmbeddedPayloadsInspected': True, 'privateCredentialScanPassed': True,
          'linuxExecutablePermissionPreserved': True}
(DIST / 'release-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
