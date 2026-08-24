"""
B站 Playwright 下载引擎

基于 Playwright 浏览器自动化，拦截 B站 /playurl API 获取视频数据。
将 PlaywrightBilibiliDownloader 与 BilibiliEngine 合并为单一类，
去除对 playwright_engine.py 的外部依赖。
"""

import os
import json
import time
import re
import subprocess
import shutil
import logging
import requests
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from .base_engine import BaseDownloadEngine

# ============================================================
# Playwright 可用性检测
# ============================================================
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# ============================================================
# 日志配置
# ============================================================
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# ============================================================
# 工具函数：参数验证和输入清理
# ============================================================
def validate_bilibili_url(url):
    """
    验证是否为有效的 B站视频链接
    支持格式：
      - https://www.bilibili.com/video/BVxxx
      - https://b23.tv/xxx (短链接)
      - 包含 BV 号的任意 URL
    返回：(valid: bool, cleaned_url: str, video_id: str)
    """
    if not url or not isinstance(url, str):
        return False, None, None

    url = url.strip()

    # 基础格式检查
    if not url.startswith(('http://', 'https://')):
        # 可能是 BV 号
        if re.match(r'^BV[a-zA-Z0-9]{10}$', url):
            url = f'https://www.bilibili.com/video/{url}'
        else:
            return False, None, None

    # 解析 URL
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return False, None, None

        # 检查是否为 B站域名或短链接
        valid_domains = ['bilibili.com', 'b23.tv', 'biligame.com']
        if not any(domain in parsed.netloc for domain in valid_domains):
            return False, None, None

    except Exception:
        return False, None, None

    # 提取视频 ID (BV 号)
    video_id = None
    bv_match = re.search(r'/(BV[a-zA-Z0-9]{10})', url)
    if bv_match:
        video_id = bv_match.group(1)

    return True, url, video_id


def sanitize_filename(title, max_length=100):
    """
    清理文件名，移除非法字符
    返回安全的文件名
    """
    if not title:
        return 'bilibili_video'

    # 移除非法字符
    safe = re.sub(r'[\\/*?:"<>|]', '', title)
    safe = safe.strip()

    # 限制长度
    if len(safe) > max_length:
        safe = safe[:max_length].strip()

    # 防止空文件名
    if not safe:
        safe = 'bilibili_video'

    return safe


def validate_quality(quality):
    """
    验证清晰度设置
    返回有效的清晰度字符串
    """
    valid_qualities = ["最佳质量", "1080P", "720P", "480P", "仅音频"]
    if quality not in valid_qualities:
        logger.warning(f"无效的清晰度设置：{quality}，使用默认值")
        return "最佳质量"
    return quality


def validate_timeout(timeout):
    """
    验证超时设置
    返回有效的超时值（秒）
    """
    try:
        timeout = int(timeout)
        if timeout < 10:
            return 10
        if timeout > 300:
            return 300
        return timeout
    except (ValueError, TypeError):
        return 30  # 默认 30 秒

def validate_proxy_config(proxy_server, proxy_username=None, proxy_password=None):
    """
    验证代理配置
    支持格式：
      - HTTP：http://proxy:port
      - HTTPS：https://proxy:port
      - SOCKS5：socks5://proxy:port
    返回：(valid: bool, proxy_config: dict, error_msg: str)
    """
    if not proxy_server:
        return False, None, "代理地址不能为空"

    # 检查协议前缀
    valid_schemes = ['http://', 'https://', 'socks5://']
    has_scheme = any(proxy_server.startswith(scheme) for scheme in valid_schemes)

    if not has_scheme:
        return False, None, f"无效的代理协议，支持：{', '.join(valid_schemes)}"

    # 构建 Playwright 代理配置
    proxy_config = {'server': proxy_server}

    # 添加认证信息
    if proxy_username and proxy_password:
        proxy_config['username'] = proxy_username
        proxy_config['password'] = proxy_password

    # 添加绕过列表
    proxy_config['bypass'] = 'localhost,127.0.0.1'

    return True, proxy_config, ""


def test_proxy_connection(proxy_server, timeout=10):
    """
    测试代理连接是否可用
    返回：(success: bool, message: str)
    """
    try:
        # 配置代理
        proxies = {
            'http': proxy_server,
            'https': proxy_server
        }

        # 测试连接（访问一个简单网站）
        logger.info(f"测试代理连接：{proxy_server}")
        resp = requests.get(
            'https://ipinfo.io/json',
            proxies=proxies,
            timeout=timeout
        )

        if resp.status_code == 200:
            data = resp.json()
            ip = data.get('ip', 'unknown')
            country = data.get('country', 'unknown')
            return True, f"代理连接成功！IP：{ip} ({country})"
        else:
            return False, f"代理连接失败：HTTP {resp.status_code}"

    except ImportError:
        return False, "需要安装 requests 库：pip install requests"
    except Exception as e:
        return False, f"代理连接失败：{str(e)}"


# 清晰度 → 最高高度映射
QUALITY_MAX_HEIGHT = {
    "最佳质量": 99999,
    "1080P": 1080,
    "720P": 720,
    "480P": 480,
    "仅音频": 0,
}


# ============================================================
# BilibiliEngine：合并后的 B站 Playwright 下载引擎
# ============================================================
class BilibiliEngine(BaseDownloadEngine):
    """
    B站 Playwright 浏览器自动化下载引擎

    工作流程：
    1. 启动真实浏览器（Chromium）
    2. 访问 B站视频页面，自动触发 /playurl API
    3. 监听网络响应，拦截视频数据（dash 格式，含视频+音频URL）
    4. 按选定清晰度筛选视频流
    5. 用 requests 下载，ffmpeg 合并音视频
    """

    def __init__(
        self,
        progress_callback=None,
        log_callback=None,
        status_callback=None,
        **kwargs,
    ):
        super().__init__(progress_callback, log_callback, status_callback)
        self.cancel_flag = False
        self._proxy = kwargs.get('proxy')
        self._proxy_username = kwargs.get('proxy_username')
        self._proxy_password = kwargs.get('proxy_password')

    # ---- 类级别元信息 ----

    @classmethod
    def get_engine_name(cls) -> str:
        return "Playwright（B站专用）"

    @classmethod
    def get_supported_domains(cls) -> list:
        return ["bilibili.com", "b23.tv"]

    @classmethod
    def is_available(cls) -> bool:
        return PLAYWRIGHT_AVAILABLE

    # ---- 公开接口 ----

    def validate_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """验证 B站视频链接"""
        if validate_bilibili_url is None:
            return False, None, None
        valid, cleaned, video_id = validate_bilibili_url(url)
        return valid, cleaned, video_id

    def get_video_info(self, url: str, **kwargs) -> Optional[dict]:
        """
        B站 Playwright 引擎暂不支持获取视频元信息
        （需要启动浏览器，成本较高）
        """
        return None

    def download(
        self,
        url: str,
        output_dir: str,
        quality: str = "最佳质量",
        **kwargs,
    ) -> bool:
        """
        B站专用下载（Playwright 浏览器自动化）

        额外参数：
        - headless: 是否无头模式（默认 True，不显示浏览器窗口）
        - timeout: 超时秒数
        """
        if not PLAYWRIGHT_AVAILABLE:
            self._log("❌ Playwright 未安装", 'error')
            self._log("   请安装：pip install playwright && playwright install chromium")
            return False

        valid, cleaned_url, video_id = self.validate_url(url)
        if not valid:
            self._log(f"❌ 无效的 B站链接：{url}", 'error')
            return False

        url = cleaned_url
        quality = validate_quality(quality)
        timeout = validate_timeout(kwargs.get('timeout', 30))

        self.cancel_flag = False
        os.makedirs(output_dir, exist_ok=True)

        headless = kwargs.get('headless', True)

        # 构建代理配置
        proxy_config = None
        if 'proxy' in kwargs and kwargs['proxy']:
            proxy_config = {'server': kwargs['proxy']}
            proxy_username = kwargs.get('proxy_username')
            proxy_password = kwargs.get('proxy_password')
            if proxy_username and proxy_password:
                proxy_config['username'] = proxy_username
                proxy_config['password'] = proxy_password

        self._log("=" * 50)
        self._log("[方案B] Playwright 浏览器自动化")
        self._log(f"链接：{url}")
        self._log(f"视频 ID：{video_id}")
        self._log(f"清晰度：{quality}")
        self._log(f"输出目录：{output_dir}")
        if proxy_config:
            self._log(f"代理：{proxy_config.get('server', '')}")
        self._log("=" * 50)

        # 第一步：启动浏览器拦截视频数据
        self._status("正在启动浏览器获取视频数据...")
        data, page_title = self._fetch_video_data(
            url, headless=headless, timeout=timeout, proxy_config=proxy_config
        )

        if data is None:
            self._log("❌ 获取视频数据失败", 'error')
            return False
        if self.cancel_flag:
            self._log("已取消")
            return False

        # 标题
        title = page_title or "bilibili_video"
        safe_title = sanitize_filename(title)
        self._log(f"视频标题：{title}")
        self._log(f"安全文件名：{safe_title}")

        # 第二步：解析 dash 数据，选择清晰度
        dash = data.get("dash") or {}
        videos = dash.get("video", [])
        audios = dash.get("audio", [])

        if not videos and quality != "仅音频":
            self._log("❌ 未找到视频流数据", 'error')
            return False

        self._log(f"视频流数量：{len(videos)}，音频流数量：{len(audios)}")

        video_item = self._select_video_stream(videos, quality)
        audio_item = max(audios, key=lambda x: x.get("bandwidth", 0)) if audios else None

        # 仅音频模式
        if quality == "仅音频":
            video_item = None
            video_url = None
        elif video_item:
            video_url = video_item.get("base_url") or video_item.get("baseUrl", "")
            self._log(f"选中视频流：{video_item.get('height', '?')}P "
                     f"{video_item.get('codecs', '?')} "
                     f"{video_item.get('bandwidth', 0) // 1000}kbps")
        else:
            self._log("❌ 未找到匹配的视频流", 'error')
            return False

        audio_url = None
        if audio_item and quality != "仅音频":
            audio_url = audio_item.get("base_url") or audio_item.get("baseUrl", "")
            self._log(f"选中音频流：{audio_item.get('codecs', '?')} "
                     f"{audio_item.get('bandwidth', 0) // 1000}kbps")

        if not video_url and not audio_url:
            self._log("❌ 无可用视频或音频 URL", 'error')
            return False

        # 第三步：下载
        self._status("正在下载...")
        base = os.path.join(output_dir, safe_title)
        video_file = base + ".video.m4s"
        audio_file = base + ".audio.m4a"
        output_file = base + ".mp4"

        # 下载视频
        if video_url and not self.cancel_flag:
            self._log("-" * 50)
            self._log("下载视频流...")
            if not self._download_file(video_url, video_file, "视频", proxy_config):
                return False

        # 下载音频
        if audio_url and not self.cancel_flag:
            self._log("-" * 50)
            self._log("下载音频流...")
            if not self._download_file(audio_url, audio_file, "音频", proxy_config):
                audio_file = None

        if self.cancel_flag:
            self._log("已取消")
            return False

        # 第四步：合并
        self._log("-" * 50)
        save_separate = kwargs.get('save_separate_streams', True)
        if video_file and os.path.exists(video_file) and audio_file and os.path.exists(audio_file):
            ok = self._merge_files(video_file, audio_file, output_file, keep_sources=save_separate)
            if ok:
                self._log(f"✅ 下载完成：{output_file}")
                self._status("下载完成")
                return True
            else:
                self._log(f"⚠️ 合并失败，原始文件：{video_file}, {audio_file}", 'warning')
                return False
        elif video_file and os.path.exists(video_file):
            # 只有视频（无音频）
            shutil.move(video_file, output_file)
            self._log(f"✅ 下载完成（无音频）：{output_file}")
            self._status("下载完成")
            return True
        elif audio_file and os.path.exists(audio_file):
            # 只有音频
            shutil.move(audio_file, output_file)
            self._log(f"✅ 下载完成（仅音频）：{output_file}")
            self._status("下载完成")
            return True

        self._log("❌ 下载失败：文件不存在", 'error')
        return False

    def cancel(self):
        """取消下载"""
        self.cancel_flag = True

    # ---- 内部方法 ----

    def _fetch_video_data(self, url, headless=True, timeout=30, proxy_config=None):
        """
        启动浏览器访问视频页，拦截 /playurl API 响应。
        返回 (video_data_dict, page_title) 或 (None, None)
        """
        if not PLAYWRIGHT_AVAILABLE:
            self._log("❌ Playwright 未安装", 'error')
            self._log("   请运行：pip install playwright && playwright install chromium", 'error')
            return None, None

        # 参数验证
        valid, cleaned_url, video_id = validate_bilibili_url(url)
        if not valid:
            self._log(f"❌ 无效的 B站视频链接：{url}", 'error')
            return None, None

        url = cleaned_url
        timeout = validate_timeout(timeout)

        self._log(f"视频 ID：{video_id}")
        logger.debug(f"_fetch_video_data: url={url}, headless={headless}, timeout={timeout}")

        video_data = None
        page_title = None

        self._log("启动浏览器...")
        try:
            with sync_playwright() as pw:
                # 启动浏览器，支持代理
                launch_options = {'headless': headless}
                if proxy_config:
                    proxy_config_copy = proxy_config.copy()

                    # 添加认证信息（如果提供）
                    if self._proxy_username and self._proxy_password:
                        proxy_config_copy['username'] = self._proxy_username
                        proxy_config_copy['password'] = self._proxy_password
                        self._log(f"使用代理（带认证）：{proxy_config.get('server', '')}")
                    else:
                        self._log(f"使用代理：{proxy_config.get('server', '')}")

                    launch_options['proxy'] = proxy_config_copy

                browser = pw.chromium.launch(**launch_options)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                # ---- 拦截 /playurl 响应 ----
                def on_response(resp):
                    nonlocal video_data
                    if video_data:
                        return
                    if '/playurl' in resp.url and resp.status == 200:
                        try:
                            body = resp.json()
                            if body.get('code') == 0 and 'data' in body:
                                video_data = body['data']
                                q = body['data'].get('quality', '?')
                                self._log(f"✅ 拦截到视频数据（接口返回 quality={q}）")
                        except Exception as e:
                            self._log(f"  解析 /playurl 响应失败：{e}", 'warning')

                page.on("response", on_response)

                # ---- 访问页面 ----
                self._log(f"访问：{url[:90]}")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                except Exception as e:
                    self._log(f"  页面加载异常：{e}", 'error')
                    return None, None

                # ---- 触发播放器加载（让页面发 /playurl 请求）----
                self._log("等待视频数据加载...")
                try:
                    # 等清晰度按钮出现 = 播放器已初始化
                    page.wait_for_selector(
                        ".bpx-player-ctrl-quality, .squirtle-quality-wrap",
                        timeout=8000
                    )
                    # 点一下播放按钮，确保触发加载
                    try:
                        page.click(".bpx-player-btn-play", timeout=2000)
                        time.sleep(0.5)
                    except Exception:
                        pass
                except Exception:
                    self._log("  （未检测到播放器 UI，继续等待 API 响应）", 'warning')

                # ---- 等 API 响应（最多 15 秒）----
                deadline = time.time() + 15
                while time.time() < deadline:
                    if self.cancel_flag or video_data:
                        break
                    time.sleep(0.3)

                # ---- 提取页面标题 ----
                try:
                    raw_title = page.evaluate("document.title")
                    # "标题_分区_哔哩哔哩_bilibili" → "标题"
                    if raw_title:
                        page_title = raw_title.split("_")[0].strip()
                except Exception:
                    page_title = None

                browser.close()

            if video_data:
                return video_data, page_title

            self._log("⚠️ 未拦截到 /playurl 响应")
            self._log("   建议：勾选「显示浏览器窗口」，手动登录后重试", 'warning')
            return None, None

        except Exception as e:
            self._log(f"❌ 浏览器启动失败：{e}", 'error')
            self._log("   可能原因：Playwright 未正确安装或 Chromium 缺失", 'error')
            return None, None

    def _select_video_stream(self, videos, quality):
        """
        videos: dash['video'] 列表，每项含 height / bandwidth / id
        返回：选中的视频流 dict，或 None
        """
        if not videos:
            return None

        max_h = QUALITY_MAX_HEIGHT.get(quality, 99999)

        if quality == "仅音频":
            return None

        # 过滤不超过目标高度的流，选其中码率最高的
        candidates = [v for v in videos if v.get("height", 0) <= max_h]
        if not candidates:
            # 没有符合高度的，降级取最接近的
            self._log(f"  清晰度 {quality} 不可用，降级取可用最高画质")
            candidates = videos

        return max(candidates, key=lambda x: x.get("bandwidth", 0))

    def _download_file(self, url, filepath, label="", proxy_config=None, max_retries=3):
        """
        下载文件，支持重试和代理
        返回：成功 True，失败 False
        """
        if not url:
            self._log(f"❌ 下载失败（{label}）：URL 为空", 'error')
            return False

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com/",
        }

        # 配置代理（如果设置了）
        proxies = None
        if proxy_config and 'server' in proxy_config:
            proxy_server = proxy_config['server']

            # 检查是否为 SOCKS5 代理
            if proxy_server.startswith('socks'):
                try:
                    import socks
                    self._log(f"使用 SOCKS5 代理：{proxy_server}")
                except ImportError:
                    self._log("❌ SOCKS5 代理需要安装依赖：", 'error')
                    self._log("   请运行：pip install requests[socks]", 'error')
                    return False

            proxies = {
                'http': proxy_server,
                'https': proxy_server
            }

        for attempt in range(1, max_retries + 1):
            try:
                self._log(f"下载 {label} (尝试 {attempt}/{max_retries})...")
                resp = requests.get(url, headers=headers, stream=True, timeout=30, proxies=proxies)
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                written = 0

                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        if self.cancel_flag:
                            return False
                        if chunk:
                            f.write(chunk)
                            written += len(chunk)
                            if total > 0 and self._progress:
                                self._progress(written / total * 100, label)

                self._log(f"✅ {label} 下载完成 ({written // 1024} KB)")
                return True

            except requests.exceptions.RequestException as e:
                self._log(f"⚠️ 下载失败（{label}，尝试 {attempt}）：{e}", 'warning')
                if attempt < max_retries:
                    time.sleep(2)  # 等待 2 秒后重试
                else:
                    self._log(f"❌ 下载失败（{label}）：已达最大重试次数", 'error')
                    return False
            except Exception as e:
                self._log(f"❌ 下载异常（{label}）：{e}", 'error')
                return False

        return False

    def _merge_files(self, video_path, audio_path, output_path, keep_sources=True):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self._log("⚠️ 未找到 ffmpeg，跳过合并")
            self._log(f"   视频：{video_path}")
            self._log(f"   音频：{audio_path}")
            # 至少把视频文件移过去
            shutil.move(video_path, output_path)
            return False

        cmd = [
            ffmpeg, "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c", "copy",
            "-map", "0:v?",
            "-map", "1:a?",
            output_path
        ]
        self._log("正在合并音视频...")
        try:
            # 不解码 ffmpeg 输出，避免 Windows GBK 编码崩溃
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300)
            if result.returncode == 0:
                if keep_sources:
                    # 合并成功后，单独保留视频流与音频流
                    base = os.path.splitext(output_path)[0]
                    video_keep = base + ".video.mp4"
                    audio_keep = base + ".audio.m4a"
                    try:
                        if os.path.exists(video_path) and video_path != video_keep:
                            shutil.move(video_path, video_keep)
                        if audio_path and os.path.exists(audio_path) and audio_path != audio_keep:
                            shutil.move(audio_path, audio_keep)
                        self._log(f"✅ 已单独保存视频流：{os.path.basename(video_keep)}")
                        self._log(f"✅ 已单独保存音频流：{os.path.basename(audio_keep)}")
                    except Exception as e:
                        self._log(f"⚠️ 保留分离流失败（主文件已合并）：{e}", 'warning')
                else:
                    os.remove(video_path)
                    os.remove(audio_path)
                return True
            err = result.stderr.decode("utf-8", "replace") if isinstance(result.stderr, bytes) else result.stderr
            self._log(f"   ffmpeg 错误：{err[:300]}")
            return False
        except Exception as e:
            self._log(f"   合并异常：{e}")
            return False


# ============================================================
# 环境检查
# ============================================================
def check_playwright_env():
    """返回 (ok: bool, message: str)"""
    if not PLAYWRIGHT_AVAILABLE:
        return False, "Playwright 未安装\n请运行：pip install playwright"
    try:
        with sync_playwright() as pw:
            pw.chromium.launch(headless=True).close()
        return True, "✅ Playwright + Chromium 已就绪"
    except Exception as e:
        return False, f"Chromium 未安装\n请运行：playwright install chromium"


# ============================================================
# 保留旧接口别名，兼容可能直接导入 PlaywrightBilibiliDownloader 的代码
# ============================================================
PlaywrightBilibiliDownloader = BilibiliEngine


# ---- CLI 测试入口 ----

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法：python bilibili_engine.py <B站视频链接> [清晰度]")
        sys.exit(1)

    url = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else "最佳质量"

    engine = BilibiliEngine(
        log_callback=print,
        progress_callback=lambda p, t: print(f"\r  进度：{p:.1f}%  {t}", end='', flush=True),
        status_callback=lambda s: print(f"\n状态：{s}"),
    )
    engine.download(url, ".", quality=quality)
