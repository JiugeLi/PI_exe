# Pi SoloAPI 便携版

原版 Pi Agent 1.3.0 命令行，内含 Node.js、Pi 全部 npm 依赖、SoloAPI 模型发现扩展和初始模型缓存。Windows 版还包含 Bash 与常用 Unix 命令；两个版本均含 rg、fd。默认 `soloapi / solo-auto`，使用 `/model` 切换模型。

## 使用

Windows：把 `Pi-SoloAPI-Windows-x64.exe` 放到项目目录后双击。也可以在终端进入目标目录后运行这个 EXE。

Linux x86_64：把 `pi-soloapi-linux-x64` 放到服务器后执行：

```bash
chmod +x ./pi-soloapi-linux-x64
./pi-soloapi-linux-x64
```

终端启动时，工作目录是终端当前目录，即使 EXE 存在别处也不改变。双击时通常是 EXE 所在目录；快捷方式以其“起始位置”为准。可用 `--portable-diagnostics` 查看实际工作目录和运行配置。

首次启动在当前目录的 `.pi-portable/` 中展开自带运行环境，无须下载安装 Node/npm 或 Pi。之后直接复用。模型请求和模型列表刷新仍需联网。

- `.pi-portable/agent/`：SoloAPI 配置、模型列表、设置、会话和扩展。
- `.pi-portable/runtime/`：按内容指纹区分的运行环境。
- `.pi-portable/tmp/`：Pi 使用的临时文件。

Pi 保留完整文件与命令权限。当前目录只是默认工作目录，不是沙箱；原有 HOME、SSH、Git 与 PATH 仍可使用。便携版不修改原来的 `~/.pi/agent`，也不自动复制你原有的聊天记录或个人扩展。

这是含个人 SoloAPI 密钥的专用版本。只应放到自己的可信服务器上；不要将 EXE、Linux 程序或 `.pi-portable/` 加入 Git、公开下载或转发。密钥内置不等于加密保护。

## 系统要求

- Windows 10 / Windows Server 2016 及以上，x86_64。
- Linux x86_64，glibc >= 2.28，内核 >= 4.18，系统已有 Bash 和常用基本命令；不支持 Alpine/musl。
- 当前工作目录可写，磁盘空间应足以容纳展开后的运行环境与会话。
- 这是自带运行环境的单文件入口，启动后会展开文件，不是零落盘程序。Linux 的具体系统兼容性以验收报告为准。

## 构建

在 Windows 上使用 Python 3.10+：

```powershell
python scripts/build.py
python scripts/verify_windows.py
```

构建程序从本机已安装的 `@earendil-works/pi-coding-agent` 1.3.0 和 `.pi/agent` 读取 SoloAPI 专用配置；只复制该 provider，不复制其他账户或会话。Go 工具链和 Node 从官方源下载，并校验 SHA256。Linux rg/fd 使用对应项目的官方 GitHub 发布文件。工具链和下载缓存在 `.tools/`、`.build/`。

产物位于 `dist/`；`manifest.json` 记录版本、字节数和校验值。构建过程不会向 GitHub 上传产物。源代码仓库：[JiugeLi/PI_exe](https://github.com/JiugeLi/PI_exe)。

上游：[Pi](https://github.com/earendil-works/pi)、[Node.js](https://nodejs.org/)、[Go](https://go.dev/)、[Git for Windows](https://github.com/git-for-windows/git)、[ripgrep](https://github.com/BurntSushi/ripgrep)、[fd](https://github.com/sharkdp/fd)。上游许可随运行环境保留。
