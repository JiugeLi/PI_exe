# Pi Agent Portable

自带运行环境的原版 Pi 命令行代理。Windows 和 Linux x86_64 分别提供一个可执行文件，不需要额外安装 Node.js 或 Pi。

下载：[Windows](https://github.com/JiugeLi/Pi-Agent-Portable/releases/latest/download/pi-windows-x64.exe) · [Linux](https://github.com/JiugeLi/Pi-Agent-Portable/releases/latest/download/pi-linux-x64) · [版本与校验值](https://github.com/JiugeLi/Pi-Agent-Portable/releases)

## 快速开始

Windows：把 `pi-windows-x64.exe` 放到需要的位置后运行。

Linux：

```bash
chmod +x ./pi-linux-x64
./pi-linux-x64
```

首次启动会显示展开进度，并在程序旁自动生成 `config.json`、中文和英文 README。已有配置不会被覆盖。

### 登录 SoloMux

SoloMux 已内置默认接口地址，无须自己添加提供商：

1. 在 Pi 中输入 `/login solomux`，也可在 `/login` 的 API Key 列表中选择 SoloMux。
2. 粘贴自己的 API Key。
3. 程序自动加载账号可用的对话模型。输入 `/model` 选择模型，默认使用 `solo-auto`。

登录凭据会保存在当前工作区的 `.pi-portable/agent/auth.json` 中，重启后继续使用。`/solomux-models` 可手动刷新模型；重新登录可更换密钥。

### 修改配置

也可打开自动生成的 `config.json`，填写 `apiKey`，重启生效：

```json
{
  "baseUrl": "https://solomux.com/v1",
  "api": "openai-responses",
  "apiKey": "",
  "defaultModel": "solo-auto",
  "thinkingLevel": "medium"
}
```

通常只需填写 `apiKey`。其他字段可保留默认值；`headers`、`compat` 是可选的网关兼容设置。也支持环境变量 `SOLOMUX_API_KEY`，或使用 `PI_PORTABLE_CONFIG` 指定其他配置文件。配置文件中的非空密钥优先；使用 `/login` 管理密钥时保持 `apiKey` 为空。

## 运行位置

Pi 使用启动时的当前目录作为工作目录，保留完整文件和命令权限；当前目录不是沙箱。原有 HOME、SSH、Git 和系统命令仍可使用。

首次启动把自带运行环境展开到工作目录的 `.pi-portable/runtime/`，显示进度条、百分比、文件数、数据量和用时。完成后自动进入 Pi；后续在同一目录直接复用。换到新的工作目录会生成独立的配置、凭据和会话目录。

`config.json` 和两份 README 保存在程序旁。工作区的模型缓存、会话和临时文件保存在 `.pi-portable/`，不修改原来的 `~/.pi/agent`。检查路径和版本可运行 `--portable-diagnostics`，输出不含密钥。

模型调用及刷新列表需要联网。程序不含个人密钥，填写过密钥的配置和凭据文件请勿公开分享。

## 系统要求

- Windows 10 / Windows Server 2016 及以上，x86_64。
- Linux x86_64，glibc >= 2.28，内核 >= 4.18；已有 Bash 和基本命令，不支持 Alpine/musl。
- 程序目录和工作目录可写，有足够磁盘空间用于展开运行环境。
