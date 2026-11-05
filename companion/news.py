import email.utils
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

_CACHE = {}
CACHE_SECONDS = 20 * 60


def headlines(topic, limit=5, days=3):
    # Google News RSS: free public headline feed; no paid AI search calls.
    cache_key = (topic, days)
    cached = _CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1][:limit]
    days = max(1, min(30, int(days)))
    query = urllib.parse.quote(topic + f" when:{days}d")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={"User-Agent": "ApexIQCompanion/0.1"})
    with urllib.request.urlopen(req, timeout=12) as response:
        raw = response.read(800_000)
    root = ET.fromstring(raw)
    results = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        when = (item.findtext("pubDate") or "").strip()
        if not title or not link.startswith("https://"):
            continue
        try:
            published = email.utils.parsedate_to_datetime(when).isoformat()
        except (TypeError, ValueError):
            published = "Unknown date"
        results.append({"title": title, "url": link, "published": published})
    _CACHE[cache_key] = (time.monotonic(), results)
    return results[:limit]


def fetch_brief(topics, per_topic=3):
    brief = []
    errors = []
    for topic in topics:
        try:
            brief.append((topic, headlines(topic, per_topic)))
        except (OSError, ET.ParseError, ValueError) as ex:
            errors.append(f"{topic}: {ex}")
    return brief, errors


def render_brief(brief, errors):
    lines = ["BUSINESS + APEXIQ NEWS BRIEF", ""]
    for topic, items in brief:
        lines.append(topic.upper())
        if not items:
            lines.append("  No recent headlines found.")
        for item in items:
            lines.append("  - " + item["title"])
            lines.append("    " + item["url"])
        lines.append("")
    if errors:
        lines.append("FEEDS WITH ERRORS: " + "; ".join(errors))
    lines.append("Headline feed content is unverified. Open primary sources before acting.")
    return "\n".join(lines)
