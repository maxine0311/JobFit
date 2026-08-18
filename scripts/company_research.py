"""Company background research for smarter resume tailoring (cached).

Searches the web for what a company does, so the tailor can decide which
experiences/projects to keep. Results are cached by company for a week.
"""

from __future__ import annotations

import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(BASE, "data", "company_research.json")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _load() -> dict:
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _ddg(query: str) -> str:
    try:
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for res in soup.select(".result")[:6]:
            title = res.select_one(".result__title")
            snip = res.select_one(".result__snippet")
            if title:
                out.append(title.get_text(" ", strip=True))
            if snip:
                out.append(snip.get_text(" ", strip=True))
        return "\n".join(out).strip()[:1800]
    except Exception:
        return ""


def search_company(company: str, ttl_days: int = 7) -> str:
    """Return a short web-research summary of what the company does (cached)."""
    if not company or not str(company).strip():
        return ""
    key = re.sub(r"\s+", " ", str(company).strip()).lower()
    cache = _load()
    hit = cache.get(key)
    if hit and time.time() - hit.get("ts", 0) < ttl_days * 86400:
        return hit.get("text", "")
    text = _ddg(f"{company} company Singapore products what it does")
    if not text:
        text = _ddg(f"{company} 公司 产品 品牌")
    if not text:
        text = f"（未能获取 {company} 的公开背景信息）"
    cache[key] = {"ts": time.time(), "text": text}
    _save(cache)
    return text


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    print(search_company(sys.argv[1] if len(sys.argv) > 1 else "Sunnystep"))
