"""
视频下载引擎抽象基类

所有平台引擎（B站、YouTube、抖音等）都继承此类，统一接口。
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Callable


class BaseDownloadEngine(ABC):
    """视频下载引擎抽象基类"""

    def __init__(
        self,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        :param progress_callback: 进度回调 (percent: float, label: str)
        :param log_callback: 日志回调 (message: str)
        :param status_callback: 状态回调 (status_text: str)
        """
        self.cancel_flag = False
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.status_callback = status_callback

    # ---------- 类方法（无需实例化即可调用） ----------

    @classmethod
    @abstractmethod
    def get_engine_name(cls) -> str:
        """返回引擎显示名称，如 'yt-dlp (通用)'、'Playwright (B站专用)'"""
        ...

    @classmethod
    def get_engine_id(cls) -> str:
        """返回引擎唯一标识，如 'yt_dlp'、'bilibili_playwright'"""
        return cls.__name__

    @classmethod
    @abstractmethod
    def get_supported_domains(cls) -> list:
        """
        返回支持的域名列表，如 ['bilibili.com', 'b23.tv']
        空列表表示支持所有域名（通用引擎）
        """
        ...

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """
        检查该引擎是否能处理指定 URL。
        默认按域名匹配，通用引擎（空域名列表）总是返回 True。
        """
        domains = cls.get_supported_domains()
        if not domains:
            return True  # 空列表 = 通用引擎

        from urllib.parse import urlparse
        try:
            hostname = urlparse(url).hostname or ''
        except Exception:
            return False
        return any(domain.lower() in hostname.lower() for domain in domains)

    # ---------- 公开接口 ----------

    @abstractmethod
    def download(
        self,
        url: str,
        output_dir: str,
        quality: str = "最佳质量",
        **kwargs
    ) -> bool:
        """
        下载视频

        :param url: 视频页面 URL
        :param output_dir: 输出目录
        :param quality: 清晰度，如 "最佳质量"、"1080P"、"720P"、"480P"、"仅音频"
        :param kwargs: 引擎特有参数
        :return: 成功返回 True，反之 False
        """
        ...

    @abstractmethod
    def validate_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        验证 URL 是否合法

        :return: (is_valid: bool, cleaned_url: str|None, info: str|None)
                 info 可以是视频 ID、平台名等附加信息
        """
        ...

    def cancel(self):
        """取消当前下载任务"""
        self.cancel_flag = True

    def get_video_info(self, url: str, **kwargs) -> Optional[dict]:
        """
        获取视频元信息（标题、时长等），无需完整下载

        :return: dict 或 None
        """
        return None

    # ---------- 内部辅助方法 ----------

    def _log(self, msg: str, level: str = 'info'):
        """统一日志输出"""
        if self.log_callback:
            self.log_callback(str(msg))

    def _status(self, msg: str):
        """更新状态文字"""
        if self.status_callback:
            self.status_callback(str(msg))

    def _progress(self, percent: float, label: str = ''):
        """更新进度"""
        if self.progress_callback:
            self.progress_callback(percent, label)
