"""
万能视频下载助手 - 入口文件
处理 Windows 中文编码问题，然后启动 GUI
"""

# ============================================================
# 编码修复：解决 Windows 中文系统输出编码问题
# ============================================================
import sys
import os

# 设置 Python 输入输出编码为 UTF-8
if sys.version_info >= (3, 7):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

try:
    if os.name == 'nt':
        os.system('chcp 65001 >nul 2>&1')
except Exception:
    pass

# 编码修复完成，导入 UI 模块并启动
from ui import main

if __name__ == "__main__":
    main()
