# Pi Portable

- Personal project; GitHub remote is `JiugeLi/PI_exe`. Switch `gh` to `JiugeLi` before remote operations.
- Ship the original Pi CLI with its dependencies and a bundled Node runtime. Do not substitute a reimplemented agent or silently download runtimes at launch.
- Windows and Linux x86_64 are separate builds. Linux Node requires glibc; do not claim Alpine/musl compatibility.
- Use the launch working directory, never change to the executable directory. Pi data and extracted runtime live in `<cwd>/.pi-portable`; use `PI_CODING_AGENT_DIR` to avoid changing `~/.pi/agent`.
- Preserve original filesystem and command permissions, server HOME, SSH, Git configuration and inherited PATH. Working directory is not a sandbox.
- Build artifacts contain a personal SoloAPI credential. Keep `dist/`, `.build/`, `private/`, `.tools/` and `launcher/payload.zip` ignored and local. Never publish them as GitHub releases or log configuration contents.
- SoloAPI model discovery requires `extensions/soloapi-models.ts` plus a provider-scoped `models-store.json` cache. Cached entries need `provider: "soloapi"`; do not replace discovery with a hard-coded model list.
- Verify cold extraction, repeat launch, original version/help, cached model discovery, real model reply and actual file/shell tools. Label Windows and Linux verification separately.
- Launch the upstream CLI as a separate Node entrypoint to preserve its loader behavior. Windows dynamic imports, if needed elsewhere, require `pathToFileURL`.
- Seed cached rg/fd binaries with exclusive creation; do not overwrite them each launch, since Windows locks executables used by concurrent sessions.
- Noninteractive CLI tests over SSH must set stdin to `DEVNULL` (or redirect `</dev/null`): Pi reads piped stdin until EOF before starting a prompt. An open SSH stdin can look like a hung model request.
