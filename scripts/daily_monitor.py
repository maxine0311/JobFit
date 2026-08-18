"""Daily monitor: find NEW suitable jobs and report gaps to prepare.

Source: internsg.com (server-rendered, no auth). Compares against the tracker's
existing applications and a local history file, then writes a dated report:
    data/new_jobs_YYYY-MM-DD.md

Schedule daily (Windows):
    schtasks /Create /TN "JobFitDailyMonitor" /TR "\"python.exe\" \"C:\\path\\to\\jobfit\\scripts\\daily_monitor.py\"" /SC DAILY /ST 09:00
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import requests
from bs4 import BeautifulSoup

from agent.llm import LLM
from rag.config import settings

KEYWORDS = [
    "software engineer", "backend engineer", "AI engineer", "full stack",
    "machine learning", "data engineer", "graduate programme", "associate",
]
BASE_URL = "https://www.internsg.com/jobs/?job_search={kw}"
JOBSTREET_URL = "https://sg.jobstreet.com/{slug}-jobs"
MCF_API = "https://api.mycareersfuture.gov.sg/v2/jobs"
GRADCONN_URL = "https://sg.gradconnection.com/jobs/?keywords={kw}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY = os.path.join(BASE_DIR, "data/new_jobs_history.jsonl")
LAST_RUN = os.path.join(BASE_DIR, "data/monitor_last_run.txt")
TRACKER = settings.tracker_xlsx
TRACKER_SHEETS = ["实习追踪", "全职追踪"]
RECENT_DAYS = 3
TOP_ANALYZE = 3

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

POSITION_STOP = {
    "intern", "internship", "associate", "analyst", "engineer", "graduate",
    "developer", "program", "trainee", "research", "operations", "software",
    "data", "full", "stack", "backend", "frontend", "ml", "ai", "science",
}

PROFILE_TERMS = [
    "ai", "backend", "full", "stack", "python", "llm", "ml", "machine",
    "software", "engineer", "intern", "graduate", "rag", "agent", "data",
]

GAP_SYSTEM = (
    "You are a job-fit advisor. Given a new job posting and the candidate's "
    "background summary, give: match (高/中/低), 需要补的知识 (concrete topics), "
    "着重准备什么 (interview/project focus), and a tier: "
    "'现在就能投' if the candidate's current skills are a strong fit, "
    "'补课后更优' if a few reachable gaps would unlock a better position, "
    "or '不合适'. "
    'Respond with ONLY JSON: {"tier": "...", "match": "...", "gaps": ["..."], "focus": ["..."]}'
)

INTERN_RE = re.compile(r"\bintern", re.I)


def cv_summary() -> str:
    """Pull a short grounded summary of the candidate's resumes from the corpus."""
    fallback = "候选人为求职者，技术背景以 Python / 后端 / LLM / RAG / AI 应用为主；具体背景见 data/candidate_summary.md。"
    if os.path.exists(settings.candidate_summary):
        try:
            text = open(settings.candidate_summary, encoding="utf-8").read().strip()
            if text:
                fallback = text[:1500]
        except Exception:
            pass
    try:
        from rag.pipeline import RagPipeline

        pipe = RagPipeline()
        q = "candidate resume skills experience projects"
        emb = pipe.embed([q])[0]
        ids = pipe.retriever.hybrid_topk(q, emb, k=3)
        text = "\n".join(c["text"] for c in pipe.retriever.contexts(ids))[:1500]
        return text or fallback
    except Exception:
        return fallback


def company_from_url(url: str) -> str:
    slug = url.split("/job/")[1].split("/")[0].split("?")[0] if "/job/" in url else url
    parts = slug.split("-")
    while parts and parts[0].isdigit():
        parts.pop(0)
    out = []
    for p in parts:
        if p in POSITION_STOP:
            break
        out.append(p)
    return "-".join(out) or slug


def jobstreet_url(kw: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", kw.lower()).strip("-")
    return JOBSTREET_URL.format(slug=slug)


def fetch_keyword(kw: str) -> list[dict]:
    r = requests.get(BASE_URL.format(kw=kw.replace(" ", "+")), headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    jobs = []
    seen = set()
    for a in soup.find_all("a", class_="job-listing-row", href=True):
        href = a["href"]
        title_el = a.find(class_="job-listing-title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            continue
        key = slug_key(href)
        if key in seen:
            continue
        seen.add(key)
        company = ""
        company_el = a.find(class_="job-listing-company")
        if company_el:
            company = company_el.get_text(strip=True)
            badge = company_el.find("span")
            if badge:
                company = company.replace(badge.get_text(strip=True), "").strip()
        date_el = a.find(class_="badge-success")
        date = date_el.get_text(strip=True) if date_el else ""
        jobs.append({"title": title, "url": href, "date": date, "company": company})
    return jobs


def fetch_jobstreet(kw: str) -> list[dict]:
    """Full-time listings from JobStreet SG (server-rendered)."""
    r = requests.get(jobstreet_url(kw), headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    jobs, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/job/" not in href:
            continue
        title = a.get_text(strip=True)
        if not title or len(title) > 90:
            continue
        key = slug_key(href)
        if key in seen:
            continue
        seen.add(key)
        company = ""
        article = a.find_parent("article")
        if article is not None:
            c = article.find(attrs={"data-automation": "jobCompany"})
            if c:
                company = c.get_text(strip=True)
        url = href if href.startswith("http") else "https://sg.jobstreet.com" + href
        if not company:
            company = company_from_url(url)
        jobs.append({"title": title, "url": url, "date": "", "company": company})
    return jobs


def fetch_mycareersfuture(kw: str) -> list[dict]:
    """Full-time listings from MyCareersFuture (official SG job API)."""
    r = requests.get(
        MCF_API,
        params={"search": kw, "sortBy": "new_posting_date", "page": 0},
        headers={**HEADERS, "Accept": "application/json"},
        timeout=20,
    )
    r.raise_for_status()
    jobs = []
    for it in r.json().get("results", []):
        if str((it.get("status") or {}).get("jobStatus", "")).lower() != "open":
            continue
        title = it.get("title") or ""
        if not title:
            continue
        meta = it.get("metadata") or {}
        jobs.append(
            {
                "title": title,
                "url": f"https://www.mycareersfuture.gov.sg/job/{it.get('uuid')}",
                "date": meta.get("newPostingDate", ""),
                "company": (it.get("postedCompany") or {}).get("name") or "",
                "deadline": meta.get("expiryDate", ""),
                "salary": it.get("salary") or {},
            }
        )
    return jobs


def fetch_gradconnection(kw: str) -> list[dict]:
    """Graduate-programme listings from JobStreet Grad (GradConnection SG)."""
    r = requests.get(GRADCONN_URL.format(kw=kw.replace(" ", "+")), headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    jobs, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        mm = re.match(r"/employers/([^/]+)/jobs/([^/]+)/", href)
        if not mm:
            continue
        key = f"{mm.group(1)}/{mm.group(2)}"
        if key in seen:
            continue
        seen.add(key)
        title = a.get_text(" ", strip=True)
        if not title or len(title) > 90:
            continue
        url = href if href.startswith("http") else "https://sg.gradconnection.com" + href
        company = mm.group(1).replace("-", " ").title()
        jobs.append({"title": title, "url": url, "date": "", "company": company})
    return jobs


def parse_date(text: str) -> datetime.date | None:
    m = re.fullmatch(r"(\d{1,2}) (\w{3})", text)
    if not m:
        return None
    day, mon = int(m.group(1)), MONTHS.get(m.group(2).lower(), 0)
    if not mon:
        return None
    today = datetime.date.today()
    d = datetime.date(today.year, mon, day)
    if d > today:
        d = datetime.date(today.year - 1, mon, day)
    return d


def score(job: dict) -> int:
    text = f"{job['title']} {job['company']}".lower()
    return sum(1 for t in PROFILE_TERMS if t in text)


def load_seen() -> tuple[set[str], set[str]]:
    seen_urls, seen_titles = set(), set()
    if os.path.exists(TRACKER):
        for sheet in TRACKER_SHEETS:
            try:
                df = pd.read_excel(TRACKER, sheet_name=sheet, dtype=str)
            except Exception:
                continue
            for _, row in df.iterrows():
                link = str(row.get("链接") or "")
                if link.startswith("http"):
                    seen_urls.add(link)
                    if "/job/" in link:
                        seen_urls.add(slug_key(link))
                title = str(row.get("职位") or "").strip().lower()
                if title:
                    seen_titles.add(title)
    if os.path.exists(HISTORY):
        for line in open(HISTORY, encoding="utf-8"):
            try:
                e = json.loads(line)
                u = e.get("url", "")
                if u:
                    seen_urls.add(u)
                    if "/job/" in u:
                        seen_urls.add(slug_key(u))
                seen_titles.add(str(e.get("title", "")).lower().strip())
            except Exception:
                continue
    return seen_urls, seen_titles


def slug_key(url: str) -> str:
    if "/job/" in url:
        return url.split("/job/")[1].split("/")[0].split("?")[0]
    return url


def fetch_detail(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    lines = [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]
    return "\n".join(lines)


def analyze(job: dict, cv: str = "") -> dict:
    llm = LLM()
    detail = fetch_detail(job["url"])[:6000]
    out = llm.chat_json(
        GAP_SYSTEM,
        f"新岗位：{job['title']} @ {job['company']}\nJD 摘要：\n{detail}\n\n候选人背景：\n{cv or '（未提供）'}",
    )
    return out["data"] or {}


def run_monitor(keywords: list[str] | None = None, top: int = TOP_ANALYZE, include_intern: bool = False) -> int:
    """Fetch new jobs, dedupe vs tracker/history, analyze top roles, write report + stamp.

    Returns the number of new jobs found. Used by the CLI, the scheduled task,
    and the dashboard on startup / refresh button.
    """
    keywords = keywords or KEYWORDS
    seen_urls, seen_titles = load_seen()
    fresh: dict[str, dict] = {}

    # source 1: JobStreet SG (full-time focus, relevance >= 2)
    for kw in keywords:
        try:
            for job in fetch_jobstreet(kw):
                job["score"] = score(job)
                if job["score"] < 2:
                    continue
                key = slug_key(job["url"])
                if key in seen_urls or job["title"].lower() in seen_titles:
                    continue
                fresh[key] = job
        except requests.RequestException as e:
            print(f"[warn] jobstreet/{kw}: {type(e).__name__}")

    # source 2: internsg (graduate roles, relevance >= 1, recent)
    for kw in keywords:
        try:
            for job in fetch_keyword(kw):
                if not include_intern and INTERN_RE.search(job["title"]) and "graduate" not in job["title"].lower():
                    continue
                job["score"] = score(job)
                if job["score"] < 1:
                    continue
                key = slug_key(job["url"])
                if key in seen_urls or job["title"].lower() in seen_titles or key in fresh:
                    continue
                d = parse_date(job["date"])
                job["days_ago"] = (datetime.date.today() - d).days if d else None
                if (job["days_ago"] is not None and job["days_ago"] <= RECENT_DAYS) or job["score"] >= 4:
                    fresh[key] = job
        except requests.RequestException as e:
            print(f"[warn] internsg/{kw}: {type(e).__name__}")

    # source 3: MyCareersFuture (full-time SG roles, relevance >= 2)
    for kw in keywords:
        try:
            for job in fetch_mycareersfuture(kw):
                job["score"] = score(job)
                if job["score"] < 2:
                    continue
                key = slug_key(job["url"])
                if key in seen_urls or job["title"].lower() in seen_titles:
                    continue
                fresh[key] = job
        except requests.RequestException as e:
            print(f"[warn] mcf/{kw}: {type(e).__name__}")

    # source 4: GradConnection SG (graduate programmes, relevance >= 1)
    for kw in keywords:
        try:
            for job in fetch_gradconnection(kw):
                job["score"] = score(job)
                if job["score"] < 1:
                    continue
                key = slug_key(job["url"])
                if key in seen_urls or job["title"].lower() in seen_titles or key in fresh:
                    continue
                fresh[key] = job
        except requests.RequestException as e:
            print(f"[warn] gradconnection/{kw}: {type(e).__name__}")

    ranked = sorted(fresh.values(), key=lambda j: (-j["score"], j.get("days_ago") or 99))
    print(f"new jobs found: {len(ranked)}")
    for j in ranked[:10]:
        print(f"  [{j['score']}] {j['date']} {j['company']} | {j['title']} | {j['url']}")

    analyze_top = [j for j in ranked if j["score"] >= 3][: top]
    analyses = []
    cv = cv_summary()
    for j in analyze_top:
        try:
            analyses.append({"job": j, "analysis": analyze(j, cv=cv)})
            print(f"  analyzed: {j['title']}")
        except Exception as e:
            print(f"  [warn] analyze failed {j['title']}: {type(e).__name__}")

    today = datetime.date.today().isoformat()
    lines = [f"# 新岗位监测报告 {today}", ""]
    if not ranked:
        lines.append("今天没有发现新的合适岗位。")
    else:
        lines.append(f"共发现 {len(ranked)} 个新岗位（近 {RECENT_DAYS} 天 / 高相关）:\n")
        for j in ranked:
            lines.append(f"- [{j['score']}分] **{j['title']}** @ {j['company']}（{j['date']}）\n  {j['url']}")
        if analyses:
            lines.append("\n## 重点岗位分析\n")
            for item in analyses:
                j, a = item["job"], item["analysis"]
                lines.append(f"### {j['title']} @ {j['company']}")
                lines.append(f"档位: {a.get('tier', '?')} ｜ 匹配度: {a.get('match', '?')}")
                lines.append("需要补的知识: " + "、".join(a.get("gaps", [])))
                lines.append("着重准备: " + "、".join(a.get("focus", [])))
                lines.append("")

    report = "\n".join(lines)
    path = os.path.join(BASE_DIR, f"data/new_jobs_{today}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    with open(HISTORY, "a", encoding="utf-8") as f:
        for j in ranked:
            entry = {**j, "found_date": today}
            for item in analyses:
                if slug_key(item["job"]["url"]) == slug_key(j["url"]):
                    entry["analysis"] = item["analysis"]
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    with open(LAST_RUN, "w", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M} | 新岗位 {len(ranked)} 条")
    print(f"report -> {path}")
    return len(ranked)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", nargs="*", default=KEYWORDS)
    parser.add_argument("--top", type=int, default=TOP_ANALYZE)
    parser.add_argument("--include-intern", action="store_true", help="keep internship-only listings (default: full-time/graduate focus)")
    parser.add_argument("--sync", action="store_true", help="扫描后自动把新岗位写入投递清单")
    args = parser.parse_args()
    n = run_monitor(keywords=args.keywords, top=args.top, include_intern=args.include_intern)
    if args.sync:
        from scripts.sync_new_to_tracker import sync_new_to_tracker

        res = sync_new_to_tracker()
        print(f"投递清单同步：新增 {res['added']} 条，跳过 EP 不达标 {res['skipped']} 条，重复 {res['dupes']} 条")


if __name__ == "__main__":
    main()
