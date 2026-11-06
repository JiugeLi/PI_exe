# Pi Portable

The original Pi coding agent with a bundled runtime. Separate executables are provided for Windows and Linux x86_64. No additional Node.js or Pi installation is required.

Download: [Windows](https://github.com/JiugeLi/PI_exe/releases/latest/download/pi-windows-x64.exe) · [Linux](https://github.com/JiugeLi/PI_exe/releases/latest/download/pi-linux-x64) · [Releases and checksums](https://github.com/JiugeLi/PI_exe/releases)

## Quick start

Windows: run `pi-windows-x64.exe`.

Linux:

```bash
chmod +x ./pi-linux-x64
./pi-linux-x64
```

On first launch, the app shows extraction progress and creates `config.json`, a Chinese README and an English README beside the executable. Existing configuration files are preserved.

### Sign in to SoloMux

SoloMux is included with its default API endpoint:

1. Enter `/login solomux`, or select SoloMux from `/login` → API key.
2. Paste your API key.
3. Available chat models are loaded automatically. Use `/model` to select one. The default is `solo-auto`.

Login credentials are saved in the current workspace's `.pi-portable/agent/auth.json` and survive restarts. Use `/solomux-models` to refresh the catalog, or sign in again to replace a key.

### Edit configuration

Alternatively, fill `apiKey` in the generated `config.json` and restart:

```json
{
  "baseUrl": "https://solomux.com/v1",
  "api": "openai-responses",
  "apiKey": "",
  "defaultModel": "solo-auto",
  "thinkingLevel": "medium"
}
```

Usually only `apiKey` needs changing. Optional `headers` and `compat` objects support gateway compatibility settings. `SOLOMUX_API_KEY` is also supported. Set `PI_PORTABLE_CONFIG` to use a different configuration file. An explicit nonempty config key takes precedence; leave it empty when managing credentials through `/login`.

## Working directory

Pi uses the directory from which it is launched and retains full file and command permissions. This directory is not a sandbox. Existing HOME, SSH, Git and system tools remain available.

On first launch, the bundled runtime is extracted to `.pi-portable/runtime/` in the working directory. Progress includes a bar, percentage, file count, data size and elapsed time. Pi starts automatically when preparation finishes. Subsequent launches reuse the runtime. A new working directory has its own workspace data, credentials and sessions.

The generated configuration and both READMEs live beside the executable. Workspace caches, sessions and temporary files live under `.pi-portable/`. Your existing `~/.pi/agent` is unchanged. Run `--portable-diagnostics` to inspect paths and versions without displaying credentials.

An internet connection is required for model requests and catalog refreshes. No personal API key is embedded. Do not publicly share configuration or credential files after entering a key.

## Requirements

- Windows 10 / Windows Server 2016 or later, x86_64.
- Linux x86_64, glibc >= 2.28, kernel >= 4.18, with Bash and basic system tools. Alpine/musl is not supported.
- Writable executable and working directories, with enough free space to extract the runtime.
