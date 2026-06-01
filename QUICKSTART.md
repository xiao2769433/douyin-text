# 快速开始

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用

```
/douyin-text https://v.douyin.com/xxxxx
```

直接提取视频中的语音文案，展示原始转录和整理后版本。

## 首次使用

首次运行会下载 Whisper small 模型（~461MB），之后自动缓存。

## 可选参数

```bash
# 使用更快的模型（精度略低）
/douyin-text --whisper-model base https://v.douyin.com/xxxxx

# 使用更准的模型（速度较慢）
/douyin-text --whisper-model medium https://v.douyin.com/xxxxx

# 仅提取视频描述（不需要下载视频，速度快）
/douyin-text --desc https://v.douyin.com/xxxxx

# 指定 Edge 浏览器 cookies
/douyin-text --cookies-browser edge https://v.douyin.com/xxxxx
```

## 常见问题

### Q: 视频下载失败？

A: 确保浏览器已登录抖音。如果 Chrome 被锁定，用 `--cookies-browser edge`。

### Q: 转录有错误？

A: 使用更大的模型：`--whisper-model medium`

### Q: 速度太慢？

A: 使用更快的模型：`--whisper-model base`（约快 2 倍）
