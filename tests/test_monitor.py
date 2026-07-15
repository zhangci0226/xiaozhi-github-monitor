import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import monitor


class MonitorTests(unittest.TestCase):
    def test_build_summary_returns_none_when_no_changes(self):
        changes = {
            "releases": [],
            "tags": [],
            "commits": [],
            "issues": [],
            "pull_requests": [],
        }

        self.assertIsNone(monitor.build_summary("78/xiaozhi-esp32", changes, [], "2026-07-15 09:00:00 HKT"))

    def test_build_summary_includes_core_sections_and_keywords(self):
        changes = {
            "releases": [
                {
                    "name": "v1.2.3",
                    "tag_name": "v1.2.3",
                    "body": "新增 OTA 固件升级能力",
                    "html_url": "https://github.com/78/xiaozhi-esp32/releases/tag/v1.2.3",
                }
            ],
            "tags": [{"name": "v1.2.3", "zipball_url": "https://example.test/tag.zip"}],
            "commits": [
                {
                    "sha": "abcdef123456",
                    "html_url": "https://github.com/78/xiaozhi-esp32/commit/abcdef1",
                    "commit": {"message": "docs: update README config example\n\nLong body"},
                }
            ],
            "issues": [
                {
                    "number": 7,
                    "state": "open",
                    "title": "语音识别配置问题",
                    "html_url": "https://github.com/78/xiaozhi-esp32/issues/7",
                }
            ],
            "pull_requests": [
                {
                    "number": 8,
                    "state": "closed",
                    "title": "Add MCP support",
                    "html_url": "https://github.com/78/xiaozhi-esp32/pull/8",
                }
            ],
        }

        summary = monitor.build_summary(
            "78/xiaozhi-esp32",
            changes,
            ["README.md", "main/config.json"],
            "2026-07-15 09:00:00 HKT",
        )

        self.assertIsNotNone(summary)
        self.assertIn("新 Release / 版本", summary)
        self.assertIn("代码提交", summary)
        self.assertIn("关键文件变化", summary)
        self.assertIn("PR 变化", summary)
        self.assertIn("Issue 变化", summary)
        self.assertIn("OTA", summary)
        self.assertIn("MCP", summary)

    def test_parse_time_supports_github_z_suffix(self):
        parsed = monitor.parse_time("2026-07-15T01:02:03Z")

        self.assertEqual(parsed, dt.datetime(2026, 7, 15, 1, 2, 3, tzinfo=dt.timezone.utc))


if __name__ == "__main__":
    unittest.main()
