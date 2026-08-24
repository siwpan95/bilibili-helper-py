"""
单元测试：engine/bilibili_engine.py 中的工具函数
运行方式：
    python -m pytest tests/test_playwright_engine.py -v
    或
    python -m unittest tests.test_playwright_engine -v
"""

import unittest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.bilibili_engine import (
    validate_bilibili_url,
    sanitize_filename,
    validate_quality,
    validate_timeout
)


class TestValidateBilibiliUrl(unittest.TestCase):
    """测试 URL 验证函数"""

    def test_valid_full_url(self):
        """测试有效的完整 URL"""
        valid, url, video_id = validate_bilibili_url("https://www.bilibili.com/video/BV1xx411c7mD")
        self.assertTrue(valid)
        self.assertEqual(video_id, "BV1xx411c7mD")

    def test_valid_short_url(self):
        """测试短链接"""
        valid, url, video_id = validate_bilibili_url("https://b23.tv/abc123")
        self.assertTrue(valid)

    def test_valid_bv_number(self):
        """测试纯 BV 号"""
        valid, url, video_id = validate_bilibili_url("BV1xx411c7mD")
        self.assertTrue(valid)
        self.assertEqual(url, "https://www.bilibili.com/video/BV1xx411c7mD")
        self.assertEqual(video_id, "BV1xx411c7mD")

    def test_invalid_url(self):
        """测试无效的 URL"""
        valid, url, video_id = validate_bilibili_url("https://www.youtube.com/watch?v=xxx")
        self.assertFalse(valid)
        self.assertIsNone(video_id)

    def test_empty_url(self):
        """测试空 URL"""
        valid, url, video_id = validate_bilibili_url("")
        self.assertFalse(valid)

    def test_none_url(self):
        """测试 None"""
        valid, url, video_id = validate_bilibili_url(None)
        self.assertFalse(valid)

    def test_invalid_bv_number(self):
        """测试无效的 BV 号（长度不对）"""
        valid, url, video_id = validate_bilibili_url("BV123")
        self.assertFalse(valid)


class TestSanitizeFilename(unittest.TestCase):
    """测试文件名清理函数"""

    def test_normal_title(self):
        """测试正常标题"""
        result = sanitize_filename("测试视频标题")
        self.assertEqual(result, "测试视频标题")

    def test_title_with_illegal_chars(self):
        """测试包含非法字符的标题"""
        result = sanitize_filename('测试/视频*标题?')
        self.assertNotIn('/', result)
        self.assertNotIn('*', result)
        self.assertNotIn('?', result)

    def test_title_too_long(self):
        """测试过长标题"""
        long_title = "a" * 200
        result = sanitize_filename(long_title, max_length=100)
        self.assertLessEqual(len(result), 100)

    def test_empty_title(self):
        """测试空标题"""
        result = sanitize_filename("")
        self.assertEqual(result, "bilibili_video")

    def test_none_title(self):
        """测试 None 标题"""
        result = sanitize_filename(None)
        self.assertEqual(result, "bilibili_video")


class TestValidateQuality(unittest.TestCase):
    """测试清晰度验证函数"""

    def test_valid_quality(self):
        """测试有效的清晰度"""
        result = validate_quality("1080P")
        self.assertEqual(result, "1080P")

    def test_invalid_quality(self):
        """测试无效的清晰度"""
        result = validate_quality("4K")
        self.assertEqual(result, "最佳质量")  # 返回默认值

    def test_empty_quality(self):
        """测试空清晰度"""
        result = validate_quality("")
        self.assertEqual(result, "最佳质量")


class TestValidateTimeout(unittest.TestCase):
    """测试超时验证函数"""

    def test_valid_timeout(self):
        """测试有效的超时值"""
        result = validate_timeout(30)
        self.assertEqual(result, 30)

    def test_timeout_too_low(self):
        """测试过小的超时值"""
        result = validate_timeout(5)
        self.assertEqual(result, 10)  # 最小值

    def test_timeout_too_high(self):
        """测试过大的超时值"""
        result = validate_timeout(500)
        self.assertEqual(result, 300)  # 最大值

    def test_invalid_timeout(self):
        """测试无效的超时值"""
        result = validate_timeout("abc")
        self.assertEqual(result, 30)  # 默认值

    def test_none_timeout(self):
        """测试 None 超时值"""
        result = validate_timeout(None)
        self.assertEqual(result, 30)  # 默认值


if __name__ == "__main__":
    unittest.main()
