# Pi Portable

- Personal project; GitHub remote is `JiugeLi/PI_exe`. Switch `gh` to `JiugeLi` before remote operations.
- Ship the original Pi CLI with its dependencies and a bundled Node runtime. Do not substitute a reimplemented agent or silently download runtimes at launch.
- Windows and Linux x86_64 are separate builds. Linux Node requires glibc; do not claim Alpine/musl compatibility.
- Use the launch working directory, never change to the executable directory. Pi data and extracted runtime live in `<cwd>/.pi-portable`; use `PI_CODING_AGENT_DIR` to avoid changing `~/.pi/agent`.
- Preserve original filesystem and command permissions, server HOME, SSH, Git configuration and inherited PATH. Working directory is not a sandbox.
- Public executables and release ZIPs must contain no credentials. Never import a home-directory provider/auth file during builds. Keep artifacts/cache ignored; private configs and legacy credential-bearing binaries belong under ignored `private/` and must never be published.
- External `pi.config.json` beside the executable is authoritative and reread each launch; `PI_PORTABLE_CONFIG` overrides its location. Do not resolve it from the working directory. Pass keys/secret headers through environment references, never compile them into payloads or log JSON parse snippets.
- ZIP distributions include the executable, blank-key config, README and SHA256SUMS; verify ZIP extraction, external key/model changes and credential-free payloads before delivery.
- Release checks: `node --test tests/config.test.mjs`, `python scripts/audit_release.py`, Windows ZIP integration via `scripts/verify_windows.py`, Linux ZIP integration via `scripts/verify_linux_zip.py`. The latter needs a private test config outside the ZIP.
- SoloAPI model discovery requires `extensions/soloapi-models.ts` plus a provider-scoped `models-store.json` cache. Cached entries need `provider: "soloapi"`; do not replace discovery with a hard-coded model list.
- Verify cold extraction, repeat launch, original version/help, cached model discovery, real model reply and actual file/shell tools. Label Windows and Linux verification separately.
- Launch the upstream CLI as a separate Node entrypoint to preserve its loader behavior. Windows dynamic imports, if needed elsewhere, require `pathToFileURL`.
- Seed cached rg/fd binaries with exclusive creation; do not overwrite them each launch, since Windows locks executables used by concurrent sessions.
- Noninteractive CLI tests over SSH must set stdin to `DEVNULL` (or redirect `</dev/null`): Pi reads piped stdin until EOF before starting a prompt. An open SSH stdin can look like a hung model request.
