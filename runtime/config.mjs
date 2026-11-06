import fs from 'node:fs';
import path from 'node:path';

function invalid(message) { throw new Error(`Pi configuration: ${message}`); }

export function loadConfig(filename, env = process.env) {
  let config;
  try { config = JSON.parse(fs.readFileSync(filename, 'utf8').replace(/^\uFEFF/, '')); }
  catch { invalid('cannot read valid JSON; edit config.json beside the executable.'); }
  if (!config || typeof config !== 'object' || Array.isArray(config)) invalid('expected a JSON object.');
  config = { baseUrl: 'https://solomux.com/v1', api: 'openai-responses', apiKey: '',
    defaultModel: 'solo-auto', thinkingLevel: 'medium', ...config };
  let url;
  try { url = new URL(config.baseUrl); } catch { invalid('baseUrl must be an HTTP or HTTPS URL.'); }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    invalid('baseUrl must be an HTTP or HTTPS URL without credentials, query or fragment.');
  }
  if (!['openai-responses', 'openai-completions', 'anthropic-messages'].includes(config.api)) invalid('unsupported api.');
  if (typeof config.apiKey !== 'string') invalid('apiKey must be a string (empty is allowed before setup).');
  if (typeof config.defaultModel !== 'string' || !config.defaultModel.trim()) invalid('defaultModel must be a nonempty string.');
  const thinking = config.thinkingLevel ?? 'medium';
  if (!['off', 'minimal', 'low', 'medium', 'high', 'xhigh'].includes(thinking)) invalid('unsupported thinkingLevel.');
  for (const field of ['headers', 'compat']) {
    if (config[field] !== undefined && (!config[field] || typeof config[field] !== 'object' || Array.isArray(config[field]))) invalid(`${field} must be an object.`);
  }
  if (config.headers && Object.values(config.headers).some(v => typeof v !== 'string')) invalid('header values must be strings.');
  return { ...config, baseUrl: config.baseUrl.replace(/\/+$/, ''), defaultModel: config.defaultModel.trim(),
    thinkingLevel: thinking, apiKey: config.apiKey.trim() };
}

export function applyConfig(config, agent, env = process.env) {
  env.PI_PORTABLE_API_KEY = config.apiKey;
  const headers = {};
  for (const [index, [name, value]] of Object.entries(config.headers ?? {}).entries()) {
    const variable = `PI_PORTABLE_HEADER_${index}`;
    env[variable] = value;
    headers[name] = '${' + variable + '}';
  }
  const provider = { baseUrl: config.baseUrl, api: config.api,
    ...(config.compat ? { compat: config.compat } : {}), ...(Object.keys(headers).length ? { headers } : {}) };
  let previous;
  try { const providers = JSON.parse(fs.readFileSync(path.join(agent, 'models.json'), 'utf8')).providers; previous = providers?.solomux ?? providers?.soloapi; } catch {}
  let store = {};
  try { store = JSON.parse(fs.readFileSync(path.join(agent, 'models-store.json'), 'utf8')); } catch {}
  if (previous && (previous.baseUrl !== provider.baseUrl || previous.api !== provider.api)) store = {};
  const previousStore = store.solomux ?? store.soloapi;
  const models = previousStore?.models ?? [];
  if (!models.some(m => m.id === config.defaultModel)) {
    // A conservative startup fallback only; the extension replaces it with
    // the gateway's discovered capabilities on refresh.
    models.push({ id: config.defaultModel, name: config.defaultModel, provider: 'solomux', api: config.api,
      reasoning: false, input: ['text'], cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow: 32000, maxTokens: 4096 });
  }
  for (const model of models) { model.api = config.api; model.provider = 'solomux'; model.baseUrl = config.baseUrl; if (config.compat) model.compat = config.compat; }
  store.solomux = { ...(previousStore ?? {}), models };
  delete store.soloapi;
  const write = (name, value) => fs.writeFileSync(path.join(agent, name), JSON.stringify(value, null, 2) + '\n', { mode: 0o600 });
  write('models.json', { providers: { solomux: provider } });
  write('models-store.json', store);
  // Keep normal /login credentials when the generated config key is empty.
  // An explicitly configured key remains authoritative after a restart.
  let auth = {};
  try { auth = JSON.parse(fs.readFileSync(path.join(agent, 'auth.json'), 'utf8')); } catch {}
  if (!auth.solomux && auth.soloapi && !config.apiKey) auth.solomux = auth.soloapi;
  if (config.apiKey) delete auth.solomux;
  delete auth.soloapi;
  write('auth.json', auth);
}
