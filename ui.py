"""
UI 模块：万能视频下载助手主窗口
包含 MainWindow 类和所有 GUI / 业务逻辑
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import json
import shutil
import logging
from pathlib import Path

# ============================================================
# 日志配置：同时输出到文件和 GUI
# ============================================================
LOG_FILE = Path(__file__).parent / "download.log"

logger = logging.getLogger('bilibili_helper')
logger.setLevel(logging.DEBUG)

# 文件处理器（记录所有日志）
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# 控制台处理器（仅 INFO 及以上）
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

PROJECT_ROOT = Path(__file__).parent

# ---- 引擎包导入 ----
from engine import (
    EngineManager, get_engine_manager,
    YtDlpEngine, BilibiliEngine,
)

# ---- 工具函数导入（已从 playwright_engine 合并到 engine/bilibili_engine）----
from engine.bilibili_engine import (
    validate_proxy_config,
    test_proxy_connection,
    check_playwright_env,
    PLAYWRIGHT_AVAILABLE as PLAYWRIGHT_AVAILABLE,
)


# ============================================================
# GUI 主窗口
# ============================================================
class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("万能视频下载助手 v3.0")
        self.root.geometry("800x700")
        self.root.resizable(True, True)

        self.config_file = PROJECT_ROOT / "config.json"
        self.load_config()

        # 初始化引擎管理器
        self.engine_mgr = get_engine_manager()

        self.current_downloader = None
        self.setup_ui()

        # URL 变更时自动检测平台
        self._after_id = None
        self.txt_url.bind('<<Modified>>', self._on_url_changed)
        self._detect_engine(self.get_urls()[0] if self.get_urls() else '')

        logger.info("GUI 主窗口已启动")
        logger.debug(f"配置文件：{self.config_file}")
        logger.info(f"已注册引擎：{len(self.engine_mgr.list_engines())} 个")

    def load_config(self):
        """加载配置，包含代理设置"""
        self.config = {
            "output_dir": str(PROJECT_ROOT / "output"),
            "quality": "最佳质量",
            "engine_mode": "auto",           # auto / 手动引擎ID
            "playwright_headless": False,
            "proxy_enabled": False,
            "proxy_server": "",
            "proxy_username": "",
            "proxy_password": "",
            "proxy_bypass": "localhost,127.0.0.1",
            "cookies_from_browser": "无",     # 无 / chrome / firefox / edge ...
            "save_separate_streams": True,  # 合并后是否单独保留视频流/音频流
        }
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
                    logger.debug(f"配置已加载：{loaded}")
            except Exception as e:
                logger.error(f"加载配置失败：{e}")

    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logger.debug("配置已保存")
        except Exception as e:
            logger.error(f"保存配置失败：{e}")

    def setup_ui(self):
        # ---- URL 输入 ----
        frm_url = ttk.LabelFrame(self.root, text="视频链接（支持多个，每行一个；支持合集）", padding=8)
        frm_url.pack(fill="x", padx=10, pady=(10, 5))

        self.txt_url = scrolledtext.ScrolledText(frm_url, height=4, font=("微软雅黑", 10))
        self.txt_url.pack(fill="x")
        self.txt_url.insert("1.0", "")

        # ---- 设置区 ----
        frm_cfg = ttk.LabelFrame(self.root, text="下载设置", padding=8)
        frm_cfg.pack(fill="x", padx=10, pady=5)

        row = 0

        # 行0：清晰度 + 保存位置
        ttk.Label(frm_cfg, text="清晰度：").grid(row=row, column=0, sticky="w", padx=(0, 5))
        self.cmb_quality = ttk.Combobox(
            frm_cfg,
            values=["最佳质量", "1080P", "720P", "480P", "仅音频"],
            state="readonly",
            width=12
        )
        self.cmb_quality.set(self.config.get("quality", "最佳质量"))
        self.cmb_quality.grid(row=row, column=1, sticky="w", padx=(0, 20))

        ttk.Label(frm_cfg, text="保存位置：").grid(row=row, column=2, sticky="w", padx=(0, 5))
        self.lbl_output = ttk.Label(
            frm_cfg, text=self.config["output_dir"],
            foreground="blue", font=("微软雅黑", 9)
        )
        self.lbl_output.grid(row=row, column=3, sticky="w", padx=(0, 5))
        ttk.Button(frm_cfg, text="选择文件夹", command=self.choose_output_dir).grid(
            row=row, column=4, sticky="w", padx=(5, 0))
        row += 1

        # 行1：Playwright 选项
        frm_pw = ttk.Frame(frm_cfg)
        frm_pw.grid(row=row, column=0, columnspan=5, sticky="w", pady=(8, 0))

        self.var_pw_headless = tk.BooleanVar(value=not self.config.get("playwright_headless", False))
        ttk.Checkbutton(
            frm_pw, text="显示浏览器窗口（勾选后可见浏览器，可手动登录 Bilibili）",
            variable=self.var_pw_headless,
            command=lambda: self.config.update({"playwright_headless": not self.var_pw_headless.get()})
        ).pack(side="left", padx=(0, 15))

        ttk.Label(frm_pw, text="首次使用建议勾选，登录一次后即可取消",
                  font=("微软雅黑", 8), foreground="gray").pack(side="left")
        row += 1

        # 行2：代理设置
        frm_proxy = ttk.Frame(frm_cfg)
        frm_proxy.grid(row=row, column=0, columnspan=5, sticky="w", pady=(8, 0))

        self.var_proxy_enabled = tk.BooleanVar(value=self.config.get("proxy_enabled", False))
        self.chk_proxy = ttk.Checkbutton(
            frm_proxy, text="使用代理",
            variable=self.var_proxy_enabled,
            command=self.toggle_proxy_ui
        )
        self.chk_proxy.pack(side="left", padx=(0, 10))

        ttk.Label(frm_proxy, text="代理地址：").pack(side="left", padx=(0, 5))
        self.ent_proxy_server = ttk.Entry(frm_proxy, width=25)
        self.ent_proxy_server.insert(0, self.config.get("proxy_server", ""))
        self.ent_proxy_server.pack(side="left", padx=(0, 5))

        ttk.Button(frm_proxy, text="测试代理", command=self.test_proxy).pack(side="left", padx=(0, 10))

        ttk.Label(frm_proxy, text="（支持 HTTP/HTTPS/SOCKS5）",
                  font=("微软雅黑", 8), foreground="gray").pack(side="left")

        # 行3：代理认证（默认隐藏）
        self.frm_proxy_auth = ttk.Frame(frm_cfg)
        self.frm_proxy_auth.grid(row=row+1, column=0, columnspan=5, sticky="w", pady=(5, 0))
        
        ttk.Label(self.frm_proxy_auth, text="用户名：").pack(side="left", padx=(0, 5))
        self.ent_proxy_username = ttk.Entry(self.frm_proxy_auth, width=15)
        self.ent_proxy_username.insert(0, self.config.get("proxy_username", ""))
        self.ent_proxy_username.pack(side="left", padx=(0, 10))

        ttk.Label(self.frm_proxy_auth, text="密码：").pack(side="left", padx=(0, 5))
        self.ent_proxy_password = ttk.Entry(self.frm_proxy_auth, width=15, show="*")
        self.ent_proxy_password.insert(0, self.config.get("proxy_password", ""))
        self.ent_proxy_password.pack(side="left", padx=(0, 10))

        row += 2

        # 行3.5：Cookie 来源（通用引擎需要从浏览器读取登录态）
        frm_cookie = ttk.Frame(frm_cfg)
        frm_cookie.grid(row=row, column=0, columnspan=5, sticky="w", pady=(8, 0))
        row += 1

        ttk.Label(frm_cookie, text="Cookie 来源：").pack(side="left", padx=(0, 5))
        self.var_cookies_browser = tk.StringVar(
            value=self.config.get("cookies_from_browser", "无")
        )
        self.cmb_cookies = ttk.Combobox(
            frm_cookie, textvariable=self.var_cookies_browser,
            state="readonly", width=14,
            values=["无", "chrome", "firefox", "edge", "safari", "opera", "brave"]
        )
        self.cmb_cookies.pack(side="left", padx=(0, 10))
        ttk.Label(
            frm_cookie,
            text="（通用引擎下载需登录的视频时，选择浏览器）",
            font=("微软雅黑", 8), foreground="gray"
        ).pack(side="left")

        # 行4：引擎选择 + 平台检测
        frm_engine = ttk.Frame(frm_cfg)
        frm_engine.grid(row=row, column=0, columnspan=5, sticky="w", pady=(8, 0))

        ttk.Label(frm_engine, text="下载引擎：").pack(side="left", padx=(0, 5))
        self.var_engine_mode = tk.StringVar(value=self.config.get("engine_mode", "auto"))
        self.cmb_engine = ttk.Combobox(
            frm_engine, textvariable=self.var_engine_mode, state="readonly", width=28
        )
        self.cmb_engine.pack(side="left", padx=(0, 10))
        self.cmb_engine.bind('<<ComboboxSelected>>', self._on_engine_selected)

        # 平台检测标签
        self.lbl_platform = ttk.Label(
            frm_engine, text="", foreground="#07c160", font=("微软雅黑", 9)
        )
        self.lbl_platform.pack(side="left", padx=(0, 10))

        # 更新引擎下拉列表
        self._refresh_engine_combo()
        row += 1

        # 行5：是否单独保存分离的视频流/音频流
        frm_sep = ttk.Frame(frm_cfg)
        frm_sep.grid(row=row, column=0, columnspan=5, sticky="w", pady=(8, 0))
        row += 1

        self.var_save_separate = tk.BooleanVar(value=self.config.get("save_separate_streams", True))
        ttk.Checkbutton(
            frm_sep,
            text="同时单独保存分离的视频流和音频流（额外生成 .video.mp4 与 .audio.m4a）",
            variable=self.var_save_separate,
            command=lambda: self.config.update({"save_separate_streams": self.var_save_separate.get()})
        ).pack(side="left")

        # ---- 操作按钮 ----
        frm_btn = ttk.Frame(self.root, padding=(10, 8))
        frm_btn.pack(fill="x")

        self.btn_download = ttk.Button(frm_btn, text="开始下载", command=self.start_download)
        self.btn_download.pack(side="left", padx=(0, 10))

        self.btn_cancel = ttk.Button(frm_btn, text="取消下载", command=self.cancel_download, state="disabled")
        self.btn_cancel.pack(side="left", padx=(0, 10))

        ttk.Button(frm_btn, text="打开输出文件夹", command=self.open_output_dir).pack(side="left", padx=(0, 10))
        ttk.Button(frm_btn, text="检查依赖", command=self.check_deps).pack(side="left")
        ttk.Button(frm_btn, text="安装依赖", command=self.install_deps).pack(side="left", padx=(10, 0))

        # ---- 进度条 ----
        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=10, pady=(5, 0))

        self.lbl_status = ttk.Label(self.root, text="就绪", font=("微软雅黑", 9))
        self.lbl_status.pack(anchor="w", padx=10, pady=(2, 0))

        # ---- 日志区 ----
        frm_log = ttk.LabelFrame(self.root, text="下载日志", padding=5)
        frm_log.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        self.txt_log = scrolledtext.ScrolledText(
            frm_log, height=15, font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white"
        )
        self.txt_log.pack(fill="both", expand=True)

    # ---- UI 事件 ----
    def choose_output_dir(self):
        d = filedialog.askdirectory(initialdir=self.config["output_dir"])
        if d:
            self.config["output_dir"] = d
            self.lbl_output.config(text=d)
            self.save_config()
            logger.debug(f"输出目录已更改：{d}")

    def toggle_proxy_ui(self):
        """切换代理输入框的可用状态"""
        enabled = self.var_proxy_enabled.get()
        self.config["proxy_enabled"] = enabled
        self.save_config()

        if enabled:
            self.ent_proxy_server.config(state="normal")
            self.ent_proxy_username.config(state="normal")
            self.ent_proxy_password.config(state="normal")
        else:
            self.ent_proxy_server.config(state="disabled")
            self.ent_proxy_username.config(state="disabled")
            self.ent_proxy_password.config(state="disabled")

        logger.debug(f"代理设置：{enabled}")

    def test_proxy(self):
        """测试代理连接"""
        proxy_server = self.ent_proxy_server.get().strip()

        if not proxy_server:
            messagebox.showwarning("提示", "请先输入代理地址！")
            return

        if not test_proxy_connection:
            messagebox.showerror("错误", "test_proxy_connection 函数未加载！")
            return

        # 验证代理配置
        if validate_proxy_config:
            proxy_username = self.ent_proxy_username.get() if self.var_proxy_enabled.get() else ""
            proxy_password = self.ent_proxy_password.get() if self.var_proxy_enabled.get() else ""
            valid, proxy_config, error_msg = validate_proxy_config(
                proxy_server,
                proxy_username if proxy_username else None,
                proxy_password if proxy_password else None
            )

            if not valid:
                messagebox.showerror("代理配置错误", error_msg)
                return

        # 测试连接
        self.log("正在测试代理连接...")
        self.log(f"代理地址：{proxy_server}")

        def worker():
            if test_proxy_connection:
                success, message = test_proxy_connection(proxy_server, timeout=10)
                self.root.after(0, lambda: self.log(f"代理测试结果：{message}"))

                if success:
                    self.root.after(0, lambda: messagebox.showinfo("代理测试", message))
                else:
                    self.root.after(0, lambda: messagebox.showerror("代理测试失败", message))

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_engine_combo(self):
        """更新引擎下拉框选项"""
        options = [("自动检测（推荐）", "auto")]
        info_list = self.engine_mgr.list_engine_info()
        for info in info_list:
            options.append((f"{info['name']}  —  {info['tag']}", info['id']))
        values = [name for name, _ in options]
        self.cmb_engine['values'] = values
        # 恢复之前的选择
        saved = self.config.get("engine_mode", "auto")
        try:
            idx = [v for _, v in options].index(saved)
            self.cmb_engine.current(idx)
        except ValueError:
            self.cmb_engine.current(0)
            self.var_engine_mode.set("auto")

    def _on_engine_selected(self, event=None):
        """引擎手动选择"""
        selected = self.var_engine_mode.get()
        for info in self.engine_mgr.list_engine_info():
            if selected.startswith(info['name']):
                self.config["engine_mode"] = info['id']
                self.save_config()
                # 重新检测
                urls = self.get_urls()
                self._detect_engine(urls[0] if urls else '')
                return
        self.config["engine_mode"] = "auto"
        self.save_config()

    def _on_url_changed(self, event=None):
        """URL 输入变化时自动检测平台"""
        self.txt_url.edit_modified(False)
        if self._after_id:
            self.root.after_cancel(self._after_id)
        self._after_id = self.root.after(500, self._auto_detect)

    def _auto_detect(self):
        """自动检测平台"""
        urls = self.get_urls()
        self._detect_engine(urls[0] if urls else '')

    def _detect_engine(self, url=''):
        """检测 URL 对应的平台和引擎"""
        if not url:
            self.lbl_platform.config(text='', foreground='#888')
            return

        # 如果用户手动选择了引擎，跳过自动检测
        if self.config.get("engine_mode", "auto") != "auto":
            info_list = self.engine_mgr.list_engine_info()
            for info in info_list:
                if info['id'] == self.config["engine_mode"]:
                    self.lbl_platform.config(
                        text=f"🔧 手动：{info['name']}",
                        foreground='#07c160'
                    )
                    return

        # 自动检测
        detected = self.engine_mgr.detect_with_info(url)
        platform = detected.get('detected_platform', '未知')
        engine_name = detected.get('engine_name', '未知')
        is_spec = detected.get('is_specialized', False)

        if is_spec:
            self.lbl_platform.config(
                text=f"✅ {platform}  →  {engine_name}",
                foreground='#07c160'
            )
        else:
            self.lbl_platform.config(
                text=f"🌐 {platform}  →  {engine_name}",
                foreground='#576b95'
            )

    def get_urls(self):
        text = self.txt_url.get("1.0", "end").strip()
        return [l.strip() for l in text.splitlines() if l.strip()]

    def log(self, msg, level='info'):
        """
        统一的日志输出
        同时输出到 GUI 和 Python logging
        """
        # GUI 输出
        self.txt_log.insert("end", str(msg) + "\n")
        self.txt_log.see("end")

        # Python logging
        if level == 'error':
            logger.error(msg)
        elif level == 'warning':
            logger.warning(msg)
        else:
            logger.info(msg)

    def update_progress(self, percent, title=""):
        self.progress["value"] = percent
        status = f"[{percent:.1f}%] {str(title)[:50]}" if title else f"[{percent:.1f}%]"
        self.lbl_status.config(text=status)

    def set_ui_state(self, downloading):
        state = "disabled" if downloading else "normal"
        self.btn_download.config(state=state)
        self.txt_url.config(state="normal" if not downloading else "disabled")
        self.cmb_quality.config(state="disabled" if downloading else "readonly")
        self.btn_cancel.config(state="normal" if downloading else "disabled")

    # ---- 下载控制 ----
    def start_download(self):
        urls = self.get_urls()
        if not urls:
            messagebox.showwarning("提示", "请输入视频链接（支持 B站/YouTube/抖音等）！")
            return

        output_dir = self.config["output_dir"]
        os.makedirs(output_dir, exist_ok=True)
        quality = self.cmb_quality.get()
        engine_mode = self.config.get("engine_mode", "auto")

        # 构建引擎参数
        engine_kwargs = {}

        # 代理设置
        if self.var_proxy_enabled.get():
            proxy_server = self.ent_proxy_server.get().strip()
            if proxy_server:
                engine_kwargs['proxy'] = proxy_server
                proxy_username = self.ent_proxy_username.get().strip()
                proxy_password = self.ent_proxy_password.get().strip()
                if proxy_username and proxy_password:
                    engine_kwargs['proxy_username'] = proxy_username
                    engine_kwargs['proxy_password'] = proxy_password
                # 保存到配置
                self.config["proxy_server"] = proxy_server
                self.config["proxy_username"] = proxy_username
                self.config["proxy_password"] = proxy_password
                self.save_config()
            else:
                messagebox.showwarning("提示", "已勾选使用代理，但代理地址为空！")
                return

        # Playwright 特有参数
        pw_headless = not self.var_pw_headless.get()
        engine_kwargs['headless'] = pw_headless

        # Cookie 来源（通用引擎用）
        cookies_browser = self.var_cookies_browser.get()
        if cookies_browser and cookies_browser != "无":
            engine_kwargs['cookies_from_browser'] = cookies_browser
            self.config["cookies_from_browser"] = cookies_browser
        else:
            self.config["cookies_from_browser"] = "无"
        self.save_config()

        # 是否单独保存分离的视频流/音频流
        engine_kwargs['save_separate_streams'] = self.var_save_separate.get()
        self.config["save_separate_streams"] = self.var_save_separate.get()
        self.save_config()

        self.set_ui_state(True)
        self.txt_log.delete("1.0", "end")
        self.progress["value"] = 0
        self.lbl_status.config(text="准备下载...")
        logger.info(f"开始下载任务：{len(urls)} 个视频")

        def worker():
            for i, url in enumerate(urls, 1):
                if self.current_downloader and self.current_downloader.cancel_flag:
                    break

                self.log(f"\n[{i}/{len(urls)}] {url}")
                logger.debug(f"下载任务 {i}/{len(urls)}: {url}")

                # 检测平台
                detected = self.engine_mgr.detect_with_info(url)
                if detected['engine_name'] != '未知':
                    self.log(f"  平台：{detected['detected_platform']}  →  {detected['engine_name']}")

                # 选择引擎
                if engine_mode == "auto":
                    # 自动检测
                    engine = self.engine_mgr.create(
                        url,
                        progress_callback=self.update_progress,
                        log_callback=self.log,
                        status_callback=lambda s: self.root.after(0, lambda: self.lbl_status.config(text=s)),
                        **engine_kwargs,
                    )
                else:
                    # 手动选择引擎
                    engine = self.engine_mgr.create(
                        engine_mode,
                        progress_callback=self.update_progress,
                        log_callback=self.log,
                        status_callback=lambda s: self.root.after(0, lambda: self.lbl_status.config(text=s)),
                        **engine_kwargs,
                    )

                if engine is None:
                    self.log("❌ 无可用的下载引擎，请检查依赖安装")
                    self.log("   点击「检查依赖」查看详情")
                    continue

                self.current_downloader = engine
                engine.download(url, output_dir, quality=quality)

            self.current_downloader = None
            self.root.after(0, lambda: self.set_ui_state(False))
            self.root.after(0, lambda: self.lbl_status.config(text="全部完成"))
            self.root.after(0, lambda: messagebox.showinfo("完成", "所有任务已完成！"))
            logger.info("所有下载任务已完成")

        threading.Thread(target=worker, daemon=True).start()

    def cancel_download(self):
        if self.current_downloader:
            self.current_downloader.cancel()
            self.log("⚠️ 已发送取消请求...")
        else:
            self.log("⚠️ 当前无活跃下载")

    def open_output_dir(self):
        d = self.config["output_dir"]
        if os.path.exists(d):
            os.startfile(d)
        else:
            messagebox.showwarning("提示", f"文件夹不存在：{d}")

    def check_deps(self):
        """检查所有引擎依赖"""
        lines = ["=== 引擎依赖检查 ===\n"]

        # yt-dlp 引擎
        lines.append("[yt-dlp 通用引擎]")
        try:
            import yt_dlp
            lines.append(f"✅ yt-dlp 已安装")
        except ImportError:
            lines.append("❌ yt-dlp 未安装")
            lines.append("   安装：pip install yt-dlp")

        # Playwright 引擎
        lines.append("\n[Playwright B站引擎]")
        if check_playwright_env is not None:
            ok, msg = check_playwright_env()
            lines.append(msg)
        else:
            lines.append("❌ Playwright 未安装")
            lines.append("   安装：pip install playwright")

        # ffmpeg（两者都需要）
        lines.append("\n[通用工具]")
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            lines.append(f"✅ ffmpeg: {ffmpeg}")
        else:
            lines.append("⚠️ ffmpeg 未找到（合并音视频需要）")
            lines.append("   安装：winget install ffmpeg")

        messagebox.showinfo("依赖检查", "\n".join(lines))

    def install_deps(self):
        """一键安装所需的依赖"""

        # 检测已安装组件
        has_playwright = PLAYWRIGHT_AVAILABLE
        has_ytdlp = False
        try:
            import yt_dlp
            has_ytdlp = True
        except ImportError:
            pass
        has_ffmpeg = shutil.which("ffmpeg") is not None

        # 构建提示
        parts = []
        if not has_ytdlp:
            parts.append("1. pip install yt-dlp")
        if not has_playwright:
            parts.append("2. pip install playwright")
            parts.append("3. playwright install chromium")
        if not has_ffmpeg:
            parts.append("4. winget install ffmpeg   (需手动管理员执行)")

        if not parts:
            messagebox.showinfo("依赖检查", "✅ 所有依赖已就绪！")
            return

        msg = "将执行以下命令：\n" + "\n".join(parts) + "\n\n是否继续？"
        result = messagebox.askyesno("安装依赖", msg)
        if not result:
            return

        self.log("正在安装依赖...")
        self.set_ui_state(True)

        def worker():
            import subprocess
            all_ok = True

            # 安装 yt-dlp
            if not has_ytdlp:
                self.log("\n--- 安装 yt-dlp ---")
                try:
                    r = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "yt-dlp"],
                        capture_output=True, text=True, encoding='utf-8', errors='replace',
                        timeout=120
                    )
                    if r.returncode == 0:
                        self.log("✅ yt-dlp 安装成功")
                    else:
                        self.log(f"⚠️ yt-dlp 安装失败：{r.stderr[:200]}")
                        all_ok = False
                except Exception as e:
                    self.log(f"❌ yt-dlp 安装异常：{e}")
                    all_ok = False

            # 安装 Playwright
            if not has_playwright:
                self.log("\n--- 安装 Playwright ---")
                try:
                    r1 = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "playwright"],
                        capture_output=True, text=True, encoding='utf-8', errors='replace',
                        timeout=120
                    )
                    if r1.returncode != 0:
                        self.log(f"⚠️ Playwright 安装失败：{r1.stderr[:200]}")
                        all_ok = False
                    else:
                        self.log("✅ Playwright 包已安装")
                        self.log("正在安装 Chromium 浏览器（可能需要几分钟）...")
                        r2 = subprocess.run(
                            [sys.executable, "-m", "playwright", "install", "chromium"],
                            capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=300
                        )
                        if r2.returncode == 0:
                            self.log("✅ Chromium 已安装")
                        else:
                            self.log(f"⚠️ Chromium 安装异常：{r2.stderr[:200]}")
                            all_ok = False
                except Exception as e:
                    self.log(f"❌ Playwright 安装异常：{e}")
                    all_ok = False

            if all_ok:
                self.log("\n✅ 依赖安装完成！请重启程序以生效")
                self.root.after(0, lambda: messagebox.showinfo(
                    "完成", "依赖安装完成！\n请重启程序以刷新引擎列表。"))
            else:
                self.log("\n⚠️ 部分依赖安装失败，请查看日志")

            self.root.after(0, lambda: self.set_ui_state(False))

        threading.Thread(target=worker, daemon=True).start()


# ============================================================
# 入口
# ============================================================
def main():
    root = tk.Tk()
    try:
        root.iconbitmap(str(PROJECT_ROOT / "icon.png"))
    except Exception:
        pass

    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
