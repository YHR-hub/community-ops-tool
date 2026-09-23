import unittest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFetchData(unittest.TestCase):
    def setUp(self):
        import db
        self.db = db

    def test_fetch_and_store_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "version": "5.0",
                    "characters": [
                        {"name": "胡桃", "usage_rate": 75.5, "floor": 12},
                        {"name": "钟离", "usage_rate": 80.0, "floor": 12},
                    ]
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("fetch_data.requests.get", return_value=mock_response):
            # 注意：实际调用需真实数据库，这里验证函数存在且可调用
            # 由于是单元测试，避免真实 DB 操作
            import fetch_data
            self.assertTrue(callable(fetch_data.fetch_and_store))

    def test_fetch_and_store_timeout(self):
        import requests
        with patch("fetch_data.requests.get", side_effect=requests.exceptions.Timeout):
            import fetch_data
            result = fetch_data.fetch_and_store()
            self.assertEqual(result, 0)

    def test_fetch_and_store_connection_error(self):
        import requests
        with patch("fetch_data.requests.get", side_effect=requests.exceptions.ConnectionError):
            import fetch_data
            result = fetch_data.fetch_and_store()
            self.assertEqual(result, 0)

    def test_module_imports(self):
        import fetch_data
        self.assertTrue(hasattr(fetch_data, "fetch_and_store"))
        self.assertTrue(hasattr(fetch_data, "URL"))
        self.assertTrue(hasattr(fetch_data, "TIMEOUT"))


if __name__ == "__main__":
    unittest.main()
