"""
测试包初始化文件
"""

# 确保能正确导入父目录的模块
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
