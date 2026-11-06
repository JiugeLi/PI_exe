/**
 * SoloAPI provider with live model discovery.
 *
 * Connection settings stay in `~/.pi/agent/models.json`
 * (`providers.soloapi.baseUrl` / `api` / `apiKey` / `compat`); the hand-maintained
 * `models` list is replaced by discovery from `GET <baseUrl>/models`.
 *
 * The discovered catalog is published to Pi's model store, so cache-only
 * startups (`pi --list-models`, `--print`, offline) still see the models.
 *
 * Refresh triggers: interactive startup, `/model`, `/soloapi-models`, and any
 * command that refreshes the model catalog with network access enabled.
 */

import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI, ProviderModelConfig } from "@earendil-works/pi-coding-agent";

const PROVIDER_ID = "soloapi";
const PROVIDER_NAME = "SoloAPI";
const AGENT_DIR = process.env.PI_CODING_AGENT_DIR ?? join(homedir(), ".pi", "agent");
const MODELS_JSON = join(AGENT_DIR, "models.json");
const DEFAULT_BASE_URL = "https://solobuild.cloud/v1";
const DEFAULT_API = "openai-completions";
const DEFAULT_CONTEXT_WINDOW = 272000;
const DEFAULT_MAX_TOKENS = 16384;
const FETCH_TIMEOUT_MS = 20000;

/** Gateway entries that are media/embedding endpoints rather than chat models. */
const NON_CHAT_ID =
	/(?:^|[-_.])(image|images|audio|tts|asr|video|i2v|t2v|s2v|v2v|embed|embedding|rerank|moderation)(?:$|[-_.])/i;

interface SoloProviderConfig {
	baseUrl: string;
	api: string;
	apiKey?: string;
	compat?: unknown;
	headers?: Record<string, string>;
}

interface SoloCatalogModel {
	slug?: string;
	display_name?: string;
	context_window?: number;
	max_context_window?: number;
	max_output_tokens?: number;
	input_modalities?: string[];
	supported_reasoning_levels?: { effort?: string }[];
	supported_in_api?: boolean;
	visibility?: string;
}

interface SoloModelsResponse {
	data?: { id?: string; input_modalities?: string[] }[];
	models?: SoloCatalogModel[];
}

let lastModels: ProviderModelConfig[] | undefined;

function readProviderConfig(): SoloProviderConfig {
	let raw: unknown;
	try {
		raw = JSON.parse(readFileSync(MODELS_JSON, "utf8"));
	} catch {
		raw = undefined;
	}
	const provider = ((raw as { providers?: Record<string, unknown> })?.providers?.[PROVIDER_ID] ?? {}) as Record<string, unknown>;
	const baseUrl = String(provider.baseUrl ?? process.env.SOLOAPI_BASE_URL ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
	return {
		baseUrl,
		api: String(provider.api ?? DEFAULT_API),
		apiKey: typeof provider.apiKey === "string" ? provider.apiKey : undefined,
		compat: provider.compat,
		headers: typeof provider.headers === "object" && provider.headers !== null
			? Object.fromEntries(Object.entries(provider.headers as Record<string, string>)
				.map(([name, value]) => [name, resolveApiKey(value) ?? value])) : undefined,
	};
}

/** Resolve literal keys and `$VAR` / `${VAR}` interpolation (`!command` keys resolve in Pi). */
function resolveApiKey(value: string | undefined): string | undefined {
	if (!value) return undefined;
	if (value.startsWith("!")) return undefined;
	const resolved = value.replace(/\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?/g, (_match, name: string) => process.env[name] ?? "");
	return resolved.trim() || undefined;
}

function toModel(
	entry: SoloCatalogModel,
	declared: { id?: string; input_modalities?: string[] } | undefined,
	config: SoloProviderConfig,
): ProviderModelConfig | undefined {
	const id = entry.slug ?? declared?.id;
	if (!id || NON_CHAT_ID.test(id)) return undefined;
	if (entry.supported_in_api === false || entry.visibility === "hidden") return undefined;

	const modalities = entry.input_modalities ?? declared?.input_modalities ?? ["text"];
	const contextWindow = entry.context_window ?? entry.max_context_window ?? DEFAULT_CONTEXT_WINDOW;
	const efforts = (entry.supported_reasoning_levels ?? [])
		.map((level) => level.effort)
		.filter((effort): effort is string => typeof effort === "string" && effort.length > 0);

	return {
		id,
		name: entry.display_name ?? id,
		api: config.api,
		reasoning: efforts.length > 0,
		input: modalities.includes("image") ? ["text", "image"] : ["text"],
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
		contextWindow,
		maxTokens: Math.min(entry.max_output_tokens ?? DEFAULT_MAX_TOKENS, contextWindow),
		...(config.compat ? { compat: config.compat } : {}),
	} as ProviderModelConfig;
}

async function fetchCatalog(config: SoloProviderConfig, apiKey: string, signal: AbortSignal): Promise<ProviderModelConfig[]> {
	const controller = new AbortController();
	const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
	const combined = AbortSignal.any([signal, controller.signal]);
	try {
		const response = await fetch(`${config.baseUrl}/models`, {
			headers: { ...config.headers, Authorization: `Bearer ${apiKey}`, Accept: "application/json" },
			signal: combined,
		});
		if (!response.ok) throw new Error(`SoloAPI /models returned ${response.status}`);
		const payload = (await response.json()) as SoloModelsResponse;
		const declared = new Map((payload.data ?? []).map((item) => [item.id, item] as const));
		const entries: SoloCatalogModel[] = payload.models?.length
			? payload.models
			: (payload.data ?? []).map((item) => ({ slug: item.id, input_modalities: item.input_modalities }));
		return entries
			.map((entry) => toModel(entry, declared.get(entry.slug ?? ""), config))
			.filter((model): model is ProviderModelConfig => model !== undefined);
	} finally {
		clearTimeout(timeout);
	}
}

export default function (pi: ExtensionAPI) {
	const config = readProviderConfig();

	pi.registerProvider(PROVIDER_ID, {
		name: PROVIDER_NAME,
		baseUrl: config.baseUrl,
		api: config.api as never,
		apiKey: config.apiKey ?? "$SOLOAPI_API_KEY",
		headers: config.headers,
		refreshModels: async (context) => {
			// Restore the catalog persisted by an earlier successful refresh.
			// `context.stored` is already scoped to this provider's store entry.
			const stored = (context.stored?.models ?? []) as unknown as ProviderModelConfig[];
			if (stored.length > 0) lastModels = stored;
			const cached = lastModels ?? [];
			if (!context.allowNetwork || context.signal.aborted) return cached;

			const credential = context.credential as { type?: string; key?: string } | undefined;
			const apiKey = (credential?.type === "api_key" ? credential.key : undefined) ?? resolveApiKey(config.apiKey);
			if (!apiKey) return cached;

			try {
				const models = await fetchCatalog(config, apiKey, context.signal);
				if (context.signal.aborted || models.length === 0) return cached;
				await context.publish({
					persist: {
						models: models.map((model) => ({ ...model, provider: PROVIDER_ID })) as never,
						checkedAt: Date.now(),
					},
					update: () => {
						lastModels = models;
					},
				});
				return models;
			} catch {
				return cached;
			}
		},
	} as never);

	// Keep the persisted catalog fresh for non-interactive runs (`pi -p`, `--list-models`).
	let lastBackgroundRefresh = 0;
	pi.on("session_start", (_event, ctx) => {
		if (Date.now() - lastBackgroundRefresh < 5 * 60_000) return;
		lastBackgroundRefresh = Date.now();
		void ctx.modelRegistry.refresh({ providers: [PROVIDER_ID], allowNetwork: true }).catch(() => {});
	});

	pi.registerCommand("soloapi-models", {
		description: "Refresh the SoloAPI model list from the gateway",
		handler: async (_args, ctx) => {
			const result = await ctx.modelRegistry.refresh({ providers: [PROVIDER_ID], allowNetwork: true, force: true });
			const count = ctx.modelRegistry.getProvider(PROVIDER_ID)?.getModels().length ?? 0;
			const error = result.errors.get(PROVIDER_ID);
			ctx.ui.notify(
				error ? `SoloAPI refresh failed: ${error.message}` : `SoloAPI: ${count} models synced`,
				error ? "warning" : "info",
			);
		},
	});
}
