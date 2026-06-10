#!/usr/bin/env python3
"""
抖音视频文案提取脚本
从抖音视频链接中提取文案内容，并进行智能整理
"""

import sys
import os
import re
import json
import time
import random
import shutil
import subprocess
import tempfile
import requests
from typing import Optional, Dict, Any

# 尝试导入 curl_cffi（Chrome TLS 指纹伪装）
try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

# 尝试导入 whisper（语音识别）并确保 ffmpeg 可用
try:
    # 将 imageio-ffmpeg 的 ffmpeg 添加到 PATH（whisper 依赖 ffmpeg）
    try:
        import imageio_ffmpeg
        _ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
        if _ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    except ImportError:
        pass
    import whisper
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

# 尝试导入 moviepy（音频提取）
try:
    from moviepy import VideoFileClip
    HAS_MOVIEPY = True
except ImportError:
    HAS_MOVIEPY = False

# 尝试导入 Playwright（可选）
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


# 跨平台默认浏览器检测
def _default_browser() -> str:
    if sys.platform == "darwin":
        return "safari"
    return "chrome"


# 配置
CONFIG = {
    "headers": {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.douyin.com/",
        "Upgrade-Insecure-Requests": "1",
    },
    "mobile_headers": {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    },
    "timeout": 20,
    "retry_times": 3,
    "retry_delay": 3,
    # yt-dlp cookies 配置
    "yt_dlp_cookies_browser": _default_browser(),
    "yt_dlp_cookies_file": None,
}

# 语气词和填充词列表
FILLER_WORDS = [
    "嗯", "啊", "呃", "额", "那个", "就是", "然后", "所以说",
    "对吧", "是不是", "对不对", "知道吗", "明白吗",
    "然后呢", "所以说呢", "这个", "那个", "就是说",
    "啊对", "嗯对", "对对对", "是是是",
]
# 预编译为单个正则（按长度降序，避免短词匹配长词的子串）
_FILLER_PATTERN = re.compile(
    "|".join(re.escape(w) for w in sorted(FILLER_WORDS, key=len, reverse=True)),
    re.IGNORECASE,
)

# 重复模式正则
REPEAT_PATTERNS = [
    r"(.)\1{2,}",  # 连续重复3次以上的字符
    r"(\w{2,})\1{1,}",  # 连续重复的词语
]

# 高置信度 ASR 误识别修正规则（只做短语级替换，避免过度纠错）
ASR_CORRECTIONS = [
    ("苏氏因被扁黄周", "苏轼因被贬黄州"),
    ("元风五年", "元丰五年"),
    ("被扁黄周", "被贬黄州"),
    ("从小喜欢装子", "从小喜欢庄子"),
    ("人生到处知何思", "人生到处知何似"),
    ("硬似飞红踏雪泥", "应似飞鸿踏雪泥"),
    ("泥上偶然流直转", "泥上偶然留指爪"),
    ("红飞哪腹寄东西", "鸿飞那复计东西"),
    ("回首向来消瘦处", "回首向来萧瑟处"),
    ("规去也无风雨也无情", "归去，也无风雨也无晴"),
]


class DouyinExtractor:
    """抖音文案提取器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(CONFIG["headers"])

    def extract_via_api(self, url: str) -> Optional[Dict[str, Any]]:
        """使用第三方 API 提取（备用方案）"""
        # 免费 API 列表（按优先级排序）
        apis = [
            {
                "name": "dlpanda",
                "url": "https://dlpanda.com/api?url={url}&token=G7eRpMaa",  # noqa: public token
                "method": "get",
            },
        ]

        for api in apis:
            try:
                api_url = api["url"].format(url=url)
                print(f"尝试使用 {api['name']} API...", file=sys.stderr)

                if api["method"] == "get":
                    response = self.session.get(api_url, timeout=CONFIG["timeout"])
                else:
                    response = self.session.post(api_url, timeout=CONFIG["timeout"])

                if response.status_code == 200:
                    data = response.json()
                    # 根据不同 API 格式解析
                    if "data" in data:
                        return data["data"]
                    elif "result" in data:
                        return data["result"]
                    elif "video" in data:
                        return data["video"]
            except Exception as e:
                print(f"{api['name']} API 失败: {e}", file=sys.stderr)
                continue

        return None

    def extract_via_douyin_api(self, video_id: str) -> Optional[Dict[str, Any]]:
        """使用抖音内部 API 提取"""
        try:
            # 抖音视频详情 API
            api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.douyin.com/",
            }

            print(f"尝试使用抖音内部 API...", file=sys.stderr)
            response = self.session.get(api_url, headers=headers, timeout=CONFIG["timeout"])

            if response.status_code == 200:
                data = response.json()
                if "item_list" in data and data["item_list"]:
                    item = data["item_list"][0]
                    return {
                        "desc": item.get("desc", ""),
                        "author": item.get("author", {}).get("nickname", ""),
                        "likes": item.get("statistics", {}).get("digg_count", 0),
                        "comments": item.get("statistics", {}).get("comment_count", 0),
                        "shares": item.get("statistics", {}).get("share_count", 0),
                    }
        except Exception as e:
            print(f"抖音内部 API 失败: {e}", file=sys.stderr)

        return None

    def extract_via_playwright(self, url: str) -> Optional[Dict[str, Any]]:
        """使用 Playwright 浏览器自动化提取"""
        if not HAS_PLAYWRIGHT:
            print("Playwright 未安装，请运行: pip install playwright && playwright install", file=sys.stderr)
            return None

        try:
            print("使用 Playwright 浏览器自动化...", file=sys.stderr)

            with sync_playwright() as p:
                # 启动浏览器（无头模式）
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ]
                )

                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    locale="zh-CN",
                )

                page = context.new_page()

                # 访问视频页面
                page.goto(url, wait_until="networkidle", timeout=30000)

                # 等待页面加载
                time.sleep(3)

                # 获取页面内容
                html = page.content()

                # 尝试从页面提取数据
                result = {}

                # 方法1: 从 meta 标签提取
                try:
                    desc = page.locator('meta[name="description"]').get_attribute("content")
                    if desc:
                        result["desc"] = desc
                except Exception:
                    pass

                # 方法2: 从页面元素提取
                if "desc" not in result:
                    try:
                        # 尝试获取视频描述
                        desc_element = page.locator('[class*="desc"]').first
                        if desc_element:
                            result["desc"] = desc_element.inner_text()
                    except Exception:
                        pass

                # 方法3: 从 JavaScript 变量提取
                if "desc" not in result:
                    try:
                        desc = page.evaluate("""
                            () => {
                                // 尝试从全局变量获取
                                if (window.__INITIAL_STATE__) {
                                    const state = window.__INITIAL_STATE__;
                                    if (state.aweme && state.aweme.detail) {
                                        return state.aweme.detail.desc;
                                    }
                                }
                                // 尝试从路由数据获取
                                if (window._ROUTER_DATA) {
                                    const data = window._ROUTER_DATA;
                                    if (data.aweme) {
                                        return data.aweme.desc;
                                    }
                                }
                                return null;
                            }
                        """)
                        if desc:
                            result["desc"] = desc
                    except Exception:
                        pass

                # 方法4: 从页面文本提取（最后手段）
                if "desc" not in result:
                    try:
                        # 获取所有文本内容
                        text = page.inner_text("body")
                        # 查找可能的文案内容
                        patterns = [
                            r"发布于\s*(.*?)\n",
                            r"(\d{4}-\d{2}-\d{2})",
                        ]
                        for pattern in patterns:
                            match = re.search(pattern, text)
                            if match:
                                result["datePublished"] = match.group(1)
                    except Exception:
                        pass

                # 提取作者
                try:
                    author = page.locator('[class*="author"]').first.inner_text()
                    if author:
                        result["author"] = author.strip()
                except Exception:
                    pass

                # 提取互动数据
                try:
                    likes = page.locator('[class*="like"]').first.inner_text()
                    if likes:
                        result["likes"] = self._parse_count(likes)
                except Exception:
                    pass

                browser.close()
                return result if result.get("desc") else None

        except Exception as e:
            print(f"Playwright 提取失败: {e}", file=sys.stderr)
            return None

    def extract_via_share_page(self, url: str) -> Optional[Dict[str, Any]]:
        """
        使用 curl_cffi（Chrome TLS 指纹伪装）访问分享页提取数据

        这是 yt-dlp 失败后的最佳降级方案：直接访问 iesdouyin.com 的分享页，
        从 SSR 渲染的 _ROUTER_DATA 中提取视频信息。

        Args:
            url: 抖音视频链接

        Returns:
            视频信息字典
        """
        if not HAS_CURL_CFFI:
            print("curl_cffi 未安装，跳过分享页提取", file=sys.stderr)
            return None

        print("使用 curl_cffi 访问分享页...", file=sys.stderr)

        try:
            # 先解析短链接获取视频 ID
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }

            # 解析短链接
            resp = curl_requests.get(url, headers=headers, impersonate="chrome", allow_redirects=True, timeout=15)
            final_url = resp.url

            # 提取视频 ID
            video_id_match = re.search(r"video/(\d+)", final_url)
            if not video_id_match:
                # 尝试从 URL 路径提取
                video_id_match = re.search(r"/(\d{15,})/", final_url)
            if not video_id_match:
                print(f"无法从 URL 提取视频 ID: {final_url}", file=sys.stderr)
                return None

            video_id = video_id_match.group(1)

            # 访问分享页
            share_url = f"https://www.iesdouyin.com/share/video/{video_id}/"
            resp = curl_requests.get(share_url, headers=headers, impersonate="chrome", timeout=15)
            html = resp.content.decode("utf-8")

            result = {}

            # 方法1: 从 _ROUTER_DATA 提取
            router_match = re.search(
                r"window\._ROUTER_DATA\s*=\s*(\{.+\})\s*;?\s*</script>",
                html, re.DOTALL,
            )
            if router_match:
                router_data_str = router_match.group(1)
                router_data_str = router_data_str.replace("\\u002F", "/")

                try:
                    data = json.loads(router_data_str)
                    # 深度搜索提取数据
                    self._extract_from_router_data(data, result)
                except json.JSONDecodeError:
                    # 尝试从原始字符串提取
                    desc_match = re.search(
                        r'"desc"\s*:\s*"((?:[^"\\]|\\.)*)"',
                        router_data_str,
                    )
                    if desc_match:
                        try:
                            result["desc"] = desc_match.group(1).encode().decode("unicode_escape")
                        except Exception:
                            result["desc"] = desc_match.group(1)

                    nickname_match = re.search(
                        r'"nickname"\s*:\s*"((?:[^"\\]|\\.)*)"',
                        router_data_str,
                    )
                    if nickname_match:
                        try:
                            result["author"] = nickname_match.group(1).encode().decode("unicode_escape")
                        except Exception:
                            result["author"] = nickname_match.group(1)

            # 方法2: 从 meta 标签提取（兜底）
            if "desc" not in result:
                meta_match = re.search(
                    r'<meta[^>]*name="description"[^>]*content="([^"]+)"',
                    html, re.IGNORECASE,
                )
                if meta_match:
                    desc = meta_match.group(1)
                    desc = desc.replace("&quot;", '"').replace("&amp;", "&")
                    result["desc"] = desc

            return result if result.get("desc") else None

        except Exception as e:
            print(f"curl_cffi 分享页提取失败: {e}", file=sys.stderr)
            return None

    def _extract_from_router_data(self, data: Any, result: dict, depth: int = 0):
        """从 _ROUTER_DATA 递归提取视频信息"""
        if depth > 20:
            return
        if isinstance(data, dict):
            for k, v in data.items():
                if k == "desc" and isinstance(v, str) and len(v) > 5 and "desc" not in result:
                    result["desc"] = self._fix_encoding(v)
                elif k == "nickname" and isinstance(v, str) and len(v) > 1 and "author" not in result:
                    result["author"] = self._fix_encoding(v)
                elif k == "statistics" and isinstance(v, dict):
                    result.setdefault("likes", v.get("digg_count", 0))
                    result.setdefault("comments", v.get("comment_count", 0))
                    result.setdefault("shares", v.get("share_count", 0))
                elif k == "digg_count" and isinstance(v, int):
                    result.setdefault("likes", v)
                elif k == "comment_count" and isinstance(v, int):
                    result.setdefault("comments", v)
                elif k == "share_count" and isinstance(v, int):
                    result.setdefault("shares", v)
                self._extract_from_router_data(v, result, depth + 1)
        elif isinstance(data, list):
            for item in data:
                self._extract_from_router_data(item, result, depth + 1)

    @staticmethod
    def _fix_encoding(text: str) -> str:
        """修复 UTF-8 文本被错误解码为 Latin-1 的问题"""
        try:
            # 如果文本看起来像 UTF-8 被错误解码，重新编码修复
            return text.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return text

    # ── 语音文案提取相关方法 ──────────────────────────────────

    def download_video_file(self, url: str, output_path: str, cookies_browser: str = None, cookies_file: str = None) -> Optional[str]:
        """
        下载抖音视频文件到本地

        优先使用 yt-dlp（处理重定向、格式选择最可靠），
        降级使用 curl_cffi 直接下载。

        Args:
            url: 抖音视频链接
            output_path: 输出文件路径（如 /tmp/video.mp4）
            cookies_browser: 浏览器名称
            cookies_file: cookies.txt 文件路径

        Returns:
            下载成功返回文件路径，失败返回 None
        """
        cookies_browser = cookies_browser or CONFIG.get("yt_dlp_cookies_browser")
        cookies_file = cookies_file or CONFIG.get("yt_dlp_cookies_file")

        # 策略 1: yt-dlp 下载
        print("  尝试 yt-dlp 下载视频...", file=sys.stderr)
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-f", "best[ext=mp4]/best",
            "--no-warnings",
            "-o", output_path,
        ]
        if cookies_file and os.path.exists(cookies_file):
            cmd.extend(["--cookies", cookies_file])
        elif cookies_browser:
            cmd.extend(["--cookies-from-browser", cookies_browser])
        cmd.extend([
            "--add-header", "Referer:https://www.douyin.com/",
            url,
        ])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode == 0 and os.path.exists(output_path):
                print("  yt-dlp 下载成功", file=sys.stderr)
                return output_path
            else:
                print(f"  yt-dlp 下载失败: {result.stderr.strip()[:200]}", file=sys.stderr)
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            print(f"  yt-dlp 下载异常: {e}", file=sys.stderr)

        # 策略 2: curl_cffi 从分享页提取视频 URL 后流式下载
        if HAS_CURL_CFFI:
            print("  尝试 curl_cffi 流式下载视频...", file=sys.stderr)
            try:
                video_url = self._extract_video_url_from_share_page(url)
                if video_url:
                    resp = curl_requests.get(video_url, impersonate="chrome", timeout=300, stream=True)
                    if resp.status_code == 200:
                        total = 0
                        with open(output_path, "wb") as f:
                            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                                    total += len(chunk)
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                            print(f"  curl_cffi 下载成功: {total / 1024 / 1024:.1f}MB", file=sys.stderr)
                            return output_path
            except Exception as e:
                print(f"  curl_cffi 下载失败: {e}", file=sys.stderr)

        return None

    def _extract_video_url_from_share_page(self, url: str) -> Optional[str]:
        """从分享页 SSR 数据中提取视频播放 URL"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                "Accept": "text/html",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            resp = curl_requests.get(url, headers=headers, impersonate="chrome", allow_redirects=True, timeout=15)
            html = resp.content.decode("utf-8")

            # 从 _ROUTER_DATA 提取视频 URL
            router_match = re.search(
                r"window\._ROUTER_DATA\s*=\s*(\{.+\})\s*;?\s*</script>",
                html, re.DOTALL,
            )
            if router_match:
                router_str = router_match.group(1).replace("\\u002F", "/")
                # 搜索 playApi 或 play_addr 中的 URL
                url_patterns = [
                    r'"playApi"\s*:\s*"([^"]+)"',
                    r'"play_addr"\s*:\s*\{[^}]*"url_list"\s*:\s*\["([^"]+)"',
                    r'"download_addr"\s*:\s*\{[^}]*"url_list"\s*:\s*\["([^"]+)"',
                ]
                for pattern in url_patterns:
                    match = re.search(pattern, router_str)
                    if match:
                        video_url = match.group(1)
                        if video_url.startswith("//"):
                            video_url = "https:" + video_url
                        return video_url
        except Exception as e:
            print(f"  提取视频 URL 失败: {e}", file=sys.stderr)
        return None

    @staticmethod
    def extract_audio(video_path: str, output_dir: str) -> Optional[str]:
        """
        从视频文件中提取音频轨

        Args:
            video_path: 视频文件路径
            output_dir: 输出目录

        Returns:
            音频文件路径（WAV 格式）
        """
        if not HAS_MOVIEPY:
            print("moviepy 未安装，无法提取音频", file=sys.stderr)
            return None

        audio_path = os.path.join(output_dir, "audio.wav")
        try:
            print("  提取音频...", file=sys.stderr)
            video = VideoFileClip(video_path)
            if video.audio is None:
                print("  视频没有音频轨", file=sys.stderr)
                video.close()
                return None
            video.audio.write_audiofile(audio_path, fps=16000, nbytes=2, codec="pcm_s16le", logger=None)
            video.close()
            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 100:
                print(f"  音频提取成功: {audio_path}", file=sys.stderr)
                return audio_path
        except Exception as e:
            print(f"  音频提取失败: {e}", file=sys.stderr)
        return None

    @staticmethod
    def transcribe_audio(audio_path: str, model_size: str = "small", language: str = "zh") -> Optional[str]:
        """
        使用 Whisper 转录音频为文字

        通过 initial_prompt 引导模型输出带标点的文本，
        并逐句拼接确保每句话之间有换行。

        Args:
            audio_path: 音频文件路径（WAV 格式）
            model_size: 模型大小（tiny/base/small/medium/large）
            language: 语言代码

        Returns:
            转录文本（带标点和换行）
        """
        if not HAS_WHISPER:
            print("whisper 未安装，无法转录", file=sys.stderr)
            return None

        try:
            print(f"  加载 Whisper {model_size} 模型...", file=sys.stderr)
            model = whisper.load_model(model_size)
            print("  正在转录音频...", file=sys.stderr)

            # initial_prompt 引导模型输出带标点的中文
            result = model.transcribe(
                audio_path,
                language=language,
                fp16=False,
                initial_prompt="以下是普通话的句子，请使用标准中文标点符号进行转录。",
                condition_on_previous_text=True,
            )

            # 逐句拼接（segments），每句独立一行
            segments = result.get("segments", [])
            if segments:
                lines = []
                for seg in segments:
                    seg_text = seg.get("text", "").strip()
                    if seg_text:
                        lines.append(seg_text)
                text = "\n".join(lines)
            else:
                text = result.get("text", "").strip()

            if text:
                print(f"  转录成功: {len(text)} 字", file=sys.stderr)
            else:
                print("  转录结果为空", file=sys.stderr)
            return text if text else None
        except Exception as e:
            print(f"  转录失败: {e}", file=sys.stderr)
            return None

    def extract_transcription(self, url: str, output_dir: str = None, cookies_browser: str = None, cookies_file: str = None, model_size: str = "base") -> Dict[str, Any]:
        """
        完整的语音文案提取流程

        下载视频 → 提取音频 → Whisper 转录 → 文案整理

        Args:
            url: 抖音视频链接
            output_dir: 临时文件目录
            cookies_browser: 浏览器名称
            cookies_file: cookies.txt 文件路径
            model_size: Whisper 模型大小

        Returns:
            包含转录结果的字典
        """
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="douyin_transcribe_")
        os.makedirs(output_dir, exist_ok=True)

        result = {
            "url": url,
            "author": "",
            "description": "",
            "transcription_raw": "",
            "transcription_cleaned": "",
            "error": None,
        }

        # 步骤 1: 获取视频基本信息（作者、描述）
        print("  获取视频信息...", file=sys.stderr)
        video_info = self.extract_via_share_page(url)
        if video_info:
            result["author"] = video_info.get("author", "")
            result["description"] = video_info.get("desc", "")

        # 步骤 2: 下载视频文件
        video_path = os.path.join(output_dir, "video.mp4")
        print("  下载视频文件...", file=sys.stderr)
        downloaded = self.download_video_file(url, video_path, cookies_browser, cookies_file)
        if not downloaded:
            result["error"] = "视频下载失败（请确保浏览器已登录抖音，或尝试 --cookies-file 方式）"
            return result

        # 步骤 3: 提取音频
        audio_path = self.extract_audio(video_path, output_dir)
        if not audio_path:
            result["error"] = "音频提取失败（视频可能没有音频轨）"
            return result

        # 步骤 4: 语音转文字
        transcription = self.transcribe_audio(audio_path, model_size=model_size)
        if not transcription:
            result["error"] = "语音转录失败（请检查 whisper 是否正确安装）"
            return result

        result["transcription_raw"] = transcription

        # 步骤 5: 文案整理
        cleaned_text = self.clean_text(transcription)
        processed_text = TextProcessor.process(cleaned_text)
        result["transcription_cleaned"] = processed_text["cleaned"]

        return result

    def extract_via_ytdlp(self, url: str, cookies_browser: str = None, cookies_file: str = None) -> Optional[Dict[str, Any]]:
        """
        使用 yt-dlp + 浏览器 Cookies 提取视频信息和下载

        这是成功率最高的方案：借用浏览器的登录态绕过抖音反爬限制。

        Args:
            url: 抖音视频链接
            cookies_browser: 浏览器名称（如 'chrome', 'edge', 'firefox'），从浏览器导入 cookies
            cookies_file: cookies.txt 文件路径（优先级高于 cookies_browser）

        Returns:
            视频信息字典，包含 desc, author, video_path 等
        """
        cookies_browser = cookies_browser or CONFIG.get("yt_dlp_cookies_browser")
        cookies_file = cookies_file or CONFIG.get("yt_dlp_cookies_file")

        print("使用 yt-dlp + Cookies 提取...", file=sys.stderr)

        # 首先获取视频元信息
        info_cmd = ["yt-dlp", "--dump-json", "--no-playlist"]

        # 添加 cookies 参数
        if cookies_file and os.path.exists(cookies_file):
            info_cmd.extend(["--cookies", cookies_file])
            print(f"  使用 cookies 文件: {cookies_file}", file=sys.stderr)
        elif cookies_browser:
            info_cmd.extend(["--cookies-from-browser", cookies_browser])
            print(f"  从浏览器导入 cookies: {cookies_browser}",file=sys.stderr)

        info_cmd.append(url)

        try:
            result = subprocess.run(
                info_cmd, capture_output=True, text=True, timeout=60
            )

            if result.returncode == 0 and result.stdout.strip():
                info = json.loads(result.stdout)
                return {
                    "desc": info.get("description", "") or info.get("title", ""),
                    "author": info.get("uploader", "") or info.get("creator", ""),
                    "likes": info.get("like_count", 0),
                    "comments": info.get("comment_count", 0),
                    "shares": info.get("repost_count", 0),
                    "duration": info.get("duration", 0),
                    "upload_date": info.get("upload_date", ""),
                    "_ytdlp_info": info,  # 保留完整信息备用
                }
            else:
                stderr_msg = result.stderr.strip()
                print(f"yt-dlp 元信息提取失败: {stderr_msg}", file=sys.stderr)

                # 常见错误的友好提示
                if "403" in stderr_msg or "Forbidden" in stderr_msg:
                    print("  提示: 403 错误通常意味着 cookies 无效或过期，请确保浏览器已登录抖音", file=sys.stderr)
                elif "cookies" in stderr_msg.lower():
                    print("  提示: 无法读取浏览器 cookies，请尝试导出 cookies.txt 文件", file=sys.stderr)

        except subprocess.TimeoutExpired:
            print("yt-dlp 元信息提取超时", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"yt-dlp 输出解析失败: {e}", file=sys.stderr)
        except FileNotFoundError:
            print("yt-dlp 未安装，请运行: pip install --upgrade yt-dlp", file=sys.stderr)
        except Exception as e:
            print(f"yt-dlp 提取异常: {e}", file=sys.stderr)

        return None

    def download_via_ytdlp(self, url: str, output_dir: str, cookies_browser: str = None, cookies_file: str = None) -> Optional[str]:
        """
        使用 yt-dlp + Cookies 下载视频

        Args:
            url: 抖音视频链接
            output_dir: 输出目录
            cookies_browser: 浏览器名称
            cookies_file: cookies.txt 文件路径

        Returns:
            下载的视频文件路径
        """
        cookies_browser = cookies_browser or CONFIG.get("yt_dlp_cookies_browser")
        cookies_file = cookies_file or CONFIG.get("yt_dlp_cookies_file")

        output_path = os.path.join(output_dir, "video.mp4")

        cmd = [
            "yt-dlp",
            "--no-playlist",
            "-f", "best",
            "--no-warnings",
            "-o", output_path,
        ]

        # 添加 cookies 参数
        if cookies_file and os.path.exists(cookies_file):
            cmd.extend(["--cookies", cookies_file])
        elif cookies_browser:
            cmd.extend(["--cookies-from-browser", cookies_browser])

        # 添加额外 headers 模拟真实浏览器
        cmd.extend([
            "--add-header", "Referer:https://www.douyin.com/",
            "--add-header", "User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ])

        cmd.append(url)

        try:
            print("yt-dlp 正在下载视频...", file=sys.stderr)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0 and os.path.exists(output_path):
                print("yt-dlp 下载成功", file=sys.stderr)
                return output_path
            else:
                print(f"yt-dlp 下载失败: {result.stderr.strip()}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print("yt-dlp 下载超时", file=sys.stderr)
        except Exception as e:
            print(f"yt-dlp 下载异常: {e}", file=sys.stderr)

        return None

    def _parse_count(self, text: str) -> int:
        """解析数字文本（如 '1.2w' -> 12000）"""
        try:
            text = text.strip().lower()
            if "w" in text:
                return int(float(text.replace("w", "")) * 10000)
            elif "k" in text:
                return int(float(text.replace("k", "")) * 1000)
            else:
                return int(re.sub(r"[^\d]", "", text) or 0)
        except Exception:
            return 0

    def extract_video_id(self, url: str) -> Optional[str]:
        """从URL中提取视频ID"""
        # 处理短链接
        if "v.douyin.com" in url:
            return self._extract_from_short_url(url)
        # 处理长链接
        elif "douyin.com/video/" in url:
            match = re.search(r"video/(\d+)", url)
            if match:
                return match.group(1)
        # 处理其他格式
        else:
            match = re.search(r"(\d{15,})", url)
            if match:
                return match.group(1)
        return None

    def _extract_from_short_url(self, url: str) -> Optional[str]:
        """从短链接提取视频ID"""
        try:
            # 使用移动端 headers
            headers = CONFIG["mobile_headers"].copy()

            # 跟随重定向获取真实URL
            response = self.session.get(
                url, headers=headers, allow_redirects=True, timeout=CONFIG["timeout"]
            )

            # 从最终 URL 提取视频ID
            final_url = response.url
            match = re.search(r"video/(\d+)", final_url)
            if match:
                return match.group(1)

            # 从页面内容提取
            match = re.search(r'"aweme_id"\s*:\s*"(\d+)"', response.text)
            if match:
                return match.group(1)

            # 尝试其他模式
            match = re.search(r'video_id\s*[=:]\s*["\']?(\d{15,})', response.text)
            if match:
                return match.group(1)

            # 从 URL 参数提取
            match = re.search(r"modal_id=(\d+)", final_url)
            if match:
                return match.group(1)

            print(f"最终URL: {final_url}", file=sys.stderr)

        except Exception as e:
            print(f"处理短链接时出错: {e}", file=sys.stderr)
        return None

    def fetch_video_page(self, video_id: str) -> Optional[str]:
        """获取视频页面内容"""
        url = f"https://www.douyin.com/video/{video_id}"

        for attempt in range(CONFIG["retry_times"]):
            try:
                # 随机延迟，避免被拦截
                if attempt > 0:
                    time.sleep(CONFIG["retry_delay"] * (attempt + 1) + random.uniform(1, 2))

                # 添加随机 cookie 模拟真实用户
                cookies = {
                    "ttwid": str(random.randint(1000000000000000000, 9999999999999999999)),
                    "msToken": "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=107)),
                }

                response = self.session.get(url, cookies=cookies, timeout=CONFIG["timeout"])

                if response.status_code == 200:
                    return response.text
                elif response.status_code == 403:
                    print("访问被拒绝，尝试使用移动端...", file=sys.stderr)
                    # 尝试移动端
                    mobile_url = f"https://m.douyin.com/share/video/{video_id}"
                    mobile_response = self.session.get(mobile_url, timeout=CONFIG["timeout"])
                    if mobile_response.status_code == 200:
                        return mobile_response.text
                elif response.status_code == 404:
                    print("视频不存在或已删除", file=sys.stderr)
                    return None

            except requests.Timeout:
                print(f"请求超时，重试 {attempt + 1}/{CONFIG['retry_times']}", file=sys.stderr)
            except Exception as e:
                print(f"请求出错: {e}", file=sys.stderr)

        return None

    def parse_video_data(self, html: str) -> Optional[Dict[str, Any]]:
        """解析视频数据"""
        try:
            result = {}

            # 方法1: 从 JSON-LD 提取
            json_ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
            matches = re.findall(json_ld_pattern, html, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    if isinstance(data, dict) and "description" in data:
                        result["desc"] = data.get("description", "")
                        result["author"] = data.get("author", {}).get("name", "未知")
                        result["datePublished"] = data.get("datePublished", "")
                        break
                except json.JSONDecodeError:
                    continue

            # 方法2: 从 meta 标签提取
            meta_patterns = {
                "desc": r'<meta\s+name="description"\s+content="(.*?)"',
                "og:description": r'<meta\s+property="og:description"\s+content="(.*?)"',
                "title": r'<meta\s+name="title"\s+content="(.*?)"',
                "og:title": r'<meta\s+property="og:title"\s+content="(.*?)"',
            }

            for key, pattern in meta_patterns.items():
                if key not in result:
                    match = re.search(pattern, html, re.IGNORECASE)
                    if match:
                        result[key] = match.group(1).strip()

            # 方法3: 从 RENDER_DATA 提取
            render_data_pattern = r'window\._ROUTER_DATA\s*=\s*(\{.+\})\s*;?\s*</script>'
            match = re.search(render_data_pattern, html, re.DOTALL)
            if match:
                try:
                    render_data = json.loads(match.group(1).encode().decode("unicode_escape"))
                    desc = self._deep_find(render_data, "desc")
                    if desc and "desc" not in result:
                        result["desc"] = desc
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass

            # 方法4: 从 SSR 数据提取
            ssr_pattern = r'"desc"\s*:\s*"((?:[^"\\]|\\.)*)"'
            match = re.search(ssr_pattern, html)
            if match and "desc" not in result:
                try:
                    result["desc"] = match.group(1).encode().decode("unicode_escape")
                except Exception:
                    result["desc"] = match.group(1)

            # 方法5: 从 __NEXT_DATA__ 提取
            next_data_pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
            match = re.search(next_data_pattern, html, re.DOTALL)
            if match:
                try:
                    next_data = json.loads(match.group(1))
                    desc = self._deep_find(next_data, "desc")
                    if desc and "desc" not in result:
                        result["desc"] = desc
                except json.JSONDecodeError:
                    pass

            # 方法6: 从 INITIAL_STATE 提取
            initial_state_pattern = r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});'
            match = re.search(initial_state_pattern, html, re.DOTALL)
            if match:
                try:
                    state_data = json.loads(match.group(1))
                    desc = self._deep_find(state_data, "desc")
                    if desc and "desc" not in result:
                        result["desc"] = desc
                except json.JSONDecodeError:
                    pass

            # 方法7: 从页面内容直接提取（最后手段）
            if "desc" not in result:
                # 尝试匹配常见的文案格式
                patterns = [
                    r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
                    r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"',
                    r'"caption"\s*:\s*"((?:[^"\\]|\\.)*)"',
                ]
                for pattern in patterns:
                    match = re.search(pattern, html)
                    if match:
                        try:
                            text = match.group(1).encode().decode("unicode_escape")
                            if len(text) > 10:  # 过滤太短的文本
                                result["desc"] = text
                                break
                        except Exception:
                            pass

            # 如果没有 desc，尝试从 og:description 获取
            if "desc" not in result and "og:description" in result:
                result["desc"] = result["og:description"]

            # 提取作者
            if "author" not in result:
                author_patterns = [
                    r'"nickname"\s*:\s*"((?:[^"\\]|\\.)*)"',
                    r'"author"\s*:\s*"((?:[^"\\]|\\.)*)"',
                    r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"',
                ]
                for pattern in author_patterns:
                    author_match = re.search(pattern, html)
                    if author_match:
                        try:
                            result["author"] = author_match.group(1).encode().decode("unicode_escape")
                        except Exception:
                            result["author"] = author_match.group(1)
                        break

            # 提取互动数据
            stats_patterns = {
                "likes": r'"diggCount"\s*:\s*(\d+)',
                "comments": r'"commentCount"\s*:\s*(\d+)',
                "shares": r'"shareCount"\s*:\s*(\d+)',
            }
            for key, pattern in stats_patterns.items():
                match = re.search(pattern, html)
                if match:
                    result[key] = int(match.group(1))

            return result if result.get("desc") else None

        except Exception as e:
            print(f"解析数据出错: {e}", file=sys.stderr)
            return None

    def _deep_find(self, data: Any, key: str, depth: int = 0) -> Optional[str]:
        """深度查找字典中的键值（限制最大深度 20）"""
        if depth > 20:
            return None
        if isinstance(data, dict):
            if key in data and data[key]:
                return str(data[key])
            for value in data.values():
                result = self._deep_find(value, key, depth + 1)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._deep_find(item, key, depth + 1)
                if result:
                    return result
        return None

    def clean_text(self, text: str) -> str:
        """清理文案文本"""
        if not text:
            return ""

        # 仅在文本包含真正的 Unicode 转义序列时才解码（如 中，不含文件路径中的 \u）
        if re.search(r"\\u[0-9a-fA-F]{4}", text):
            try:
                text = text.encode("ascii").decode("unicode_escape")
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass

        # 移除 HTML 标签
        text = re.sub(r"<[^>]+>", "", text)

        # 移除多余空白
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    @staticmethod
    def format_count(count: int) -> str:
        """格式化数字（如 12345 -> 1.2w）"""
        if count >= 10000:
            return f"{count / 10000:.1f}w"
        elif count >= 1000:
            return f"{count / 1000:.1f}k"
        return str(count)


class TextProcessor:
    """文案处理器"""

    @staticmethod
    def correct_obvious_asr_errors(text: str) -> str:
        """修正常见且高置信度的 ASR 误识别短语"""
        if not text:
            return ""

        result = text
        for source, target in ASR_CORRECTIONS:
            result = result.replace(source, target)

        return result

    @staticmethod
    def remove_filler_words(text: str) -> str:
        """移除语气词和填充词"""
        if not text:
            return ""

        result = _FILLER_PATTERN.sub("", text)

        # 清理多余的空格
        result = re.sub(r"\s+", " ", result)
        return result.strip()

    @staticmethod
    def remove_repeats(text: str) -> str:
        """移除重复词语"""
        if not text:
            return ""

        result = text

        # 移除连续重复的字符（3次以上）
        for pattern in REPEAT_PATTERNS:
            result = re.sub(pattern, r"\1", result)

        # 移除重复的短语（如 "对对对" -> "对"）
        repeat_pattern = r"(\w{1,2})\1{2,}"
        result = re.sub(repeat_pattern, r"\1", result)

        return result

    @staticmethod
    def optimize_sentences(text: str) -> str:
        """优化句子断句（保留原始标点）"""
        if not text:
            return ""

        result = text

        # 清理连续重复的同类标点（如 "。。。" → "。"，"，，，" → "，"）
        result = re.sub(r"。{2,}", "。", result)
        result = re.sub(r"，{2,}", "，", result)
        result = re.sub(r"！{2,}", "！", result)
        result = re.sub(r"？{2,}", "？", result)

        # 清理标点前后的多余空格
        result = re.sub(r"\s*([。，！？；])\s*", r"\1", result)

        # 清理多余空格
        result = re.sub(r"\s+", " ", result)

        return result.strip()

    @staticmethod
    def extract_key_points(text: str) -> list:
        """提取核心观点"""
        if not text:
            return []

        key_points = []

        # 按句子分割
        sentences = re.split(r"[。！？]+", text)

        # 关键词列表
        keywords = [
            "重要", "关键", "核心", "必须", "一定", "记住",
            "首先", "其次", "最后", "第一", "第二", "第三",
            "总结", "归纳", "总之", "所以", "因此",
            "记住", "切记", "务必", "千万",
        ]

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # 检查是否包含关键词
            for keyword in keywords:
                if keyword in sentence:
                    key_points.append(sentence)
                    break

        # 如果没有找到关键词，取前3个句子作为要点
        if not key_points and sentences:
            key_points = [s.strip() for s in sentences[:3] if s.strip()]

        return key_points[:5]  # 最多返回5个要点

    @staticmethod
    def bold_key_points(text: str, key_points: list) -> str:
        """将核心观点加粗"""
        if not text or not key_points:
            return text

        result = text
        for point in key_points:
            if point in result:
                # 在 Markdown 中加粗
                bold_text = f"**{point}**"
                result = result.replace(point, bold_text)

        return result

    @staticmethod
    def process(text: str) -> dict:
        """完整处理流程"""
        # 1. 修正常见 ASR 误识别
        step1 = TextProcessor.correct_obvious_asr_errors(text)

        # 2. 移除语气词
        step2 = TextProcessor.remove_filler_words(step1)

        # 3. 移除重复词
        step3 = TextProcessor.remove_repeats(step2)

        # 4. 优化断句
        step4 = TextProcessor.optimize_sentences(step3)

        # 5. 提取核心观点
        key_points = TextProcessor.extract_key_points(step4)

        # 6. 加粗核心观点
        formatted = TextProcessor.bold_key_points(step4, key_points)

        return {
            "original": text,
            "cleaned": step4,
            "key_points": key_points,
            "formatted": formatted,
        }


def format_output(video_data: dict, processed_text: dict) -> str:
    """格式化输出"""
    lines = []

    lines.append("")
    lines.append("📹 抖音视频信息")
    lines.append("═" * 50)
    lines.append("")

    # 基本信息
    if video_data.get("url"):
        lines.append(f"🔗 链接：{video_data['url']}")
    if video_data.get("author"):
        lines.append(f"👤 作者：@{video_data['author']}")
    if video_data.get("datePublished"):
        lines.append(f"📅 发布时间：{video_data['datePublished']}")
    if video_data.get("likes"):
        lines.append(f"👍 点赞：{DouyinExtractor.format_count(video_data['likes'])}")
    if video_data.get("comments"):
        lines.append(f"💬 评论：{DouyinExtractor.format_count(video_data['comments'])}")
    if video_data.get("shares"):
        lines.append(f"🔄 转发：{DouyinExtractor.format_count(video_data['shares'])}")

    lines.append("")
    lines.append("═" * 50)
    lines.append("📝 原始文案")
    lines.append("─" * 50)
    lines.append(processed_text["original"] if processed_text["original"] else "（无文案）")

    lines.append("")
    lines.append("═" * 50)
    lines.append("✨ 整理后文案")
    lines.append("─" * 50)
    lines.append(processed_text["formatted"] if processed_text["formatted"] else "（无文案）")

    if processed_text.get("key_points"):
        lines.append("")
        lines.append("═" * 50)
        lines.append("💡 核心观点")
        lines.append("─" * 50)
        for i, point in enumerate(processed_text["key_points"], 1):
            lines.append(f"{i}. **{point}**")

    lines.append("")
    lines.append("═" * 50)

    return "\n".join(lines)


def format_transcription_output(result: dict) -> str:
    """格式化语音文案完整输出（用于保存文件和短视频显示）"""
    lines = []
    raw = result.get("transcription_raw", "") or ""
    cleaned = result.get("transcription_cleaned", "") or ""
    total_chars = len(raw)

    lines.append("")
    lines.append("📹 抖音视频语音文案")
    lines.append("═" * 50)
    lines.append("")

    if result.get("url"):
        lines.append(f"🔗 链接：{result['url']}")
    if result.get("author"):
        lines.append(f"👤 作者：@{result['author']}")
    if result.get("description"):
        lines.append(f"📝 视频描述：{result['description']}")

    lines.append("")
    lines.append("═" * 50)
    lines.append(f"🎤 原始语音转录（{total_chars} 字）")
    lines.append("─" * 50)
    lines.append(raw)

    lines.append("")
    lines.append("═" * 50)
    lines.append("✨ 整理后文案")
    lines.append("─" * 50)
    lines.append(cleaned if cleaned else "（无内容）")

    if cleaned:
        processor = TextProcessor()
        key_points = processor.extract_key_points(cleaned)
        if key_points:
            lines.append("")
            lines.append("═" * 50)
            lines.append("💡 核心观点")
            lines.append("─" * 50)
            for i, point in enumerate(key_points, 1):
                lines.append(f"{i}. {point}")

    lines.append("")
    lines.append("═" * 50)
    return "\n".join(lines)


def extract_douyin_transcription(url: str, cookies_browser: str = None, cookies_file: str = None, model_size: str = "base") -> str:
    """
    语音文案提取主函数

    下载视频 → 提取音频 → Whisper 转录 → 文案整理

    Args:
        url: 抖音视频链接
        cookies_browser: 浏览器名称
        cookies_file: cookies.txt 文件路径
        model_size: Whisper 模型大小（tiny/base/small/medium/large）

    Returns:
        包含转录数据的字典，或以 "❌" 开头的错误字符串
    """
    extractor = DouyinExtractor()

    # 检查依赖
    if not HAS_WHISPER:
        return "❌ whisper 未安装，请运行: pip install openai-whisper"
    if not HAS_MOVIEPY:
        return "❌ moviepy 未安装，请运行: pip install moviepy"

    # 创建临时目录
    output_dir = tempfile.mkdtemp(prefix="douyin_transcribe_")

    print("━" * 40, file=sys.stderr)
    print("开始语音文案提取", file=sys.stderr)
    print(f"  Whisper 模型: {model_size}", file=sys.stderr)
    print(f"  临时目录: {output_dir}", file=sys.stderr)

    # 执行完整流程
    result = extractor.extract_transcription(url, output_dir, cookies_browser, cookies_file, model_size)

    # 清理临时文件
    try:
        shutil.rmtree(output_dir, ignore_errors=True)
    except Exception:
        pass

    if result.get("error"):
        return f"❌ {result['error']}"

    return result


def extract_douyin_text(url: str, cookies_browser: str = None, cookies_file: str = None) -> str:
    """
    主提取函数

    Args:
        url: 抖音视频链接
        cookies_browser: 浏览器名称（如 'chrome', 'edge'），用于导入 cookies
        cookies_file: cookies.txt 文件路径

    提取策略（按优先级）：
        1. yt-dlp + 浏览器 Cookies（成功率最高，推荐）
        2. curl_cffi 分享页提取（Chrome TLS 指纹伪装，无需 cookies）
        3. 直接请求页面解析
        4. 第三方 API
        5. 抖音内部 API
        6. Playwright 浏览器自动化
    """
    extractor = DouyinExtractor()
    processor = TextProcessor()

    # 1. 提取视频ID
    video_id = extractor.extract_video_id(url)
    if not video_id:
        return "❌ 无法从链接中提取视频ID，请检查链接格式"

    print(f"视频ID: {video_id}", file=sys.stderr)

    # 2. 【首选】使用 yt-dlp + Cookies 提取
    print("━" * 40, file=sys.stderr)
    print("策略 1/6: yt-dlp + 浏览器 Cookies", file=sys.stderr)
    video_data = extractor.extract_via_ytdlp(url, cookies_browser, cookies_file)

    # 3. 【降级】使用 curl_cffi 访问分享页
    if not video_data or not video_data.get("desc"):
        print("━" * 40, file=sys.stderr)
        print("策略 2/6: curl_cffi 分享页提取（Chrome TLS 指纹伪装）", file=sys.stderr)
        video_data = extractor.extract_via_share_page(url)

    # 4. 如果 curl_cffi 失败，尝试直接请求页面
    if not video_data or not video_data.get("desc"):
        print("━" * 40, file=sys.stderr)
        print("策略 3/6: 直接请求页面解析", file=sys.stderr)
        html = extractor.fetch_video_page(video_id)
        if html:
            video_data = extractor.parse_video_data(html)

    # 5. 如果直接提取失败，尝试使用第三方 API
    if not video_data or not video_data.get("desc"):
        print("━" * 40, file=sys.stderr)
        print("策略 4/6: 第三方 API", file=sys.stderr)
        video_data = extractor.extract_via_api(url)

    # 6. 如果第三方 API 也失败，尝试抖音内部 API
    if not video_data or not video_data.get("desc"):
        print("━" * 40, file=sys.stderr)
        print("策略 5/6: 抖音内部 API", file=sys.stderr)
        video_data = extractor.extract_via_douyin_api(video_id)

    # 7. 如果所有方法都失败，尝试 Playwright
    if not video_data or not video_data.get("desc"):
        print("━" * 40, file=sys.stderr)
        print("策略 6/6: Playwright 浏览器自动化", file=sys.stderr)
        video_data = extractor.extract_via_playwright(url)

    if not video_data:
        return "❌ 无法解析视频数据，可能触发了访问限制\n\n💡 建议:\n1. 运行 pip install --upgrade yt-dlp 更新到最新版\n2. 运行 pip install curl-cffi 安装 TLS 指纹伪装库\n3. 确保 Chrome 浏览器已登录抖音\n4. 尝试导出 cookies.txt 文件: --cookies-file cookies.txt"

    # 5. 清理文案
    desc = extractor.clean_text(video_data.get("desc", "") or video_data.get("title", ""))
    if not desc:
        return "❌ 无法提取视频文案，视频可能没有文案内容"

    # 6. 处理文案
    processed_text = processor.process(desc)

    # 7. 格式化输出
    video_data["url"] = url
    output = format_output(video_data, processed_text)

    return output


def _truncate_console_output(full_output: str, total_chars: int, file_path: str = None) -> str:
    """
    为长视频生成截断的控制台输出

    原始转录和整理后文案各取前 3 段，核心观点完整保留。
    """
    lines = []

    # 提取头部信息（链接、作者、描述）
    header_match = re.search(r"(📹 抖音视频语音文案\n═+\n\n.*?)(\n═+\n🎤)", full_output, re.DOTALL)
    if header_match:
        lines.append(header_match.group(1))

    # 原始转录（取前 3 段）
    raw_match = re.search(r"🎤 原始语音转录.*?\n─+\n(.*?)(?=\n═+\n✨)", full_output, re.DOTALL)
    if raw_match:
        raw_text = raw_match.group(1).strip()
        raw_paragraphs = [p.strip() for p in raw_text.split("\n") if p.strip()]
        lines.append("")
        lines.append("═" * 50)
        lines.append(f"🎤 原始语音转录（共 {total_chars} 字，以下为前 3 段）")
        lines.append("─" * 50)
        for p in raw_paragraphs[:3]:
            lines.append(p)
        if len(raw_paragraphs) > 3:
            lines.append(f"\n...（共 {len(raw_paragraphs)} 段，完整版见文件）")

    # 整理后文案（截取前 300 字）
    cleaned_match = re.search(r"✨ 整理后文案.*?\n─+\n(.*?)(?=\n═+\n💡)", full_output, re.DOTALL)
    if cleaned_match:
        cleaned_text = cleaned_match.group(1).strip()
        lines.append("")
        lines.append("═" * 50)
        lines.append("✨ 整理后文案（以下为摘要）")
        lines.append("─" * 50)
        if len(cleaned_text) > 300:
            # 在 300 字附近找最近的句号
            cut = cleaned_text[:300]
            last_period = max(cut.rfind("。"), cut.rfind("！"), cut.rfind("？"))
            if last_period > 150:
                lines.append(cut[:last_period + 1])
            else:
                lines.append(cut)
            lines.append(f"\n...（完整版见文件）")
        else:
            lines.append(cleaned_text)

    # 核心观点（完整保留）
    points_match = re.search(r"💡 核心观点\n─+\n(.*?)(?:\n═|\Z)", full_output, re.DOTALL)
    if points_match:
        lines.append("")
        lines.append("═" * 50)
        lines.append("💡 核心观点")
        lines.append("─" * 50)
        lines.append(points_match.group(1).strip())

    # 文件保存路径
    lines.append("")
    lines.append("═" * 50)
    if file_path:
        lines.append(f"📄 完整文案已保存: {file_path}")
    lines.append("")

    return "\n".join(lines)


def main():
    """主函数"""
    import argparse

    # 设置控制台编码为 UTF-8
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="抖音视频语音文案提取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 提取视频语音文案（默认，直接使用）
  python extract.py https://v.douyin.com/xxxxx

  # 使用更准确的模型
  python extract.py --whisper-model medium https://v.douyin.com/xxxxx

  # 仅提取视频描述（不需要下载视频）
  python extract.py --desc https://v.douyin.com/xxxxx

  # 指定 cookies
  python extract.py --cookies-browser edge https://v.douyin.com/xxxxx
  python extract.py --cookies-file cookies.txt https://v.douyin.com/xxxxx

  # 更新 yt-dlp
  python extract.py --update-ytdlp
        """,
    )
    parser.add_argument("url", nargs="?", help="抖音视频链接")
    parser.add_argument(
        "--desc",
        action="store_true",
        help="仅提取视频描述文字（不需要下载视频，速度快）",
    )
    parser.add_argument(
        "--whisper-model",
        default="small",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper 模型大小（默认: small）。tiny 最快，large 最准",
    )
    parser.add_argument(
        "--cookies-browser",
        default="chrome",
        help="从浏览器导入 cookies（默认: chrome）。可选: chrome, edge, firefox, safari",
    )
    parser.add_argument(
        "--cookies-file",
        help="使用 cookies.txt 文件（优先级高于 --cookies-browser）",
    )
    parser.add_argument(
        "--no-cookies",
        action="store_true",
        help="不使用 cookies（降级为旧版行为）",
    )
    parser.add_argument(
        "--update-ytdlp",
        action="store_true",
        help="更新 yt-dlp 到最新版本后退出",
    )
    parser.add_argument(
        "--raw-json",
        action="store_true",
        help="只输出原始转录的 JSON 数据（url, author, description, transcription_raw, error），不生成 Markdown 文件。供 Claude Code Skill 使用。",
    )

    args = parser.parse_args()

    # 更新 yt-dlp
    if args.update_ytdlp:
        print("正在更新 yt-dlp...", file=sys.stderr)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print("✅ yt-dlp 更新成功")
        else:
            print(f"❌ 更新失败: {result.stderr}")
        sys.exit(0)

    if not args.url:
        parser.print_help()
        sys.exit(1)

    url = args.url.strip()

    # 验证URL格式
    if not re.search(r"douyin\.com", url):
        print("请输入有效的抖音视频链接")
        sys.exit(1)

    # 处理 cookies 参数
    cookies_browser = None if args.no_cookies else args.cookies_browser
    cookies_file = args.cookies_file

    if args.desc:
        # 仅提取视频描述（不需要下载视频）
        print("正在提取视频描述...", file=sys.stderr)
        result = extract_douyin_text(url, cookies_browser, cookies_file)
        print(result)
    elif args.raw_json:
        # Claude Code Skill 模式：只输出原始转录的 JSON，不生成 Markdown
        # Claude 会基于此 JSON 一次性生成最终 Markdown 文档
        print("正在提取视频原始转录（raw-json 模式）...", file=sys.stderr)
        result = extract_douyin_transcription(url, cookies_browser, cookies_file, args.whisper_model)

        # 错误处理：result 是字符串说明出错
        if isinstance(result, str) and result.startswith("❌"):
            payload = {
                "url": url,
                "author": "",
                "description": "",
                "transcription_raw": "",
                "error": result.lstrip("❌ ").strip(),
            }
        else:
            # result 是 dict，提取原始字段，不包含任何 Markdown 或整理后文本
            payload = {
                "url": result.get("url", url),
                "author": result.get("author", ""),
                "description": result.get("description", ""),
                "transcription_raw": result.get("transcription_raw", ""),
                "error": result.get("error"),
            }

        # 输出纯 JSON 到 stdout（Claude 解析用），不写文件
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        # 默认：提取视频语音文案（下载视频 → Whisper 转录）
        print("正在提取视频语音文案...", file=sys.stderr)
        result = extract_douyin_transcription(url, cookies_browser, cookies_file, args.whisper_model)

        # 错误处理
        if isinstance(result, str) and result.startswith("❌"):
            print(result)
            return

        # result 是 dict，包含转录数据
        # 1. 格式化完整版
        full_output = format_transcription_output(result)

        # 2. 保存完整版到文件
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        author = re.sub(r'[\\/:*?"<>|]', '', result.get("author", ""))[:20]
        filename = "_".join(filter(None, ["douyin", timestamp, author])) + ".md"
        file_path = os.path.join(output_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_output)

        # 3. 控制台输出（长文本截断）
        total_chars = len(result.get("transcription_raw", ""))
        if total_chars > 1000:
            print(_truncate_console_output(full_output, total_chars, file_path))
        else:
            print(full_output)
            print(f"📄 完整文案已保存: {file_path}")


if __name__ == "__main__":
    main()
