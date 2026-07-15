# 小智 AI GitHub 每日 PushPlus ClawBot 推送

这个小项目会每天自动检查 [`78/xiaozhi-esp32`](https://github.com/78/xiaozhi-esp32) 的 GitHub 变化，并通过 PushPlus 的微信 ClawBot 渠道推送中文摘要。

## 功能

- 监控 release、tag、commit、issue、PR。
- 自动识别 README、docs、配置、固件等关键文件变化。
- 命中 `OTA`、`唤醒词`、`语音识别`、`ESP32`、`MCP`、`配置变更` 等关键词时在摘要里提示。
- 没有变化时默认不推送。
- 用 `state.json` 记录上次检查位置，避免重复提醒。

## 使用方法

1. 在 GitHub 创建一个新仓库，例如 `xiaozhi-github-monitor`。
2. 把本目录所有文件上传到仓库根目录。
3. 在 PushPlus 里确认你的消息 token 已经绑定微信 ClawBot 渠道。
4. 打开 GitHub 仓库 `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`。
5. 新增 secret：
   - `PUSHPLUS_TOKEN`：你的 PushPlus 用户 token 或消息 token。
6. 打开 `Actions`，启用 workflow。
7. 手动运行一次 `Daily xiaozhi-esp32 monitor`，可以把 `force_send` 选成 `true` 来强制发一条测试日报。

GitHub Actions 会使用内置的 `GITHUB_TOKEN` 读取 GitHub API，不需要你额外创建 token。

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

## 可选配置

- `TARGET_REPO`：默认 `78/xiaozhi-esp32`。
- `PUSHPLUS_CHANNEL`：默认 `clawbot`，如需改回公众号渠道可设为 `wechat`。
- `INITIAL_LOOKBACK_HOURS`：首次运行时回看最近多少小时，默认 24。
- `WECHAT_WEBHOOK_URL`：企业微信机器人备用通道；只有未配置 `PUSHPLUS_TOKEN` 时才会使用。
