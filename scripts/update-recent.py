#!/usr/bin/env python3
"""Refresh the auto-updated 'recent' block in README.md from RSS feeds.

Fetches blog + wiki RSS from michaelbommarito.com, picks the most recent
items overall (interleaved by pubDate), and injects them between the
markers below. Idempotent: writes only if the resulting block differs.

Markers in README.md:

  <!-- RECENT:START -->
  ...auto-generated content...
  <!-- RECENT:END -->
"""
from __future__ import annotations
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

FEEDS = [
    ("blog", "https://michaelbommarito.com/rss.xml"),
    ("bookmarks", "https://michaelbommarito.com/bookmarks/rss.xml"),
]
README = Path(__file__).resolve().parent.parent / "README.md"
START = "<!-- RECENT:START -->"
END = "<!-- RECENT:END -->"
MAX_ITEMS = 6


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mjbommar-profile-readme-bot"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def parse_items(label: str, xml_bytes: bytes) -> list[dict]:
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        print(f"warn: failed to parse {label} feed", file=sys.stderr)
        return items
    # RSS 2.0: channel/item
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_text = item.findtext("pubDate") or ""
        try:
            pub = parsedate_to_datetime(pub_text)
        except (TypeError, ValueError):
            pub = datetime.min
        if title and link:
            items.append({"label": label, "title": title, "link": link, "pub": pub})
    return items


def render(items: list[dict]) -> str:
    if not items:
        return f"{START}\n{END}"
    lines = [START, ""]
    for it in items:
        date = it["pub"].strftime("%Y-%m-%d") if it["pub"] != datetime.min else ""
        date_part = f" · `{date}`" if date else ""
        lines.append(f"- [{it['title']}]({it['link']}) — *{it['label']}*{date_part}")
    lines += ["", END]
    return "\n".join(lines)


def main() -> int:
    all_items: list[dict] = []
    for label, url in FEEDS:
        try:
            all_items.extend(parse_items(label, fetch(url)))
        except Exception as e:
            print(f"warn: {url}: {e}", file=sys.stderr)
    all_items.sort(key=lambda i: i["pub"], reverse=True)
    block = render(all_items[:MAX_ITEMS])

    text = README.read_text()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        print(f"error: README has no {START} ... {END} markers", file=sys.stderr)
        return 1
    new_text = pattern.sub(block, text)
    if new_text == text:
        print("no change")
        return 0
    README.write_text(new_text)
    print("updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
