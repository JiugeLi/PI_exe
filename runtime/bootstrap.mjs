import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { loadConfig, applyConfig } from './config.mjs';

const runtime = path.dirname(fileURLToPath(import.meta.url));
const state = process.env.PI_PORTABLE_STATE;
if (!state || !path.isAbsolute(state)) throw new Error('Launch through the Pi Portable executable.');
const configFile = process.env.PI_PORTABLE_CONFIG_FILE;
let config;
try { config = loadConfig(configFile); }
catch (error) { console.error(error.message); process.exit(2); }
const agent = path.join(state, 'agent');
const provision = path.join(runtime, 'provision');
fs.mkdirSync(agent, { recursive: true, mode: 0o700 });
const oldExtension = path.join(agent, 'extensions', 'soloapi-models.ts');
if (fs.existsSync(oldExtension)) {
  const migration = path.join(state, 'migrations');
  fs.mkdirSync(migration, { recursive: true, mode: 0o700 });
  fs.renameSync(oldExtension, path.join(migration, `soloapi-models-${Date.now()}.ts`));
}

function seed(source, target) {
  if (fs.statSync(source).isDirectory()) {
    fs.mkdirSync(target, { recursive: true, mode: 0o700 });
    for (const item of fs.readdirSync(source)) seed(path.join(source, item), path.join(target, item));
  } else {
    try { fs.copyFileSync(source, target, fs.constants.COPYFILE_EXCL); fs.chmodSync(target, 0o600); }
    catch (error) { if (error.code !== 'EEXIST') throw error; }
  }
}
seed(provision, agent);
const managedExtension = path.join(agent, 'extensions', 'solomux.ts');
const extensionSource = fs.readFileSync(path.join(provision, 'extensions', 'solomux.ts'));
if (!fs.readFileSync(managedExtension).equals(extensionSource)) {
  const migration = path.join(state, 'migrations');
  fs.mkdirSync(migration, { recursive: true, mode: 0o700 });
  fs.copyFileSync(managedExtension, path.join(migration, `solomux-${Date.now()}.ts`));
  fs.writeFileSync(managedExtension, extensionSource, { mode: 0o600 });
}
applyConfig(config, agent);

const localBin = path.join(agent, 'bin');
fs.mkdirSync(localBin, { recursive: true, mode: 0o700 });
for (const item of fs.readdirSync(path.join(runtime, 'tools'))) {
  const target = path.join(localBin, item);
  // Concurrent sessions can already be executing rg/fd (Windows locks EXEs).
  try {
    fs.copyFileSync(path.join(runtime, 'tools', item), target, fs.constants.COPYFILE_EXCL);
    fs.chmodSync(target, 0o700);
  } catch (error) { if (error.code !== 'EEXIST') throw error; }
}

process.env.PI_CODING_AGENT_DIR = agent;
process.env.PI_PACKAGE_DIR = path.join(runtime, 'pi');
process.env.PI_SKIP_VERSION_CHECK = '1';
process.env.NODE_DISABLE_COMPILE_CACHE = '1';
process.env.NODE_COMPILE_CACHE = path.join(state, 'cache', 'node');
process.env.TEMP = process.env.TMP = process.env.TMPDIR = path.join(state, 'tmp');
fs.mkdirSync(process.env.TMPDIR, { recursive: true, mode: 0o700 });
// Isolate Pi's own data; retain HOME/USERPROFILE so the original tools keep
// full access to the server's SSH keys, Git configuration and installed tools.
const pathKey = Object.keys(process.env).find(k => k.toLowerCase() === 'path') ?? 'PATH';
process.env[pathKey] = [path.join(runtime, 'node'), path.join(runtime, 'node', 'bin'), localBin,
  ...(process.platform === 'win32' ? [path.join(runtime, 'bash', 'usr', 'bin')] : []),
  process.env[pathKey] ?? ''].join(path.delimiter);

const settingsFile = path.join(agent, 'settings.json');
const settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'));
settings.defaultProvider = 'solomux';
settings.defaultModel = config.defaultModel;
settings.defaultThinkingLevel = config.thinkingLevel;
if (process.platform === 'win32') settings.shellPath = path.join(runtime, 'bash', 'usr', 'bin', 'bash.exe');
else delete settings.shellPath;
fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2) + '\n', { mode: 0o600 });

const args = process.argv.slice(2);
if (args[0] === '--portable-diagnostics') {
  let storedKey = false;
  try { storedKey = Boolean(JSON.parse(fs.readFileSync(path.join(agent, 'auth.json'), 'utf8')).solomux?.key); } catch {}
  console.log(JSON.stringify({ platform: process.platform, arch: process.arch,
    cwd: process.cwd(), agentDir: agent, runtime, node: process.version,
    pi: JSON.parse(fs.readFileSync(path.join(runtime, 'pi', 'package.json'), 'utf8')).version,
    provider: settings.defaultProvider, model: settings.defaultModel,
    configFile, apiKeyConfigured: Boolean(config.apiKey || process.env.SOLOMUX_API_KEY || storedKey),
    shell: settings.shellPath ?? '/bin/bash', fullPermissions: true }, null, 2));
} else {
  const cli = path.join(runtime, 'pi', 'dist', 'bundle', 'cli.js');
  // Execute the upstream CLI as Node's own entrypoint, preserving its loader
  // and command-line behavior rather than importing it into our bootstrap.
  const child = spawn(process.execPath, [cli, ...args], { stdio: 'inherit', cwd: process.cwd() });
  process.on('SIGINT', () => {}); // The console also delivers it to the real Pi.
  process.on('SIGTERM', () => child.kill('SIGTERM'));
  child.on('error', () => { console.error('Cannot start the bundled Pi CLI.'); process.exitCode = 1; });
  child.on('exit', (code, signal) => { process.exitCode = code ?? (signal === 'SIGINT' ? 130 : 1); });
}
