# 小智 AI GitHub 每日 PushPlus ClawBot 推送

这个小项目会每天自动检查 [`78/xiaozhi-esp32`](https://github.com/78/xiaozhi-esp32) 的 GitHub 变化，并通过 PushPlus 的微信 ClawBot 渠道推送中文摘要。配置 DeepSeek API Key 后，会先生成一段“普通人能看懂”的 AI 通俗总结，再附上技术明细。

## 功能

- 监控 release、tag、commit、issue、PR。
- 自动识别 README、docs、配置、固件等关键文件变化。
- 命中 `OTA`、`唤醒词`、`语音识别`、`ESP32`、`MCP`、`配置变更` 等关键词时在摘要里提示。
- 可选调用 DeepSeek，把技术变更整理成“新增了什么、改变了什么、要注意什么”。
- 没有变化时默认不推送。
- 用 `state.json` 记录上次检查位置，避免重复提醒。

## 使用方法

1. 在 GitHub 创建一个新仓库，例如 `xiaozhi-github-monitor`。
2. 把本目录所有文件上传到仓库根目录。
3. 在 PushPlus 里确认你的消息 token 已经绑定微信 ClawBot 渠道。
4. 打开 GitHub 仓库 `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`。
5. 新增 secret：
   - `PUSHPLUS_TOKEN`：你的 PushPlus 用户 token 或消息 token。
   - `DEEPSEEK_API_KEY`：你的 DeepSeek API Key。可选，但配置后日报会更通俗。
6. 打开 `Actions`，启用 workflow。
7. 手动运行一次 `Daily xiaozhi-esp32 monitor`，可以把 `force_send` 选成 `true` 来强制发一条测试日报。

GitHub Actions 会使用内置的 `GITHUB_TOKEN` 读取 GitHub API，不需要你额外创建 token。

## AI 总结

如果配置了 `DEEPSEEK_API_KEY`，推送内容会变成：

1. AI 通俗总结：用几句话说明新增功能、行为变化、修复内容和需要关注的地方。
2. 技术明细：保留 commit、PR、issue、关键文件链接，方便你想深入时点开看。

默认模型是 `deepseek-v4-flash`。如果想换模型，可以在 GitHub 仓库 `Settings` -> `Secrets and variables` -> `Actions` -> `Variables` 里新增：

- `DEEPSEEK_MODEL`：例如 `deepseek-v4-flash` 或 `deepseek-v4-pro`。

如果 DeepSeek 调用失败，脚本会自动回退到原来的技术日报，不会中断 PushPlus 推送。

## 推送时间

默认每天香港/北京时间 09:00 推送，对应 workflow 里的 UTC 时间：

```yaml
cron: "0 1 * * *"
```

如果想改成北京时间 21:00，把它改成：

```yaml
cron: "0 13 * * *"
```

## 本地测试

只打印摘要、不推送：

```bash
python monitor.py --dry-run --force-send
```

真实发送到 PushPlus ClawBot：

```bash
PUSHPLUS_TOKEN=你的token python monitor.py --force-send
```

Windows PowerShell：

```powershell
$env:PUSHPLUS_TOKEN="你的token"
python monitor.py --force-send
```

测试 AI 总结：

```powershell
$env:PUSHPLUS_TOKEN="你的pushplus-token"
$env:DEEPSEEK_API_KEY="你的deepseek-api-key"
python monitor.py --force-send
```

## 可选配置

- `TARGET_REPO`：默认 `78/xiaozhi-esp32`。
- `PUSHPLUS_CHANNEL`：默认 `clawbot`，如需改回公众号渠道可设为 `wechat`。
- `DEEPSEEK_API_KEY`：可选，配置后启用 AI 通俗总结。
- `DEEPSEEK_MODEL`：可选，默认 `deepseek-v4-flash`。
- `OPENAI_API_KEY` / `OPENAI_MODEL`：备用 OpenAI 通道；只有未配置 `DEEPSEEK_API_KEY` 时才会使用。
- `INITIAL_LOOKBACK_HOURS`：首次运行时回看最近多少小时，默认 24。
- `WECHAT_WEBHOOK_URL`：企业微信机器人备用通道；只有未配置 `PUSHPLUS_TOKEN` 时才会使用。
