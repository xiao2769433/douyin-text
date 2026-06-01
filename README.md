# 抖音视频语音文案提取 (douyin-text)

一个 Claude Code Skill，从抖音视频中提取**语音内容**（说话人讲了什么），并进行智能整理。

## ✨ 功能

- 🎤 提取视频中的语音内容（Whisper 语音识别）
- ✨ 自动去除语气词、重复词
- 💡 核心观点自动提取
- 🔄 6 种视频下载策略自动降级
- 💾 自动保存完整文案到文件

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
git clone https://github.com/YOUR_USERNAME/douyin-text.git ~/.claude/skills/douyin-text

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

### 作为命令行工具使用

```bash
# 提取语音文案（默认）
python extract.py https://v.douyin.com/xxxxx

# 仅提取视频描述（不需要下载视频）
python extract.py --desc https://v.douyin.com/xxxxx

# 使用更大的模型（更准确）
python extract.py --whisper-model medium https://v.douyin.com/xxxxx

# 指定浏览器 cookies
python extract.py --cookies-browser edge https://v.douyin.com/xxxxx
```

## 📖 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `url` | 抖音视频链接 | 必填 |
| `--whisper-model` | Whisper 模型（tiny/base/small/medium/large） | small |
| `--desc` | 仅提取视频描述（不需要下载视频） | 否 |
| `--cookies-browser` | 浏览器 cookies 来源 | chrome |
| `--cookies-file` | cookies.txt 文件路径 | 无 |
| `--no-cookies` | 不使用 cookies | 否 |
| `--update-ytdlp` | 更新 yt-dlp 到最新版 | 否 |

## 📊 输出格式

```
📹 抖音视频语音文案
══════════════════════════════════════

🔗 链接：https://v.douyin.com/xxxxx
👤 作者：@username
📝 视频描述：xxx

══════════════════════════════════════
🎤 原始语音转录（XXX 字）
────────────────────────────────────
[Whisper 转录的原始内容]

══════════════════════════════════════
✨ 整理后文案
────────────────────────────────────
[去除语气词、重复词后的版本]

══════════════════════════════════════
💡 核心观点
────────────────────────────────────
1. 观点一
2. 观点二

══════════════════════════════════════
📄 完整文案已保存: ./output/douyin_xxx.md
```

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
