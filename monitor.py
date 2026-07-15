#!/usr/bin/env python3
"""Daily GitHub change monitor for 78/xiaozhi-esp32.

The script is intentionally dependency-free so it can run directly on
GitHub Actions. It reads state.json, fetches repository activity via the
GitHub REST API, posts a Chinese Markdown summary to PushPlus ClawBot or
a WeCom bot webhook when configured, then updates state.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_REPO = "78/xiaozhi-esp32"
DEFAULT_STATE_PATH = "state.json"
DEFAULT_INITIAL_LOOKBACK_HOURS = 24
IMPORTANT_KEYWORDS = [
    "OTA",
    "唤醒词",
    "语音识别",
    "ASR",
    "TTS",
    "ESP32",
    "MCP",
    "配置",
    "固件",
    "firmware",
    "config",
    "README",
    "docs",
]
KEY_FILE_PATTERNS = (
    "readme",
    "docs/",
    "doc/",
    "config",
    "sdkconfig",
    "partitions",
    "firmware",
    ".md",
    ".yml",
    ".yaml",
    ".json",
)


class GitHubClient:
    def __init__(self, repo: str, token: str | None = None) -> None:
        self.repo = repo
        self.base_url = f"https://api.github.com/repos/{repo}"
        self.token = token

    def get(self, path: str, query: dict[str, str] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "xiaozhi-github-monitor",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API error {exc.code} for {url}: {body}") from exc


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_time(value: str | None) -> dt.datetime:
    if not value:
        return dt.datetime.fromtimestamp(0, tz=dt.timezone.utc)
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def first_line(text: str | None, max_len: int = 90) -> str:
    if not text:
        return ""
    line = re.sub(r"\s+", " ", text.strip()).splitlines()[0]
    return line if len(line) <= max_len else f"{line[: max_len - 1]}..."


def issue_is_pull_request(item: dict[str, Any]) -> bool:
    return "pull_request" in item


def initial_since() -> str:
    hours = int(os.getenv("INITIAL_LOOKBACK_HOURS", str(DEFAULT_INITIAL_LOOKBACK_HOURS)))
    value = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def collect_changes(client: GitHubClient, state: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    since = state.get("last_checked_at") or initial_since()
    since_dt = parse_time(since)
    new_state = dict(state)
    changes: dict[str, list[dict[str, Any]]] = {
        "releases": [],
        "tags": [],
        "commits": [],
        "issues": [],
        "pull_requests": [],
    }

    releases = client.get("/releases", {"per_page": "20"})
    last_release_id = state.get("last_release_id")
    for release in releases:
        published_at = parse_time(release.get("published_at") or release.get("created_at"))
        if release.get("id") != last_release_id and published_at > since_dt:
            changes["releases"].append(release)
    if releases:
        new_state["last_release_id"] = releases[0].get("id")

    tags = client.get("/tags", {"per_page": "20"})
    last_tag_name = state.get("last_tag_name")
    for tag in tags:
        if tag.get("name") == last_tag_name:
            break
        commit_sha = tag.get("commit", {}).get("sha")
        if commit_sha:
            detail = client.get(f"/commits/{commit_sha}")
            commit_date = parse_time(detail.get("commit", {}).get("committer", {}).get("date"))
            if commit_date <= since_dt:
                continue
        changes["tags"].append(tag)
    if tags:
        new_state["last_tag_name"] = tags[0].get("name")

    commit_query = {"per_page": "30"}
    if since:
        commit_query["since"] = since
    commits = client.get("/commits", commit_query)
    last_commit_sha = state.get("last_commit_sha")
    for commit in commits:
        sha = commit.get("sha")
        if sha == last_commit_sha:
            break
        changes["commits"].append(commit)
    if commits:
        new_state["last_commit_sha"] = commits[0].get("sha")

    issues = client.get(
        "/issues",
        {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "since": since or "1970-01-01T00:00:00Z",
            "per_page": "50",
        },
    )
    for item in issues:
        updated_at = parse_time(item.get("updated_at"))
        if updated_at <= since_dt:
            continue
        target = "pull_requests" if issue_is_pull_request(item) else "issues"
        changes[target].append(item)

    new_state["last_checked_at"] = iso_now()
    return changes, new_state


def is_key_file(filename: str) -> bool:
    normalized = filename.lower().replace("\\", "/")
    return any(pattern in normalized for pattern in KEY_FILE_PATTERNS)


def changed_key_files(client: GitHubClient, commits: list[dict[str, Any]]) -> list[str]:
    files: list[str] = []
    seen: set[str] = set()
    for commit in commits[:10]:
        sha = commit.get("sha")
        if not sha:
            continue
        detail = client.get(f"/commits/{sha}")
        for file_info in detail.get("files", []):
            filename = file_info.get("filename", "")
            if filename and is_key_file(filename) and filename not in seen:
                seen.add(filename)
                files.append(filename)
    return files[:12]


def markdown_link(title: str, url: str | None) -> str:
    safe_title = title.replace("[", "［").replace("]", "］")
    return f"[{safe_title}]({url})" if url else safe_title


def keyword_hits(text: str) -> list[str]:
    upper_text = text.upper()
    hits = []
    for keyword in IMPORTANT_KEYWORDS:
        probe = keyword.upper() if keyword.isascii() else keyword
        if probe in upper_text or keyword in text:
            hits.append(keyword)
    return hits


def build_summary(
    repo: str,
    changes: dict[str, list[dict[str, Any]]],
    key_files: list[str],
    checked_at: str,
) -> str | None:
    total = sum(len(items) for items in changes.values()) + len(key_files)
    if total == 0:
        return None

    all_text = " ".join(
        [
            *(release.get("name") or release.get("tag_name") or "" for release in changes["releases"]),
            *(commit.get("commit", {}).get("message", "") for commit in changes["commits"]),
            *(item.get("title", "") for item in changes["issues"]),
            *(item.get("title", "") for item in changes["pull_requests"]),
            *key_files,
        ]
    )
    hits = keyword_hits(all_text)
    repo_url = f"https://github.com/{repo}"
    lines = [
        f"## 小智 AI 项目日报",
        f"> 仓库：{markdown_link(repo, repo_url)}",
        f"> 检查时间：{checked_at}",
        "",
        f"**今日结论：**发现 {total} 项变化"
        + (f"，重点关注：{', '.join(dict.fromkeys(hits[:8]))}" if hits else "。"),
    ]

    if changes["releases"]:
        lines.extend(["", "### 新 Release / 版本"])
        for release in changes["releases"][:5]:
            title = release.get("name") or release.get("tag_name") or "未命名版本"
            body = first_line(release.get("body"))
            lines.append(f"- {markdown_link(title, release.get('html_url'))}")
            if body:
                lines.append(f"  {body}")

    if changes["tags"]:
        lines.extend(["", "### 新 Tag"])
        for tag in changes["tags"][:8]:
            tag_name = tag.get("name", "unknown")
            lines.append(f"- {markdown_link(tag_name, f'https://github.com/{repo}/releases/tag/{tag_name}')}")

    if changes["commits"]:
        lines.extend(["", "### 代码提交"])
        for commit in changes["commits"][:12]:
            message = first_line(commit.get("commit", {}).get("message"), 100)
            sha = (commit.get("sha") or "")[:7]
            url = commit.get("html_url")
            lines.append(f"- `{sha}` {markdown_link(message or '无提交说明', url)}")

    if key_files:
        lines.extend(["", "### 关键文件变化"])
        for filename in key_files:
            lines.append(f"- `{filename}`")

    if changes["pull_requests"]:
        lines.extend(["", "### PR 变化"])
        for pr in changes["pull_requests"][:10]:
            state = "已关闭/合并" if pr.get("state") == "closed" else "打开"
            lines.append(f"- #{pr.get('number')} [{state}] {markdown_link(pr.get('title', ''), pr.get('html_url'))}")

    if changes["issues"]:
        lines.extend(["", "### Issue 变化"])
        for issue in changes["issues"][:10]:
            state = "已关闭" if issue.get("state") == "closed" else "打开"
            lines.append(f"- #{issue.get('number')} [{state}] {markdown_link(issue.get('title', ''), issue.get('html_url'))}")

    lines.extend(["", f"查看仓库：{repo_url}"])
    return "\n".join(lines)


def post_wecom(webhook_url: str, content: str, dry_run: bool = False) -> None:
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": content[:3900]},
    }
    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        result = json.loads(body)
        if result.get("errcode") != 0:
            raise RuntimeError(f"WeCom webhook returned an error: {body}")


def post_pushplus(token: str, content: str, dry_run: bool = False) -> None:
    payload = {
        "token": token,
        "title": "小智 AI 项目日报",
        "content": content,
        "template": "markdown",
        "channel": os.getenv("PUSHPLUS_CHANNEL", "clawbot"),
    }
    if dry_run:
        safe_payload = dict(payload)
        safe_payload["token"] = "***"
        print(json.dumps(safe_payload, ensure_ascii=False, indent=2))
        return
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "http://www.pushplus.plus/send",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        result = json.loads(body)
        if result.get("code") != 200:
            raise RuntimeError(f"PushPlus returned an error: {body}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send daily xiaozhi-esp32 GitHub updates to PushPlus/WeCom.")
    parser.add_argument("--repo", default=os.getenv("TARGET_REPO", DEFAULT_REPO))
    parser.add_argument("--state", default=os.getenv("STATE_PATH", DEFAULT_STATE_PATH))
    parser.add_argument("--dry-run", action="store_true", help="Print the webhook payload instead of sending it.")
    parser.add_argument("--force-send", action="store_true", help="Send a message even when there are no changes.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_path = Path(args.state)
    token = os.getenv("GITHUB_TOKEN")
    pushplus_token = os.getenv("PUSHPLUS_TOKEN")
    webhook_url = os.getenv("WECHAT_WEBHOOK_URL")

    client = GitHubClient(args.repo, token)
    state = load_state(state_path)
    changes, new_state = collect_changes(client, state)
    key_files = changed_key_files(client, changes["commits"])
    checked_at = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    summary = build_summary(args.repo, changes, key_files, checked_at)

    if not summary and args.force_send:
        summary = (
            "## 小智 AI 项目日报\n"
            f"> 仓库：{args.repo}\n\n"
            "今日没有发现新的 release、tag、commit、issue 或 PR 变化。"
        )

    if summary:
        print(summary)
        if pushplus_token:
            post_pushplus(pushplus_token, summary, dry_run=args.dry_run)
        elif webhook_url:
            post_wecom(webhook_url, summary, dry_run=args.dry_run)
        else:
            print("\nPUSHPLUS_TOKEN and WECHAT_WEBHOOK_URL are not set; skipped sending notification.")
    else:
        print("No changes detected; skipped notification.")

    save_state(state_path, new_state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
