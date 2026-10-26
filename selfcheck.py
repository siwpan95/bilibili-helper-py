# -*- coding: utf-8 -*-
"""bilibili-helper-py · 无头自检（不启动 tkinter，不启动浏览器/网络）。

验证 engine/bilibili_engine.py 的纯校验逻辑：
1. B站 URL / 纯 BV 号识别与短链接归一；
2. 文件名清理、清晰度与超时参数校验、代理配置校验；
3. 引擎的 B站域名路由（can_handle）与降级行为（未装 Playwright 也能 import）。

Playwright 未安装时本自检仍应通过（PLAYWRIGHT_AVAILABLE=False）。
"""

from __future__ import annotations

import logging
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from engine.bilibili_engine import (      # noqa: E402
    PLAYWRIGHT_AVAILABLE,
    BilibiliEngine,
    validate_bilibili_url,
    validate_proxy_config,
    validate_quality,
    validate_timeout,
    sanitize_filename,
)

# 自检时静音“无效清晰度”警告，保持输出干净
logging.getLogger("engine.bilibili_engine").setLevel(logging.ERROR)


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def check_urls() -> None:
    valid, url, video_id = validate_bilibili_url(
        "https://www.bilibili.com/video/BV1xx411c7mD?p=2")
    check(valid is True and video_id == "BV1xx411c7mD",
          f"完整 URL 解析错误: {(valid, url, video_id)!r}")

    valid, url, video_id = validate_bilibili_url("BV1xx411c7mD")
    check(valid is True and video_id == "BV1xx411c7mD",
          "纯 BV 号未被识别")
    check(url == "https://www.bilibili.com/video/BV1xx411c7mD",
          f"纯 BV 号未补全 URL: {url!r}")

    valid, _url, _video_id = validate_bilibili_url("https://b23.tv/abc123")
    check(valid is True, "b23.tv 短链接未被识别")

    for bad in ("https://www.youtube.com/watch?v=xxx", "", None, "BV123"):
        valid, url, video_id = validate_bilibili_url(bad)
        check(valid is False and url is None and video_id is None,
              f"非法输入未被拒绝: {bad!r}")


def check_filename_and_params() -> None:
    check(sanitize_filename("测试视频标题") == "测试视频标题", "正常标题被改动")
    cleaned = sanitize_filename('测试/视频*标题?<>:"|')
    check(cleaned == "测试视频标题", f"非法字符清理错误: {cleaned!r}")
    check(sanitize_filename(None) == "bilibili_video", "None 标题未回退默认名")
    check(sanitize_filename("") == "bilibili_video", "空标题未回退默认名")
    check(len(sanitize_filename("a" * 200, max_length=100)) <= 100,
          "超长标题未被截断")

    check(validate_quality("1080P") == "1080P", "合法清晰度被改动")
    check(validate_quality("4K") == "最佳质量", "非法清晰度未回退默认")
    check(validate_quality("") == "最佳质量", "空清晰度未回退默认")

    check(validate_timeout(30) == 30, "合法超时值被改动")
    check(validate_timeout(5) == 10, "过小超时未抬到下限")
    check(validate_timeout(500) == 300, "过大超时未压到上限")
    check(validate_timeout("abc") == 30, "非法超时未回退默认")
    check(validate_timeout(None) == 30, "None 超时未回退默认")


def check_proxy() -> None:
    valid, config, error = validate_proxy_config("http://127.0.0.1:7890")
    check(valid is True and error == "", f"合法代理被拒绝: {error!r}")
    check(config["server"] == "http://127.0.0.1:7890", "代理 server 配置错误")
    check("localhost" in config["bypass"], "代理 bypass 配置缺失")

    valid, config, error = validate_proxy_config(
        "socks5://user:pass@127.0.0.1:1080", "user", "pass")
    check(valid is True and config["username"] == "user"
          and config["password"] == "pass", "SOCKS5 认证代理配置错误")

    valid, config, error = validate_proxy_config("127.0.0.1:7890")
    check(valid is False and config is None and "协议" in error,
          f"缺协议代理未被拒绝: {(valid, config, error)!r}")


def check_routing() -> None:
    check(BilibiliEngine.get_supported_domains() == ["bilibili.com", "b23.tv"],
          "B站引擎域名列表错误")
    check(BilibiliEngine.can_handle("https://www.bilibili.com/video/BV1xx411c7mD"),
          "B站 URL 未被本引擎接管")
    check(BilibiliEngine.can_handle("https://b23.tv/abc123"),
          "b23.tv 未本引擎接管")
    check(not BilibiliEngine.can_handle("https://www.youtube.com/watch?v=xxx"),
          "非 B站 URL 被错误接管")
    check(BilibiliEngine.is_available() == PLAYWRIGHT_AVAILABLE,
          "is_available 与 PLAYWRIGHT_AVAILABLE 不一致")


def main() -> int:
    try:
        check_urls()
        check_filename_and_params()
        check_proxy()
        check_routing()
        print(
            "selfcheck ok: URL/纯BV/短链识别与非法输入拒绝；文件名清理、"
            "清晰度/超时/代理参数校验；B站域名路由正确"
            f"（Playwright 可用={PLAYWRIGHT_AVAILABLE}，纯逻辑用例均不依赖浏览器）"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
