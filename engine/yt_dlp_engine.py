"""
yt-dlp 通用视频下载引擎

基于 yt-dlp Python API，支持 1800+ 站点：
- YouTube、B站、抖音/TikTok、Twitter/X、Instagram 等

使用方式：
    engine = YtDlpEngine(progress_callback=..., log_callback=...)
    engine.download("https://www.youtube.com/watch?v=xxx", "./output", "1080P")
"""

import os
import sys
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from .base_engine import BaseDownloadEngine

logger = logging.getLogger(__name__)

# ---- 检测 yt-dlp 是否可用 ----
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    yt_dlp = None


# ---- 清晰度 → yt-dlp format 字符串映射 ----
QUALITY_FORMAT_MAP = {
    "最佳质量": "bestvideo+bestaudio/best",
    "1080P":     "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720P":      "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480P":      "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "仅音频":     "bestaudio/best",
}


class YtDlpEngine(BaseDownloadEngine):
    """yt-dlp 通用下载引擎"""

    # ---- 类级别元信息 ----

    @classmethod
    def get_engine_name(cls) -> str:
        return "yt-dlp（通用）"

    @classmethod
    def get_supported_domains(cls) -> list:
        return []  # 空列表 = 通用引擎，支持所有域名

    @classmethod
    def is_available(cls) -> bool:
        """检查 yt-dlp + ffmpeg 是否可用"""
        return YTDLP_AVAILABLE and shutil.which("ffmpeg") is not None

    # ---- 公开接口 ----

    def validate_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        yt-dlp 几乎能处理任何 URL，所以验证比较宽松
        只做基本的 URL 格式检查
        """
        if not url or not isinstance(url, str):
            return False, None, None

        url = url.strip()
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, None, None
            return True, url, parsed.netloc
        except Exception:
            return False, None, None

    def get_video_info(self, url: str, **kwargs) -> Optional[dict]:
        """获取视频元信息（标题、时长、格式等）"""
        if not YTDLP_AVAILABLE:
            return None

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
            **self._common_opts(kwargs),
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    'title': info.get('title', ''),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', ''),
                    'webpage_url': info.get('webpage_url', url),
                    'extractor': info.get('extractor', ''),
                    'formats_count': len(info.get('formats', [])),
                }
        except Exception as e:
            logger.warning(f"获取视频信息失败：{e}")
            return None

    def download(
        self,
        url: str,
        output_dir: str,
        quality: str = "最佳质量",
        **kwargs
    ) -> bool:
        """
        使用 yt-dlp 下载视频

        :param url: 视频 URL
        :param output_dir: 输出目录
        :param quality: 清晰度
        :param kwargs: 额外选项
            - headless: bool，无头模式（yt-dlp 不需要浏览器，忽略）
            - proxy: str，代理地址
            - cookies_from_browser: str，从浏览器读取 Cookie
            - timeout: int，超时秒数
        """
        if not YTDLP_AVAILABLE:
            self._log("❌ yt-dlp 未安装，请运行：pip install yt-dlp", 'error')
            return False

        valid, cleaned_url, _ = self.validate_url(url)
        if not valid:
            self._log(f"❌ 无效链接：{url}", 'error')
            return False

        url = cleaned_url
        self.cancel_flag = False
        self._last_filepath = None
        os.makedirs(output_dir, exist_ok=True)

        # ffmpeg 预检（合并音视频需要）
        has_ffmpeg = shutil.which("ffmpeg") is not None
        if not has_ffmpeg:
            self._log("⚠️ 未检测到 ffmpeg，音视频将无法合并为单个文件", 'warning')
            self._log("   安装 ffmpeg 后重启即可生效", 'warning')

        # 选择清晰度格式
        format_str = QUALITY_FORMAT_MAP.get(quality, QUALITY_FORMAT_MAP["最佳质量"])

        self._log("=" * 55)
        self._log(f"[yt-dlp 通用引擎]")
        self._log(f"链接：{url}")
        self._log(f"清晰度：{quality}  →  {format_str}")
        self._log(f"输出目录：{output_dir}")
        self._log("=" * 55)

        # 构建 yt-dlp 选项
        ydl_opts = {
            **self._common_opts(kwargs),
            'outtmpl': os.path.join(output_dir, '%(title).100s.%(ext)s'),
            'format': format_str,
            'merge_output_format': 'mp4',
            'progress_hooks': [self._progress_hook],
            'postprocessor_hooks': [self._postprocessor_hook],
        }

        # 代理设置（支持嵌入用户名密码）
        proxy_url = kwargs.get('proxy')
        proxy_user = kwargs.get('proxy_username', '')
        proxy_pass = kwargs.get('proxy_password', '')
        if proxy_url and (proxy_user or proxy_pass):
            # 把认证信息嵌入代理 URL：http://user:pass@host:port
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(proxy_url)
            # 如果 URL 里还没有用户信息，嵌入进去
            if parsed.hostname and not parsed.username:
                netloc = ''
                if proxy_user:
                    netloc += proxy_user
                if proxy_pass:
                    netloc += ':' + proxy_pass
                netloc += '@' + parsed.hostname
                if parsed.port:
                    netloc += ':' + str(parsed.port)
                proxy_url = urlunparse((parsed.scheme, netloc, parsed.path, '', '', ''))
                self._log(f"代理（含认证）：{parsed.scheme}://{parsed.hostname}:{parsed.port}")
            ydl_opts['proxy'] = proxy_url
        elif proxy_url:
            ydl_opts['proxy'] = proxy_url
            self._log(f"代理：{proxy_url}")

        # Cookie 来源（从浏览器读取登录态）
        cookies_from = kwargs.get('cookies_from_browser')
        if cookies_from:
            ydl_opts['cookiesfrombrowser'] = (cookies_from,)
            self._log(f"Cookie 来源：{cookies_from} 浏览器")

        self._status("正在解析视频信息...")
        self._progress(0, "准备中...")

        save_separate = kwargs.get('save_separate_streams', True)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

            if self.cancel_flag:
                self._log("⚠️ 已取消")
                return False

            # 获取最终输出文件路径
            final_path = None
            if info:
                rd = info.get('requested_downloads') or []
                if rd and rd[0].get('filepath'):
                    final_path = rd[0]['filepath']
            if not final_path and getattr(self, '_last_filepath', None):
                final_path = self._last_filepath

            # 单独保存分离的视频流与音频流
            if save_separate:
                self._save_separate_streams(final_path, quality)

            self._progress(100, "完成")
            self._status("下载完成")
            self._log("✅ 下载完成")
            return True

        except yt_dlp.utils.DownloadError as e:
            self._log(f"❌ 下载失败：{e}", 'error')
            return False
        except Exception as e:
            self._log(f"❌ 异常：{e}", 'error')
            return False

    # ---- 内部方法 ----

    def _common_opts(self, kwargs: dict) -> dict:
        """yt-dlp 公共选项"""
        return {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'noprogress': True,
            'extract_flat': False,
            'socket_timeout': kwargs.get('timeout', 60),
        }

    def _progress_hook(self, d: dict):
        """yt-dlp 下载进度钩子"""
        status = d.get('status')

        if self.cancel_flag:
            raise yt_dlp.utils.DownloadError("用户取消")

        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('_speed_str', '')
            eta = d.get('_eta_str', '')
            filename = os.path.basename(d.get('filename', ''))

            if total and total > 0:
                percent = min(downloaded / total * 100, 99.0)
                info = f"{filename}  {speed}" if speed else filename
                self._progress(percent, info)
            else:
                # 无法获取总大小，显示已下载字节数 + 速度
                dl_mb = downloaded / 1024 / 1024
                speed_str = f" {speed}" if speed else ""
                label = f"{filename}  {dl_mb:.1f} MB{speed_str}"
                self._progress(0, label)  # 进度条不动，但状态文字更新

            self._status(f"下载中 {speed}  ETA {eta}" if speed and eta else "下载中...")

        elif status == 'finished':
            self._progress(99, "处理中...")

        elif status == 'error':
            self._log(f"⚠️ 下载出错")

    def _postprocessor_hook(self, d: dict):
        """yt-dlp 后处理钩子（合并音视频等）"""
        status = d.get('status')
        pp = d.get('postprocessor', '')

        if self.cancel_flag:
            raise yt_dlp.utils.DownloadError("用户取消")

        if status == 'started':
            self._status(f"处理：{pp}...")
            self._log(f"  处理：{pp}")
        elif status == 'finished':
            info = d.get('info_dict') or {}
            fp = info.get('filepath') or info.get('filename') or d.get('filename')
            if fp:
                self._last_filepath = fp
            self._status(f"{pp} 完成")

    def _save_separate_streams(self, final_path, quality):
        """
        从合并后的文件拆分出单独的视频流和音频流（仅 remux，不重新编码）。
        生成：<标题>.video.mp4 与 <标题>.audio.m4a
        """
        if not final_path or not os.path.exists(final_path):
            return
        if quality == "仅音频":
            # 仅音频模式：输出文件本身就是音频，无需拆分
            self._log("ℹ️ 仅音频模式，已保存音频文件")
            return

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self._log("⚠️ 未找到 ffmpeg，无法拆分音视频流", 'warning')
            return

        base, _ = os.path.splitext(final_path)
        video_only = base + ".video.mp4"
        audio_only = base + ".audio.m4a"

        # 拆分视频流
        if not os.path.exists(video_only):
            try:
                cmd = [ffmpeg, "-y", "-i", final_path, "-an", "-c", "copy", video_only]
                # 不解码 ffmpeg 输出，避免 Windows GBK 编码崩溃
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
                if os.path.exists(video_only) and os.path.getsize(video_only) > 0:
                    self._log(f"✅ 已单独保存视频流：{os.path.basename(video_only)}")
                elif os.path.exists(video_only):
                    os.remove(video_only)
            except Exception as e:
                self._log(f"⚠️ 拆分视频流失败：{e}", 'warning')

        # 拆分音频流
        if not os.path.exists(audio_only):
            try:
                cmd = [ffmpeg, "-y", "-i", final_path, "-vn", "-c", "copy", audio_only]
                # 不解码 ffmpeg 输出，避免 Windows GBK 编码崩溃
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
                if os.path.exists(audio_only) and os.path.getsize(audio_only) > 0:
                    self._log(f"✅ 已单独保存音频流：{os.path.basename(audio_only)}")
                elif os.path.exists(audio_only):
                    os.remove(audio_only)
            except Exception as e:
                self._log(f"⚠️ 拆分音频流失败：{e}", 'warning')


# ---- 便捷函数 ----

def check_ytdlp_availability():
    """检查 yt-dlp 环境"""
    messages = []
    if not YTDLP_AVAILABLE:
        messages.append("❌ yt-dlp 未安装")
        messages.append("   安装：pip install yt-dlp")
    else:
        messages.append(f"✅ yt-dlp 已安装")

    if shutil.which("ffmpeg"):
        messages.append("✅ ffmpeg 已就绪")
    else:
        messages.append("⚠️ ffmpeg 未找到（合并音视频需要）")

    return YTDLP_AVAILABLE and shutil.which("ffmpeg") is not None, "\n".join(messages)


# ---- CLI 测试入口 ----

if __name__ == "__main__":
    if not YTDLP_AVAILABLE:
        print("请先安装 yt-dlp：pip install yt-dlp")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("用法：python yt_dlp_engine.py <视频链接> [清晰度]")
        sys.exit(1)

    url = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else "最佳质量"

    engine = YtDlpEngine(
        log_callback=print,
        progress_callback=lambda p, t: print(f"\r  进度：{p:.1f}%  {t}", end='', flush=True),
        status_callback=lambda s: print(f"\n状态：{s}"),
    )
    engine.download(url, ".", quality=quality)
