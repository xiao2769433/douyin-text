---
name: douyin-text
description: 从抖音视频中提取语音文案，展示优化前后对比
user-invocable: true
---

# 抖音视频语音文案提取

从抖音视频中提取**语音内容**（说话人讲了什么），并进行智能整理。

## 安装

### 方式一：让 Claude Code 自动安装

在 Claude Code 中输入：

```
帮我从这个 GitHub 仓库安装 skill：https://github.com/YOUR_USERNAME/douyin-text
```

### 方式二：手动安装

```bash
git clone https://github.com/YOUR_USERNAME/douyin-text.git ~/.claude/skills/douyin-text
cd ~/.claude/skills/douyin-text
pip install -r requirements.txt
```

## 使用方法

```
/douyin-text <抖音视频链接>
```

## 参数

- `url`：抖音视频链接（必填）
  - 支持格式：`https://v.douyin.com/xxxxx`、`https://www.douyin.com/video/xxxxx`
- `--whisper-model`：Whisper 模型大小（tiny/base/small/medium/large，默认 small）
- `--desc`：仅提取视频描述文字（不需要下载视频）
- `--cookies-browser`：从浏览器导入 cookies（默认 chrome）
- `--cookies-file`：使用 cookies.txt 文件
- `--no-cookies`：不使用 cookies
- `--update-ytdlp`：更新 yt-dlp

## 使用示例

```
/douyin-text https://v.douyin.com/abc123
```

## 输出格式

控制台和保存文件格式一致：

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

## 输出规则

| 内容长度 | 控制台行为 | 文件保存 |
|----------|-----------|----------|
| ≤ 1000 字 | 完整显示全部内容 | 保存完整版 |
| > 1000 字 | 原始转录前 3 段 + 整理文案前 300 字 + 核心观点完整 | 保存完整版 |

## 故障排除

| 错误信息 | 原因 | 解决方案 |
|----------|------|----------|
| whisper 未安装 | 缺少依赖 | `pip install openai-whisper` |
| moviepy 未安装 | 缺少依赖 | `pip install moviepy` |
| 视频下载失败 | 反爬限制 | 确保浏览器已登录抖音 |
| 找不到 ffmpeg | 系统依赖缺失 | macOS: `brew install ffmpeg`，Linux: `sudo apt install ffmpeg` |

## 注意事项

- 仅支持公开可见的视频
- 首次使用会下载 Whisper 模型（~461MB）
- CPU 模式下 small 模型处理 1 分钟视频约 30 秒
- 提取的文案仅供个人学习使用
