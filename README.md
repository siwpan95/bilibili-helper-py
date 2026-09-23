# B站视频下载助手 - Python桌面版 v2.1

> 仓库：<https://gitee.com/siwpan/bilibili-helper-py> ｜ 许可：MIT（见 [LICENSE](LICENSE)）

原 Chrome 扩展的独立桌面版本，基于 Playwright 浏览器自动化，可直接使用浏览器登录状态下载视频。

## 🎯 功能特性

- ✅ 单个视频下载
- ✅ **合集/多P视频批量下载**
- ✅ 清晰度选择（最佳/1080P/720P/480P/仅音频）
- ✅ 浏览器内直接登录（无需手动导出 Cookie）
- ✅ VIP/会员视频下载
- ✅ 图形界面（Tkinter，Python内置）
- ✅ **代理支持**（新增 v2.1）
- ✅ **输入验证和错误提示**（新增 v2.1）
- ✅ **结构化日志系统**（新增 v2.1）
- ✅ **单元测试覆盖**（新增 v2.1）

---

## 📦 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 运行

```bash
python main.py
```
或双击 `启动.bat`

### 3. 打包为 EXE（可选）

双击运行 `打包.bat`，生成的 EXE 位于 `dist/B站视频下载助手.exe`

---

## 📖 使用说明

### 基本流程

1. **输入链接**：粘贴 B站视频链接（支持多个，每行一个）
   - 单个视频：`https://www.bilibili.com/video/BV1xx411c7mD`
   - 合集：直接粘贴链接，自动下载所有P
   - 短链接：`https://b23.tv/xxx`
   - 纯 BV 号：`BV1xx411c7mD`（会自动补全）

2. **选择清晰度**：下拉菜单选择

3. **设置保存位置**：默认保存到项目目录下 `output/`

4. **（可选）配置代理**：如果需要使用代理下载
   - 勾选 "使用代理"
   - 输入代理地址（格式：`http://proxy:port`）

5. 点击 **"开始下载"**

### 登录 Bilibili

如果需要下载会员视频或登录后才能看的视频：

1. 勾选 **"显示浏览器窗口"**
2. 点击"开始下载"
3. 在弹出的浏览器中**手动登录 Bilibili**
4. 登录后程序会自动下载（不要关闭浏览器）
5. 登录状态会被 Playwright 保留，后续下载无需重复登录

### 代理配置

如果需要使用代理下载（例如访问受限视频）：

1. 勾选 **"使用代理"**
2. 输入代理服务器地址（例如：`http://127.0.0.1:7890`）
3. 配置会自动保存到 `config.json`
4. 开始下载时自动使用代理

**支持的代理格式：**
- HTTP：`http://proxy:port`
- HTTPS：`https://proxy:port`
- 带认证：`http://user:pass@proxy:port`

---

## 🛠️ 技术架构

### 技术栈

- **GUI**：Tkinter（Python 内置）
- **下载引擎**：[Playwright](https://playwright.dev/python/) 浏览器自动化
- **日志系统**：Python `logging` 模块
- **测试框架**：`unittest` / `pytest`
- **打包**：PyInstaller

### 项目结构

```
bilibili-helper-py/
├── main.py                 # 主程序（GUI + 日志配置）
├── playwright_engine.py    # Playwright 浏览器自动化引擎
├── cookie_utils.py         # Cookie 导出工具
├── requirements.txt        # Python 依赖
├── 启动.bat                # Windows 快速启动脚本
├── 打包.bat                # PyInstaller 打包脚本
├── README.md               # 本文件
├── icon.png                # 图标
├── config.json             # 用户配置（自动生成）
├── download.log            # 下载日志（自动生成）
├── output/                 # 默认输出目录
└── tests/                  # 单元测试（新增 v2.1）
    ├── __init__.py
    └── test_playwright_engine.py
```

---

## 🔍 功能测试

### 1. 运行单元测试

```bash
# 使用 unittest
python -m unittest tests/test_playwright_engine -v

# 使用 pytest（需要先安装：pip install pytest）
pytest tests/test_playwright_engine.py -v
```

**测试覆盖：**
- ✅ URL 验证（7 个测试用例）
- ✅ 文件名清理（5 个测试用例）
- ✅ 清晰度验证（4 个测试用例）
- ✅ 超时参数验证（5 个测试用例）

### 2. 手动功能测试

**测试场景 1：单个视频下载**
1. 输入有效的 B站视频链接
2. 选择清晰度
3. 点击"开始下载"
4. 检查 `output/` 目录是否生成 MP4 文件

**测试场景 2：合集批量下载**
1. 输入合集链接（例如：`https://www.bilibili.com/video/BV1xx411c7mD?p=1`）
2. 点击"开始下载"
3. 检查是否下载所有分P

**测试场景 3：无效链接处理**
1. 输入无效链接（例如：`https://www.youtube.com/watch?v=xxx`）
2. 点击"开始下载"
3. 检查是否弹出错误提示

**测试场景 4：代理功能**
1. 勾选"使用代理"
2. 输入有效的代理地址
3. 点击"开始下载"
4. 检查日志是否显示"使用代理：..."

**测试场景 5：日志系统**
1. 运行一次下载任务
2. 检查项目目录下是否生成 `download.log`
3. 检查日志格式是否包含时间戳、级别、消息

---

## 📝 日志系统

### 日志文件

所有下载任务会自动生成日志文件 `download.log`，位于项目根目录。

**日志级别：**
- `DEBUG` - 详细调试信息（默认不显示）
- `INFO` - 一般信息（默认显示）
- `WARNING` - 警告信息
- `ERROR` - 错误信息

**日志格式：**
```
2026-06-29 06:00:00 - playwright_engine - INFO - 启动浏览器...
2026-06-29 06:00:01 - playwright_engine - ERROR - 下载失败：连接超时
```

### 查看日志

- **GUI 日志区**：显示 INFO 及以上级别
- **文件日志**：记录所有级别（DEBUG 到 ERROR）

---

## 🐛 常见问题

**Q：下载失败 / 视频加载失败？**
A：勾选「显示浏览器窗口」，看浏览器是否正常加载了视频页面。可能需要登录。

**Q：提示 Playwright 未安装？**
A：点击 GUI 中的「安装 Playwright」按钮，或手动运行：
```
pip install playwright
playwright install chromium
```

**Q：提示 ffmpeg 不存在？**
A：不安装也可以，视频和音频会分开保存。安装方式：`winget install ffmpeg`

**Q：合集只下载了第一个视频？**
A：Playwright 引擎默认下载合集所有分P，请检查日志。

**Q：代理无法连接？**
A：
1. 检查代理地址格式是否正确（例如：`http://127.0.0.1:7890`）
2. 确认代理服务器正在运行
3. 检查防火墙设置

**Q：日志文件太大？**
A：可以手动删除 `download.log`，程序会自动创建新的日志文件。

**Q：如何清理配置文件？**
A：删除项目根目录下的 `config.json`，程序会重新生成默认配置。

---

## 🚀 开发指南

### 添加新功能

1. 在 `playwright_engine.py` 中添加核心逻辑
2. 在 `main.py` 中添加 GUI 控件
3. 在 `tests/test_playwright_engine.py` 中添加单元测试
4. 更新 `README.md` 文档

### 代码规范

- 使用 Python 类型提示
- 添加中文注释和文档字符串
- 所有公开函数添加参数验证
- 使用 `self.log(msg, level)` 输出日志

### 提交代码前检查

```bash
# 运行单元测试
python -m unittest tests/test_playwright_engine -v

# 检查代码风格（可选）
pip install pylint
pylint main.py playwright_engine.py
```

---

## 📊 与原 Chrome 扩展对比

| 功能 | Chrome 扩展 | Python 桌面版 |
|------|-----------|-------------|
| 单个视频下载 | ✅ | ✅ |
| 合集批量下载 | ❌ | ✅ |
| 图形界面 | 浏览器 Popup | 独立窗口 |
| Cookie 管理 | 自动 | 浏览器内登录 |
| VIP 视频 | ✅ | ✅ |
| 字幕下载 | ❌ | ❌（计划中） |
| 代理支持 | ❌ | ✅（新增 v2.1） |
| 日志系统 | ❌ | ✅（新增 v2.1） |
| 单元测试 | ❌ | ✅（新增 v2.1） |

---

## 📄 授权

MIT License

---

## 📮 更新日志

### v2.1 (2026-06-29)

**新增功能：**
- ✅ 添加参数验证和输入 sanitization
- ✅ 优化日志系统（使用 Python `logging` 模块）
- ✅ 支持代理配置（GUI + 引擎）
- ✅ 增加单元测试（覆盖核心函数）

**改进：**
- 改进错误提示（更友好的用户界面）
- 支持 BV 号直接输入
- 下载失败自动重试（最多 3 次）

**修复：**
- 修复文件名非法字符导致保存失败
- 修复超时参数无效导致的异常

### v2.0 (2026-06-28)

- 初始版本
- 支持单个视频和合集下载
- 基于 Playwright 浏览器自动化

> 资产目录标注（2026-08-24）：`output/`（下载输出，约 5GB）与 `download.log` 本地保留、不进版本库（见 .gitignore）。
