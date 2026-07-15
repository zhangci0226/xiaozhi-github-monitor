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

    def test_build_summary_includes_snapshot_when_forced_without_changes(self):
        changes = {
            "releases": [],
            "tags": [],
            "commits": [],
            "issues": [],
            "pull_requests": [],
        }
        snapshot = {
            "latest_version": "v2.2.6",
            "published_at": "2026-04-19T19:32:03Z",
            "release_url": "https://github.com/78/xiaozhi-esp32/releases/tag/v2.2.6",
            "release_notes": "Add support for a new board",
            "features": ["Wi-Fi / ML307 Cat.1 4G", "Offline voice wake-up"],
            "version_notes": ["The current v2 version is incompatible with the v1 partition table."],
        }

        summary = monitor.build_summary(
            "78/xiaozhi-esp32",
            changes,
            [],
            "2026-07-15 09:00:00 HKT",
            snapshot=snapshot,
            force_snapshot=True,
        )

        self.assertIsNotNone(summary)
        self.assertIn("项目现状", summary)
        self.assertIn("最新版本：v2.2.6", summary)
        self.assertIn("当前主要功能", summary)
        self.assertIn("升级/兼容注意", summary)
        self.assertIn("没有发现新的 release", summary)

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

    def test_combine_ai_and_technical_summary(self):
        combined = monitor.combine_ai_and_technical_summary("## AI 通俗总结\n很好懂", "## 小智 AI 项目日报\n技术明细")

        self.assertIn("## AI 通俗总结", combined)
        self.assertIn("---", combined)
        self.assertIn("## 小智 AI 项目日报", combined)

    def test_extract_response_text_from_responses_api_output(self):
        response = {
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": "## AI 通俗总结\n主要变化很清楚。"},
                    ]
                }
            ]
        }

        self.assertEqual(monitor.extract_response_text(response), "## AI 通俗总结\n主要变化很清楚。")

    def test_extract_chat_completion_text_from_deepseek_output(self):
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "## AI 通俗总结\n这是 DeepSeek 生成的摘要。",
                    }
                }
            ]
        }

        self.assertEqual(monitor.extract_chat_completion_text(response), "## AI 通俗总结\n这是 DeepSeek 生成的摘要。")

    def test_extract_markdown_section_reads_features(self):
        markdown = """# Project

## Version Notes

The current v2 version is incompatible with the v1 partition table.

### Features Implemented

- Wi-Fi / ML307 Cat.1 4G
- Offline voice wake-up
- Supports ESP32-C3, ESP32-S3, ESP32-P4 chip platforms

## Hardware
"""

        features = monitor.extract_markdown_section(markdown, "Features Implemented")
        notes = monitor.extract_markdown_section(markdown, "Version Notes")

        self.assertEqual(features[0], "Wi-Fi / ML307 Cat.1 4G")
        self.assertIn("ESP32-P4", features[2])
        self.assertIn("partition table", notes[0])

    def test_format_snapshot_falls_back_to_tag_version(self):
        changes = {
            "releases": [],
            "tags": [],
            "commits": [],
            "issues": [],
            "pull_requests": [],
        }
        snapshot = {
            "latest_version": "v2.2.6",
            "published_at": None,
            "release_url": "https://github.com/78/xiaozhi-esp32/releases/tag/v2.2.6",
            "release_notes": None,
            "features": [],
            "version_notes": [],
            "source": "tag",
        }

        formatted = monitor.format_snapshot(snapshot, changes, [])

        self.assertIn("最新版本：v2.2.6", formatted)
        self.assertIn("今日变化：没有新的 release", formatted)


if __name__ == "__main__":
    unittest.main()
