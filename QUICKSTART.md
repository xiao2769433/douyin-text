# 快速开始

## 安装

### 方式一：让 Claude Code 自动安装（推荐）

在 Claude Code 中输入：

```
帮我从这个 GitHub 仓库安装 skill：https://github.com/YOUR_USERNAME/douyin-text
```

Claude Code 会自动完成克隆和依赖安装。

### 方式二：手动安装

```bash
# 克隆到 Claude Code skills 目录
git clone https://github.com/YOUR_USERNAME/douyin-text.git ~/.claude/skills/douyin-text

# 安装依赖
cd ~/.claude/skills/douyin-text
pip install -r requirements.txt
```

### 目录位置

| 系统 | 路径 |
|------|------|
| Windows | `C:\Users\<用户名>\.claude\skills\douyin-text` |
| macOS | `~/.claude/skills/douyin-text` |
| Linux | `~/.claude/skills/douyin-text` |

## 使用

在 Claude Code 中直接输入：

```
/douyin-text https://v.douyin.com/xxxxx
```

## 首次使用

首次运行会下载 Whisper small 模型（~461MB），之后自动缓存。

## 可选参数

```bash
# 使用更快的模型
/douyin-text --whisper-model base https://v.douyin.com/xxxxx

# 使用更准的模型
/douyin-text --whisper-model medium https://v.douyin.com/xxxxx

# 仅提取视频描述（不需要下载视频）
/douyin-text --desc https://v.douyin.com/xxxxx

# 指定浏览器 cookies
/douyin-text --cookies-browser edge https://v.douyin.com/xxxxx
```

## 常见问题

### Q: 安装后 `/douyin-text` 没反应？

确认 skill 目录下有 `skill.md` 文件。重启 Claude Code 试试。

### Q: 视频下载失败？

确保浏览器已登录抖音。Chrome 被锁定时用 `--cookies-browser edge`。

### Q: 转录有错误？

用更大模型：`--whisper-model medium`
