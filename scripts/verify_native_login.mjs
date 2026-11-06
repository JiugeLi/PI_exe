import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';
const [infoFile, privateFile] = process.argv.slice(2);
const info = JSON.parse(fs.readFileSync(infoFile, 'utf8'));
const key = JSON.parse(fs.readFileSync(privateFile, 'utf8').replace(/^\uFEFF/, '')).apiKey;
assert(key);
process.env.PI_CODING_AGENT_DIR = info.agentDir;
process.env.PI_PACKAGE_DIR = path.join(info.runtime, 'pi');
delete process.env.PI_PORTABLE_API_KEY;
const { createAgentSession, SessionManager } = await import(pathToFileURL(path.join(info.runtime, 'pi/dist/index.js')).href);
const { session, extensionsResult } = await createAgentSession({ cwd: info.cwd, agentDir: info.agentDir,
  sessionManager: SessionManager.inMemory(info.cwd), noTools: 'all' });
try {
  if (extensionsResult.errors.length) console.error(JSON.stringify(extensionsResult.errors).replaceAll(key, '[REDACTED]'));
  assert.equal(extensionsResult.errors.length, 0, 'Provider extension failed to load');
  const provider = session.modelRuntime.getProvider('solomux');
  assert.equal(provider.name, 'SoloMux');
  assert.equal(typeof provider.auth.apiKey.login, 'function');
  let secretPrompt = false;
  await session.modelRuntime.login('solomux', 'api_key', {
    signal: new AbortController().signal,
    prompt: async prompt => { assert.equal(prompt.type, 'secret'); secretPrompt = true; return key; },
    notify: () => {},
  });
  assert(secretPrompt);
  const models = session.modelRuntime.getProvider('solomux').getModels();
  assert(models.length > 0 && models.some(m => m.id === 'solo-auto'));
  const config = JSON.parse(fs.readFileSync(info.configFile, 'utf8'));
  const response = await fetch(config.baseUrl.replace(/\/+$/, '') + '/models', {
    headers: {Authorization: 'Bearer ' + key}, signal: AbortSignal.timeout(20000) });
  assert(response.ok);
  const advertised = await response.json();
  const chatIds = (advertised.data ?? []).map(m => m.id)
    .filter(id => !/(?:^|[-_.])(image|images|audio|tts|asr|video|i2v|t2v|s2v|v2v|embed|embedding|rerank|moderation)(?:$|[-_.])/i.test(id));
  assert(chatIds.every(id => models.some(m => m.id === id)), 'An available chat model is missing');
  const saved = JSON.parse(fs.readFileSync(path.join(info.agentDir, 'auth.json'), 'utf8'));
  assert.equal(saved.solomux.type, 'api_key');
  assert(saved.solomux.key === key, 'Native login credential was not persisted');
  const cache = JSON.parse(fs.readFileSync(path.join(info.agentDir, 'models-store.json'), 'utf8'));
  assert(cache.solomux.models.length >= models.length);
  console.log(JSON.stringify({ nativeApiKeyLogin: true, secretPromptVerified: true,
    modelsLoadedImmediately: models.length, advertisedChatModelsMatched: true, credentialPersisted: true }));
} finally { session.dispose(); }
