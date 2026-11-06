import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { loadConfig, applyConfig } from '../runtime/config.mjs';

const base = { baseUrl: 'https://example.test/v1', api: 'openai-responses',
  apiKey: 'test-credential-A', defaultModel: 'model-A', thinkingLevel: 'medium' };
function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pi-config-test-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

test('accepts UTF-8 BOM and environment key fallback without mutating the file', t => {
  const file = path.join(fixture(t), 'pi.config.json');
  fs.writeFileSync(file, '\uFEFF' + JSON.stringify({ ...base, apiKey: '' }));
  assert.equal(loadConfig(file, { SOLOAPI_API_KEY: 'test-env-credential' }).apiKey, 'test-env-credential');
  assert.equal(JSON.parse(fs.readFileSync(file, 'utf8').slice(1)).apiKey, '');
});

test('rotation replaces stale auth and uses environment references for keys and headers', t => {
  const dir = fixture(t);
  fs.writeFileSync(path.join(dir, 'auth.json'), JSON.stringify({soloapi: {key: 'obsolete-key'}, other: {type: 'api_key', key: 'other-test-key'}}));
  const env = {};
  applyConfig({ ...base, headers: { 'X-Private': 'test-header-credential' } }, dir, env);
  applyConfig({ ...base, apiKey: 'test-credential-B', defaultModel: 'model-B', headers: {'X-Private': 'new-test-header'} }, dir, env);
  assert.equal(env.PI_PORTABLE_API_KEY, 'test-credential-B');
  assert.equal(env.PI_PORTABLE_HEADER_0, 'new-test-header');
  const generated = fs.readFileSync(path.join(dir, 'models.json'), 'utf8');
  assert(!generated.includes('test-credential-A') && !generated.includes('test-credential-B'));
  assert(!generated.includes('new-test-header'));
  assert.equal(JSON.parse(generated).providers.solomux.apiKey, undefined);
  const auth = JSON.parse(fs.readFileSync(path.join(dir, 'auth.json')));
  assert.equal(auth.soloapi, undefined);
  assert.equal(auth.other.key, 'other-test-key');
  assert(JSON.parse(fs.readFileSync(path.join(dir, 'models-store.json'))).solomux.models.some(m => m.id === 'model-B'));
});

test('changing endpoint discards old catalog capabilities', t => {
  const dir = fixture(t);
  applyConfig(base, dir, {});
  applyConfig({ ...base, baseUrl: 'http://localhost:12345/v1', defaultModel: 'different-model', api: 'openai-completions' }, dir, {});
  const models = JSON.parse(fs.readFileSync(path.join(dir, 'models-store.json'))).solomux.models;
  assert.deepEqual(models.map(m => m.id), ['different-model']);
  assert.equal(models[0].api, 'openai-completions');
});

test('native login survives an empty config key, while an explicit key overrides it', t => {
  const dir = fixture(t);
  fs.writeFileSync(path.join(dir, 'auth.json'), JSON.stringify({ solomux: {type: 'api_key', key: 'native-test-key'} }));
  applyConfig({...base, apiKey: ''}, dir, {});
  assert.equal(JSON.parse(fs.readFileSync(path.join(dir, 'auth.json'))).solomux.key, 'native-test-key');
  applyConfig({...base, apiKey: 'explicit-test-key'}, dir, {});
  assert.equal(JSON.parse(fs.readFileSync(path.join(dir, 'auth.json'))).solomux, undefined);
});

test('a key-only file uses built-in SoloMux defaults', t => {
  const file = path.join(fixture(t), 'config.json');
  fs.writeFileSync(file, JSON.stringify({apiKey:'test-config-key'}));
  const config = loadConfig(file, {});
  assert.equal(config.baseUrl, 'https://solomux.com/v1');
  assert.equal(config.defaultModel, 'solo-auto');
});

test('invalid JSON errors never echo a credential-bearing input fragment', t => {
  const file = path.join(fixture(t), 'pi.config.json');
  fs.writeFileSync(file, '{"apiKey":"test-secret-must-not-be-logged", broken');
  assert.throws(() => loadConfig(file), error => !error.message.includes('test-secret-must-not-be-logged') && error.message.includes('valid JSON'));
  fs.writeFileSync(file, JSON.stringify({...base, baseUrl: 'https://user:password@example.test/v1'}));
  assert.throws(() => loadConfig(file), error => !error.message.includes('password'));
});
