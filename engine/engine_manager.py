"""
引擎注册中心

管理所有下载引擎，提供：
1. 引擎注册/取消注册
2. 根据 URL 自动选择合适的引擎
3. 统一的下载入口
"""

import logging
from typing import Optional, Type, Dict, List

from .base_engine import BaseDownloadEngine
from .yt_dlp_engine import YtDlpEngine, YTDLP_AVAILABLE
from .bilibili_engine import BilibiliEngine, PLAYWRIGHT_AVAILABLE

logger = logging.getLogger(__name__)


class EngineManager:
    """
    引擎管理器

    使用方式：
        mgr = EngineManager()
        mgr.register(BilibiliEngine)  # 优先注册专用引擎
        mgr.register(YtDlpEngine)     # 通用引擎作为后备

        engine_class = mgr.detect(url)          # 自动选择
        engine = mgr.create(engine_class, ...)  # 创建实例
        engine.download(url, output_dir, quality)
    """

    def __init__(self):
        self._registry: Dict[str, Type[BaseDownloadEngine]] = {}
        self._default_engine: Optional[Type[BaseDownloadEngine]] = None

    # ---- 引擎注册 ----

    def register(self, engine_class: Type[BaseDownloadEngine], set_default: bool = False):
        """
        注册一个引擎类

        :param engine_class: 继承自 BaseDownloadEngine 的类
        :param set_default: 是否设为默认引擎（通用引擎应设为默认）
        """
        engine_id = engine_class.get_engine_id()
        self._registry[engine_id] = engine_class

        if set_default:
            self._default_engine = engine_class

        # 如果该引擎的域名列表为空，自动设为默认
        if not engine_class.get_supported_domains():
            self._default_engine = engine_class

        logger.debug(f"注册引擎：{engine_class.get_engine_name()} (id={engine_id})")

    def unregister(self, engine_id: str):
        """取消注册"""
        removed = self._registry.pop(engine_id, None)
        if removed and self._default_engine and self._default_engine.get_engine_id() == engine_id:
            self._default_engine = None
        logger.debug(f"取消注册引擎：{engine_id}")

    def get_engine(self, engine_id: str) -> Optional[Type[BaseDownloadEngine]]:
        """按 ID 获取引擎类"""
        return self._registry.get(engine_id)

    def list_engines(self) -> List[Type[BaseDownloadEngine]]:
        """列出所有已注册的引擎"""
        return list(self._registry.values())

    def list_engine_info(self) -> List[dict]:
        """列出引擎信息（供 GUI 下拉框使用）"""
        result = []
        for eng in self._registry.values():
            domains = eng.get_supported_domains()
            tag = "(通用)" if not domains else ", ".join(domains[:3])
            result.append({
                'id': eng.get_engine_id(),
                'name': eng.get_engine_name(),
                'tag': tag,
            })
        return result

    # ---- 引擎检测 ----

    def detect(self, url: str) -> Optional[Type[BaseDownloadEngine]]:
        """
        根据 URL 自动选择最合适的引擎

        优先级：
        1. 专用引擎（域名匹配）
        2. 默认/通用引擎（作为后备）

        :return: 引擎类，或 None（无可用引擎）
        """
        if not url:
            return None

        matched = None

        # 第一轮：找专用引擎
        for engine_class in self._registry.values():
            if engine_class.can_handle(url):
                domains = engine_class.get_supported_domains()
                if domains:
                    # 有特定域名列表 → 专用引擎，优先返回
                    logger.debug(f"URL 匹配专用引擎：{engine_class.get_engine_name()}")
                    return engine_class
                else:
                    # 通用引擎，记住但继续找专用引擎
                    matched = engine_class

        # 第二轮：返回通用引擎作为后备
        if matched:
            logger.debug(f"使用通用引擎：{matched.get_engine_name()}")
            return matched

        # 如果连通用引擎都没有，返回默认引擎
        if self._default_engine:
            return self._default_engine

        return None

    def detect_with_info(self, url: str) -> dict:
        """
        检测并返回详细信息

        :return: {
            'engine_class': Type[BaseDownloadEngine] | None,
            'engine_name': str,
            'engine_id': str,
            'is_specialized': bool,      # 是否为专用引擎
            'detected_platform': str,    # 检测到的平台名
        }
        """
        result = {
            'engine_class': None,
            'engine_name': '未知',
            'engine_id': '',
            'is_specialized': False,
            'detected_platform': '无法识别',
        }

        # 找专用引擎
        for engine_class in self._registry.values():
            domains = engine_class.get_supported_domains()
            if domains and engine_class.can_handle(url):
                result['engine_class'] = engine_class
                result['engine_name'] = engine_class.get_engine_name()
                result['engine_id'] = engine_class.get_engine_id()
                result['is_specialized'] = True
                result['detected_platform'] = ', '.join(domains[:2])
                return result

        # 通用引擎
        for engine_class in self._registry.values():
            if not engine_class.get_supported_domains() and engine_class.can_handle(url):
                result['engine_class'] = engine_class
                result['engine_name'] = engine_class.get_engine_name()
                result['engine_id'] = engine_class.get_engine_id()
                result['is_specialized'] = False
                result['detected_platform'] = '通用'
                return result

        return result

    # ---- 创建实例 ----

    def create(
        self,
        engine_id_or_url: str,
        progress_callback=None,
        log_callback=None,
        status_callback=None,
        **kwargs,
    ) -> Optional[BaseDownloadEngine]:
        """
        创建引擎实例

        :param engine_id_or_url: 引擎 ID（如 'YtDlpEngine'）或视频 URL（自动检测）
        :param kwargs: 引擎特有参数（proxy, headless 等）
        """
        # 如果传入的是 URL，自动检测
        if engine_id_or_url.startswith(('http://', 'https://')):
            engine_class = self.detect(engine_id_or_url)
            if engine_class is None:
                return None
        else:
            engine_class = self._registry.get(engine_id_or_url)
            if engine_class is None:
                return None

        try:
            return engine_class(
                progress_callback=progress_callback,
                log_callback=log_callback,
                status_callback=status_callback,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"创建引擎实例失败：{e}")
            return None


# ---- 全局单例 ----

_engine_manager: Optional[EngineManager] = None


def get_engine_manager() -> EngineManager:
    """
    获取全局引擎管理器单例。
    首次调用时自动注册所有可用引擎：
    - BilibiliEngine（B站专用，Playwright）
    - YtDlpEngine（通用引擎，yt-dlp）
    """
    global _engine_manager
    if _engine_manager is None:
        _engine_manager = EngineManager()

        # 注册专用引擎
        if PLAYWRIGHT_AVAILABLE:
            _engine_manager.register(BilibiliEngine)

        # 注册通用引擎（设为默认）
        if YTDLP_AVAILABLE:
            _engine_manager.register(YtDlpEngine, set_default=True)

        logger.info(
            f"引擎管理器已初始化，已注册 {len(_engine_manager._registry)} 个引擎"
        )

    return _engine_manager


# ---- CLI 测试 ----

if __name__ == "__main__":
    import sys

    mgr = get_engine_manager()
    print("已注册引擎：")
    for info in mgr.list_engine_info():
        print(f"  [{info['id']}] {info['name']} — {info['tag']}")

    if len(sys.argv) > 1:
        url = sys.argv[1]
        detected = mgr.detect_with_info(url)
        print(f"\n链接：{url}")
        print(f"  检测结果：{detected['engine_name']}")
        print(f"  平台：{detected['detected_platform']}")
        print(f"  专用引擎：{detected['is_specialized']}")
    else:
        print("\n用法：python engine_manager.py <视频链接>")
