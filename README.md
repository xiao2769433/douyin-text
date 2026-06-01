# 抖音视频语音文案提取工具 (douyin-text)

从抖音视频中提取**语音内容**（说话人讲了什么），并进行智能整理。

## 功能特点

- ✅ 直接提取视频中的语音内容（非视频描述）
- ✅ Whisper 语音识别，中文准确率高
- ✅ 自动去除语气词和重复词
- ✅ 核心观点提取
- ✅ 6 种视频下载策略自动降级
- ✅ 自动保存完整文案到文件

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 使用
/douyin-text https://v.douyin.com/xxxxx
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `url` | 抖音视频链接 | 必填 |
| `--whisper-model` | Whisper 模型（tiny/base/small/medium/large） | small |
| `--desc` | 仅提取视频描述（不需要下载视频） | 否 |
| `--cookies-browser` | 浏览器 cookies 来源 | chrome |
| `--cookies-file` | cookies.txt 文件路径 | 无 |
| `--no-cookies` | 不使用 cookies | 否 |
| `--update-ytdlp` | 更新 yt-dlp 到最新版 | 否 |

## 提取流程

```
抖音链接
  │
  ▼
① yt-dlp + 浏览器 Cookies              ← 首选
② curl_cffi（Chrome TLS 指纹伪装）     ← 备选
③ curl_cffi 直接请求页面                ← 降级
④ 第三方 API                            ← 降级
⑤ 抖音内部 API                          ← 降级
⑥ Playwright 浏览器自动化               ← 最后手段
  │
  ▼
  下载视频文件
  │
  ▼
  moviepy 提取音频 → Whisper 语音识别 → 文案整理
```

## 输出规则

| 内容长度 | 控制台行为 | 文件保存 |
|----------|-----------|----------|
| ≤ 1000 字 | 完整显示 | 保存完整版 |
| > 1000 字 | 摘要显示 + 文件路径 | 保存完整版 |

## Whisper 模型选择

| 模型 | 大小 | 速度（1分钟视频） | 推荐 |
|------|------|-------------------|------|
| tiny | ~75MB | ~5秒 | 快速测试 |
| base | ~140MB | ~15秒 | 追求速度 |
| **small** | ~461MB | ~30秒 | **默认，平衡** |
| medium | ~1.5GB | ~60秒 | 高精度 |
| large | ~3GB | ~120秒 | 最高精度 |

## 依赖

- openai-whisper
- moviepy
- curl_cffi
- yt-dlp
- requests
- imageio-ffmpeg

## 许可证

MIT License
