# Pi Agent Portable

[中文说明](README.zh-CN.md) · [English guide](README.en.md)

Portable, self-contained builds of the original Pi coding agent for Windows and Linux x86_64. The launcher includes its runtime, shows real extraction progress, and generates `config.json` plus both guides on first launch.

SoloMux is included as a native API-key provider. Run `/login solomux`, enter your key, and available chat models load automatically. You can also enter a key in the generated configuration. No personal credentials are included in the downloads.

## Download

- [Windows x86_64](https://github.com/JiugeLi/Pi-Agent-Portable/releases/latest/download/pi-windows-x64.exe)
- [Linux x86_64](https://github.com/JiugeLi/Pi-Agent-Portable/releases/latest/download/pi-linux-x64)
- [All releases and checksums](https://github.com/JiugeLi/Pi-Agent-Portable/releases)

Linux:

```bash
chmod +x ./pi-linux-x64
./pi-linux-x64
```

The agent starts in your current working directory and keeps full file and command permissions. Windows requires Windows 10 / Server 2016 or later. Linux requires glibc >= 2.28, kernel >= 4.18, Bash and basic system tools; Alpine/musl is not supported.

## Build and test

Build on Windows with Python 3.10+ and an installed `@earendil-works/pi-coding-agent` 1.3.0. The build downloads verified Go and Node archives. Windows shell tools come from the local Git for Windows installation. No local provider credentials are imported into builds.

```powershell
python scripts/build.py
node --test tests/config.test.mjs
python scripts/test_launcher.py
python scripts/audit_release.py
```

Integration checks in `scripts/verify_native.py` verify a real native login, model discovery, restart persistence and the original file/shell tools. They require a private test key and incur model usage. Do not publish test configurations, local runtime directories, or legacy credential-bearing builds.

Pi, Node.js, Git for Windows and other bundled components retain their upstream notices inside the expanded runtime. This project packages Pi; it does not reimplement the agent.
