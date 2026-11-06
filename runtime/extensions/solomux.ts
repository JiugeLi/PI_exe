import { readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import type { ExtensionAPI } from '@earendil-works/pi-coding-agent';

const ID = 'solomux';
const agentDir = process.env.PI_CODING_AGENT_DIR ?? join(homedir(), '.pi', 'agent');
const NON_CHAT = /(?:^|[-_.])(image|images|audio|tts|asr|video|i2v|t2v|s2v|v2v|embed|embedding|rerank|moderation)(?:$|[-_.])/i;
const resolve = (value: string) => value.replace(/\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?/g, (_m, name) => process.env[name] ?? '');

export default async function (pi: ExtensionAPI) {
  // Pi's extension aliases map pi-ai to its compatibility entrypoint, including
  // prefix matches. Resolve native API subpaths from the bundled package instead.
  const load = (file: string) => import(pathToFileURL(join(process.env.PI_PACKAGE_DIR!, 'node_modules', '@earendil-works', 'pi-ai', 'dist', file)).href);
  const { createProvider, envApiKeyAuth } = await load('index.js');
  const { openAIResponsesApi } = await load('api/openai-responses.lazy.js');
  const { openAICompletionsApi } = await load('api/openai-completions.lazy.js');
  const { anthropicMessagesApi } = await load('api/anthropic-messages.lazy.js');
  const config = JSON.parse(readFileSync(join(agentDir, 'models.json'), 'utf8')).providers.solomux;
  const headers = Object.fromEntries(Object.entries(config.headers ?? {}).map(([k, v]) => [k, resolve(String(v))]));
  let pending: { key: string; models: any[] } | undefined;

  async function discover(key: string, signal: AbortSignal) {
    const response = await fetch(`${config.baseUrl}/models`, { headers: { ...headers, Authorization: `Bearer ${key}` },
      signal: AbortSignal.any([signal, AbortSignal.timeout(20000)]) });
    if (!response.ok) throw new Error(`SoloMux model discovery returned HTTP ${response.status}`);
    const body = await response.json() as any;
    const metadata = new Map((body.models ?? []).map((m: any) => [m.slug ?? m.id, m]));
    const entries = new Map<string, any>();
    for (const m of body.data ?? []) if (m.id) entries.set(m.id, { ...m, ...metadata.get(m.id), id: m.id });
    for (const m of body.models ?? []) { const id = m.slug ?? m.id; if (id && !entries.has(id)) entries.set(id, { ...m, id }); }
    const models = [...entries.values()].filter(m => !NON_CHAT.test(m.id) && m.supported_in_api !== false && m.visibility !== 'hidden')
      .map(m => ({ id: m.id, name: m.display_name ?? m.id, provider: ID, baseUrl: config.baseUrl, api: config.api,
        reasoning: Boolean(m.supported_reasoning_levels?.length),
        input: (m.input_modalities ?? ['text']).includes('image') ? ['text', 'image'] : ['text'],
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: m.context_window ?? m.max_context_window ?? 272000,
        maxTokens: Math.min(m.max_output_tokens ?? 16384, m.context_window ?? m.max_context_window ?? 272000),
        ...(config.compat ? { compat: config.compat } : {}) }));
    if (!models.length) throw new Error('SoloMux returned no compatible chat models for this key.');
    return models;
  }

  // The same native API-key authentication used by providers such as DeepSeek.
  const standardAuth = envApiKeyAuth('SoloMux API key', ['PI_PORTABLE_API_KEY', 'SOLOMUX_API_KEY']);
  const auth = { ...standardAuth, login: async (interaction: any) => {
    const credential = await standardAuth.login!(interaction);
    if (!credential.key?.trim()) throw new Error('An API key is required.');
    credential.key = credential.key.trim();
    interaction.notify({ type: 'progress', message: 'Loading SoloMux models...' });
    pending = { key: credential.key, models: await discover(credential.key, interaction.signal) };
    interaction.notify({ type: 'progress', message: `Loaded ${pending.models.length} SoloMux models.` });
    return credential;
  } };
  const api = config.api === 'openai-completions' ? openAICompletionsApi()
    : config.api === 'anthropic-messages' ? anthropicMessagesApi() : openAIResponsesApi();
  const provider = createProvider({ id: ID, name: 'SoloMux', baseUrl: config.baseUrl, headers,
    auth: { apiKey: auth }, models: [], api,
    fetchModels: async context => {
      const key = context.credential?.type === 'api_key' ? context.credential.key : undefined;
      const effective = key ?? process.env.PI_PORTABLE_API_KEY ?? process.env.SOLOMUX_API_KEY;
      if (!effective) return context.stored?.models ?? [];
      if (pending?.key === effective) { const models = pending.models; pending = undefined; return models; }
      return discover(effective, context.signal);
    },
  });
  const refresh = provider.refreshModels!.bind(provider);
  provider.refreshModels = async context => {
    // Login already downloaded this catalog. Publish that in-memory result
    // during Pi's credential synchronization, without another network request.
    const prefetched = pending && context.credential?.type === 'api_key' && pending.key === context.credential.key;
    return refresh(prefetched ? { ...context, allowNetwork: true } : context);
  };
  pi.registerProvider(provider);
  pi.on('session_start', (_event, ctx) => {
    void ctx.modelRegistry.refresh({ providers: [ID], allowNetwork: true }).catch(() => {});
  });
  pi.registerCommand('solomux-models', { description: 'Refresh available SoloMux models', handler: async (_args, ctx) => {
    const result = await ctx.modelRegistry.refresh({ providers: [ID], allowNetwork: true, force: true });
    const error = result.errors.get(ID);
    const count = ctx.modelRegistry.getProvider(ID)?.getModels().length ?? 0;
    ctx.ui.notify(error ? 'SoloMux model refresh failed; check your key and connection.' : `SoloMux: ${count} models loaded`, error ? 'warning' : 'info');
  } });
}
