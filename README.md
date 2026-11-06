# Pi SoloAPI 便携版

原版 Pi Agent 1.3.0 命令行，自带 Node.js/npm、Pi 依赖和 SoloAPI 模型发现扩展。Windows 版另带 Bash 与基本命令；两端均有 rg、fd，无须另外安装 Pi 或 Node。

## 解压使用

解压对应系统的 ZIP，保留程序旁边的 `pi.config.json`，先填写 `apiKey`。Windows 双击 EXE；Linux x86_64 执行：

```bash
chmod +x ./pi-soloapi-linux-x64
./pi-soloapi-linux-x64
```

配置示例（JSON，不支持注释）：

```json
{
  "baseUrl": "https://solomux.com/v1",
  "api": "openai-responses",
  "apiKey": "",
  "defaultModel": "solo-auto",
  "thinkingLevel": "medium"
}
```

- `baseUrl`：API 地址，通常以 `/v1` 结束。
- `apiKey`：自己的密钥；留空时可使用环境变量 `SOLOAPI_API_KEY`。
- `defaultModel`：启动默认模型；在原版界面中可用 `/model` 临时切换。
- `api`：支持 `openai-responses`、`openai-completions`、`anthropic-messages`。
- `thinkingLevel`：`off`、`minimal`、`low`、`medium`、`high`、`xhigh`，实际支持程度由模型决定。

可选配置 `headers` 和 `compat` 对象用于网关兼容设置。配置每次启动读取，修改后退出重启即可，无须重新打包。配置文件损坏时会报错，不会回退到旧密钥。默认配置位置始终是程序旁边；可用环境变量 `PI_PORTABLE_CONFIG` 指定另一份配置，适合多账号使用。

发布 ZIP 和程序本身不含个人密钥。填过密钥的配置文件应私下保管；发布产品时保留空的 `apiKey`。原先内置个人密钥的旧版本不能作为通用产品包发布。

## 工作目录和权限

工作目录是启动时终端所在目录，程序不会切换到 EXE 所在目录。双击通常以 EXE 目录为工作目录，快捷方式以其“起始位置”为准。配置位置与工作目录可以不同。

首次启动在工作目录的 `.pi-portable/` 展开自带环境，此后复用；首次可能需要等待约一分钟。配置、会话和临时文件均独立保存，不修改原来的 `~/.pi/agent`。密钥通过进程环境传递，不写入新生成的 `models.json`；外置配置是密钥和默认模型的权威来源，重启时覆盖该便携工作区旧的 SoloAPI 登录凭据。

Pi 保留完整文件和命令权限；工作目录不是沙箱。服务器原有 HOME、SSH、Git 配置、系统命令及代理环境仍可使用。模型请求和刷新模型列表需要联网。

`--portable-diagnostics` 显示实际配置路径、工作目录、默认模型和是否已配置密钥，不显示密钥内容。没有密钥也可查看版本、帮助和缓存的模型列表。

## 系统要求

- Windows 10 / Windows Server 2016 及以上，x86_64。
- Linux x86_64，glibc >= 2.28，内核 >= 4.18；系统已有 Bash 和基本命令，不支持 Alpine/musl。
- 工作目录可写，并有足够空间保存展开后的运行文件和会话。

## 构建和验证

Windows 使用 Python 3.10+：

```powershell
python scripts/build.py
node --test tests/config.test.mjs
python scripts/verify_windows.py
```

构建读取本机安装的 Pi 1.3.0 代码及 rg/fd 二进制，配置、模型缓存和扩展从本仓库读取，不导入个人密钥、会话或认证文件。Go 与 Node 从官方源下载并校验 SHA256。Linux rg/fd 使用官方 GitHub 发布文件。

通用产物和 ZIP 位于 `dist/`，ZIP 内有使用说明、空密钥配置及 `SHA256SUMS.txt`。`manifest.json` 记录版本和产物校验值。构建不会自动上传产品包。

实机验证时，用 `PI_PORTABLE_CONFIG` 指向自己的私人配置；Windows 验证脚本默认使用本地忽略目录 `private/pi.config.json`。Linux 将验证脚本和程序放在同一测试目录，提供私人配置后执行 `python3 verify_linux.py`。两个验证脚本都会实际调用 SoloAPI 并执行文件、命令工具，会产生少量模型用量。非交互测试须关闭标准输入。

源码：[JiugeLi/PI_exe](https://github.com/JiugeLi/PI_exe)。

上游：[Pi](https://github.com/earendil-works/pi)、[Node.js](https://nodejs.org/)、[Go](https://go.dev/)、[Git for Windows](https://github.com/git-for-windows/git)、[ripgrep](https://github.com/BurntSushi/ripgrep)、[fd](https://github.com/sharkdp/fd)。上游许可随运行环境保留。
