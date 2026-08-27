---
name: bilibili-helper
description: Maintain bilibili-helper-py (G:/tools/crawler/bilibili-helper-py). Bilibili video downloader with Playwright.
agent_created: true
---

# bilibili-helper-py（B站助手）维护

## 概述
B站视频/弹幕下载与处理：Playwright、合集批量、清晰度选择、SOCKS5 代理；engine/ 多引擎架构。

## 结构
- ui.py：GUI；main.py：入口；engine/：下载引擎；tests/：test_features.py
- output/：下载输出（资产目录，已 gitignore，约 5GB）；download.log

## 已知陷阱
- Playwright 浏览器内核需预装
- 资产标注（2026-08-24）：output/ 与 download.log 不进版本库

## 谱系（crawler-kit，2026-08-27）
- cookie_utils（Playwright 登录态导出）已提炼为 crawl-hub/crawler_kit/session.py（共享库规范）；本仓保留内联副本，两侧改动需手工对照。
