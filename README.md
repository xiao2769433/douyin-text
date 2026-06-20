# 抖音视频语音文案提取 (douyin-text)

一个 Claude Code Skill，从抖音视频中提取**语音内容**（说话人讲了什么）：Python 负责下载视频和 Whisper 原始转录，Claude Code 负责动态校对、自然分段、核心观点提炼，并一次性生成最终 Markdown 文档。

## ✨ 功能

- 🎤 提取视频中的语音内容（Whisper 语音识别）
- 🧠 Claude 动态校对 ASR 识别错误（人名、地名、诗词、专有名词等）
- 📑 按语义自然分段，去除口癖、重复、无意义语气词
- 💡 Claude 重新提炼 3-5 条核心观点
- 🔄 6 种视频下载策略自动降级
- 💾 一次性生成最终 Markdown 成品文档（不留半成品）

## 📦 安装

### 方式一：让 Claude Code 自动安装（推荐）

在 Claude Code 中输入：

```
帮我从这个 GitHub 仓库安装 skill：https://github.com/YOUR_USERNAME/douyin-text
```

Claude Code 会自动克隆仓库、安装依赖、配置 skill。

### 方式二：手动安装

```bash
# 1. 克隆仓库到 Claude Code 的 skills 目录
git clone https://github.com/xiao2769433/douyin-text.git ~/.claude/skills/douyin-text

# 2. 安装 Python 依赖
cd ~/.claude/skills/douyin-text
pip install -r requirements.txt
```

> **目录说明**：
> - Windows: `C:\Users\<你的用户名>\.claude\skills\douyin-text`
> - macOS/Linux: `~/.claude/skills/douyin-text`

### 3. 验证安装

在 Claude Code 中输入：

```
/douyin-text
```

如果看到帮助信息，说明安装成功。

## 🚀 使用

### 作为 Claude Code Skill 使用（推荐）

在 Claude Code 中直接输入：

```
/douyin-text https://v.douyin.com/xxxxx
```

Skill 内部会调用 `python extract.py --raw-json <url>`，由 Claude 完成校对和文档生成。详见 `skill.md`。

### 作为命令行工具使用

```bash
# 默认：旧版完整流程（Python 同时做转录和机械整理，并直接保存 Markdown）
python extract.py https://v.douyin.com/xxxxx

# 仅输出原始转录的 JSON（Claude Code Skill 模式使用，不生成 Markdown）
python extract.py --raw-json https://v.douyin.com/xxxxx

# 仅提取视频描述（不需要下载视频）
python extract.py --desc https://v.douyin.com/xxxxx

# 使用更大的模型（更准确）
python extract.py --whisper-model medium https://v.douyin.com/xxxxx

# 指定浏览器 cookies
python extract.py --cookies-browser edge https://v.douyin.com/xxxxx
```

> 默认模式（不带 `--raw-json`）仍保留旧行为，便于命令行直接使用。
> Claude Code Skill 走 `--raw-json` 流程，由 Claude 一次性生成最终文档。

## 📖 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `url` | 抖音视频链接 | 必填 |
| `--whisper-model` | Whisper 模型（tiny/base/small/medium/large） | small |
| `--raw-json` | 只输出原始转录 JSON，不生成 Markdown（Claude Code Skill 用） | 否 |
| `--desc` | 仅提取视频描述（不需要下载视频） | 否 |
| `--cookies-browser` | 浏览器 cookies 来源 | chrome |
| `--cookies-file` | cookies.txt 文件路径 | 无 |
| `--no-cookies` | 不使用 cookies | 否 |
| `--update-ytdlp` | 更新 yt-dlp 到最新版 | 否 |

## 📊 输出格式

### Claude Code Skill 模式（`--raw-json`）

Python 输出纯 JSON 到 stdout：

```json
{
  "url": "https://v.douyin.com/xxxxx",
  "author": "作者昵称",
  "description": "视频描述文字",
  "transcription_raw": "Whisper 原始转录全文（含换行）",
  "error": null
}
```

Claude 解析此 JSON 后一次性生成最终 Markdown 文件，结构如下：

```
📹 抖音视频语音文案
══════════════════════════════════════

🔗 链接：https://v.douyin.com/xxxxx
👤 作者：@username
📝 视频描述：xxx

══════════════════════════════════════
🎤 原始语音转录（XXX 字）
────────────────────────────────────
[Whisper 原始转录，保持不动]

══════════════════════════════════════
✨ 整理后文案
────────────────────────────────────
[Claude 校对、自然分段后的版本]

══════════════════════════════════════
💡 核心观点
────────────────────────────────────
1. 观点一
2. 观点二
3. 观点三

══════════════════════════════════════
```

### 命令行默认模式（旧版）

Python 直接生成完整 Markdown 并保存到 `output/`，包含原始转录、机械整理后的文案、关键词触发的核心观点。

## ⚙️ 依赖

### Python 包

```
pip install -r requirements.txt
```

### 系统依赖

- **ffmpeg** — 音视频处理（moviepy 依赖）
  - Windows: `pip install imageio-ffmpeg`（已包含在 requirements.txt）
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

## 🔧 Whisper 模型选择

| 模型 | 大小 | 速度（1分钟视频） | 推荐场景 |
|------|------|-------------------|----------|
| tiny | ~75MB | ~5秒 | 快速测试 |
| base | ~140MB | ~15秒 | 追求速度 |
| **small** | ~461MB | ~30秒 | **默认推荐** |
| medium | ~1.5GB | ~60秒 | 高精度 |
| large | ~3GB | ~120秒 | 最高精度 |

首次使用会自动下载模型，之后缓存在本地。

## ❓ 常见问题

### Q: 安装后输入 `/douyin-text` 没反应？

A: 确认 skill 目录路径正确，且目录下有 `skill.md` 文件。

### Q: 视频下载失败？

A: 确保浏览器已登录抖音。如果 Chrome 被锁定，用 `--cookies-browser edge`。

### Q: 转录结果有错误？

A: 使用更大的模型：`--whisper-model medium`

### Q: 支持哪些链接格式？

A: 支持 `https://v.douyin.com/xxxxx` 和 `https://www.douyin.com/video/xxxxx`

## 📄 许可证

MIT License
