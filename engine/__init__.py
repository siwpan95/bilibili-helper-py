"""
引擎包 - 多平台视频下载引擎架构

支持引擎：
- YtDlpEngine：基于 yt-dlp 的通用引擎（支持 1800+ 站点）
- BilibiliEngine：基于 Playwright 浏览器自动化的 B站专用引擎
"""

from .base_engine import BaseDownloadEngine
from .engine_manager import EngineManager, get_engine_manager
from .yt_dlp_engine import YtDlpEngine
from .bilibili_engine import BilibiliEngine

__all__ = [
    'BaseDownloadEngine',
    'EngineManager', 'get_engine_manager',
    'YtDlpEngine',
    'BilibiliEngine',
]
