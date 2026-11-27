#!/usr/bin/env python3
"""Collect GitHub traffic data and merge it into a persistent history.

GitHub keeps clone/view traffic for only 14 days. This script fetches the
current window and merges it into JSON files (key = UTC date), so repeated
runs build a gap-free history. Standard library only.

Environment:
  TRAFFIC_TOKEN        fine-grained PAT with read access to repo administration
  GITHUB_REPOSITORY    "owner/name" (set automatically in GitHub Actions)

Usage: collect_traffic.py OUTPUT_DIR
Writes OUTPUT_DIR/clones.json, views.json (daily history, merged),
referrers.json, paths.json, releases.json (dated snapshots), TRAFFIC.md and
badge-clones.json (shields.io endpoint badge: total clones in the history).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

API = "https://api.github.com"


def api_get(path: str, token: str):
    req = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "traffic-collector",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def merge_daily(history: dict, entries: list[dict]) -> dict:
    """Merge API day entries into history; newer API values replace the same date."""
    for entry in entries:
        day = entry["timestamp"][:10]
        history[day] = {"count": entry["count"], "uniques": entry["uniques"]}
    return dict(sorted(history.items()))


def merge_snapshot(history: dict, today: str, items) -> dict:
    history[today] = items
    return dict(sorted(history.items()))


def render_markdown(clones: dict, views: dict, releases: dict) -> str:
    def totals(h):
        return sum(v["count"] for v in h.values()), sum(v["uniques"] for v in h.values())

    lines = ["# Traffic history", "", f"Updated: {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC", ""]
    for name, hist in (("Clones", clones), ("Views", views)):
        c, u = totals(hist)
        first = next(iter(hist), "-")
        lines.append(f"- **{name}** since {first}: {c} total, {u} sum of daily uniques")
    if releases:
        last = releases[max(releases)]
        lines += ["", "## Release downloads (latest snapshot)", "", "| Release | Asset | Downloads |", "|---|---|---|"]
        for rel in last:
            for a in rel["assets"]:
                lines.append(f"| {rel['tag']} | {a['name']} | {a['downloads']} |")
    lines += ["", "## Last 30 days (clones / unique cloners)", "", "| Date | Clones | Unique |", "|---|---|---|"]
    for day in sorted(clones, reverse=True)[:30]:
        lines.append(f"| {day} | {clones[day]['count']} | {clones[day]['uniques']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    token = os.environ.get("TRAFFIC_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        print("TRAFFIC_TOKEN and GITHUB_REPOSITORY must be set", file=sys.stderr)
        return 2
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    clones = merge_daily(load_json(out / "clones.json", {}), api_get(f"/repos/{repo}/traffic/clones", token)["clones"])
    views = merge_daily(load_json(out / "views.json", {}), api_get(f"/repos/{repo}/traffic/views", token)["views"])
    save_json(out / "clones.json", clones)
    save_json(out / "views.json", views)

    referrers = merge_snapshot(
        load_json(out / "referrers.json", {}), today, api_get(f"/repos/{repo}/traffic/popular/referrers", token))
    paths = merge_snapshot(
        load_json(out / "paths.json", {}), today, api_get(f"/repos/{repo}/traffic/popular/paths", token))
    save_json(out / "referrers.json", referrers)
    save_json(out / "paths.json", paths)

    rel_items = [
        {"tag": r["tag_name"], "assets": [{"name": a["name"], "downloads": a["download_count"]} for a in r["assets"]]}
        for r in api_get(f"/repos/{repo}/releases?per_page=100", token)
    ]
    releases = merge_snapshot(load_json(out / "releases.json", {}), today, rel_items)
    save_json(out / "releases.json", releases)

    save_json(out / "badge-clones.json", {
        "schemaVersion": 1,
        "label": "clones",
        "message": str(sum(v["count"] for v in clones.values())),
        "color": "blue",
    })

    (out / "TRAFFIC.md").write_text(render_markdown(clones, views, releases), encoding="utf-8")
    print(f"clones days: {len(clones)}, views days: {len(views)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
