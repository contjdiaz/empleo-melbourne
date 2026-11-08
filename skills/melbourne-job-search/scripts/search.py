#!/usr/bin/env python3
"""Search real job ads in Melbourne: SEEK, LinkedIn (guest) and Victorian Government Careers.

Standard library only, so it runs in the Managed Agents sandbox with no install.

Commands
  search   run one or more keyword sets on the chosen sources; print compact JSON
  remember add job URLs to the seen list, so later searches mark them "seen"

Examples
  python3 search.py search -k "admin assistant" -k "receptionist" --type fulltime \
      --seen /mnt/memory/job-finder-memory/seen.json
  python3 search.py remember --seen /mnt/memory/job-finder-memory/seen.json URL [URL ...]

Every job comes from a source response. A value the source does not give is "not specified".
Cleaning jobs are removed by title and counted in "excluded_cleaning".
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)
NS = "not specified"
EXCLUDE = (
    "cleaner", "cleaning", "housekeep", "janitor", "limpieza",
    "domestic clean", "commercial clean", "window clean", "laundry attendant",
)
SEEK_TYPES = {"fulltime": "242", "parttime": "243", "contract": "244", "casual": "245"}
LINKEDIN_TYPES = {"fulltime": "F", "parttime": "P", "contract": "C", "casual": "T"}
MAX_SEEN = 1000
SUMMARY_CHARS = 220


def _get(url: str, referer: str, accept: str, timeout: int = 20, tries: int = 2) -> str:
    last = ""
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept": accept,
            "Accept-Language": "en-AU,en;q=0.9", "Referer": referer,
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as err:
            last = f"HTTP {err.code}"
            if err.code in (429, 500, 502, 503):
                time.sleep(1.5 * (attempt + 1))
                continue
            break
        except (urllib.error.URLError, TimeoutError) as err:
            last = f"network error: {err}"
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(last or "no response")


def _clean(text: Any) -> str:
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", str(text or "")))
    return re.sub(r"\s+", " ", text).strip()


def _excluded(title: str) -> str | None:
    low = title.lower()
    return next((p for p in EXCLUDE if p in low), None)


# ── SEEK ────────────────────────────────────────────────────────────────

def seek(keywords: str, work_type: str, where: str) -> list[dict[str, Any]]:
    params = {"siteKey": "AU-Main", "where": where, "page": "1", "pagesize": "30",
              "sortmode": "ListedDate", "keywords": keywords}
    if work_type in SEEK_TYPES:
        params["worktype"] = SEEK_TYPES[work_type]
    raw = _get("https://au.seek.com/api/jobsearch/v5/search?" + urllib.parse.urlencode(params),
               "https://au.seek.com/", "application/json, text/plain, */*")
    data = json.loads(raw)
    jobs = []
    for j in data.get("data") or []:
        jid = str(j.get("id") or "")
        if not jid:
            continue
        def label(v: Any) -> str:
            return str(v.get("label") or v.get("text") or "") if isinstance(v, dict) else str(v or "")
        jobs.append({
            "title": _clean(j.get("title")),
            "company": _clean(j.get("companyName")) or NS,
            "location": ", ".join(label(x) for x in j.get("locations") or [] if label(x)) or NS,
            "work_type": ", ".join(label(x) for x in j.get("workTypes") or [] if label(x)) or NS,
            "salary": _clean(j.get("salaryLabel")) or NS,
            "posted": _clean(j.get("listingDateDisplay")) or NS,
            "summary": _clean(j.get("teaser"))[:SUMMARY_CHARS],
            "url": f"https://www.seek.com.au/job/{jid}",
            "source": "SEEK",
        })
    return jobs


# ── LinkedIn (public guest endpoint, no login) ─────────────────────────

def linkedin(keywords: str, work_type: str, where: str) -> list[dict[str, Any]]:
    params = {"keywords": keywords, "location": "Melbourne, Victoria, Australia", "start": 0}
    if work_type in LINKEDIN_TYPES:
        params["f_JT"] = LINKEDIN_TYPES[work_type]
    page = _get("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
                + urllib.parse.urlencode(params),
                "https://www.linkedin.com/jobs", "text/html,application/xhtml+xml,*/*;q=0.8")
    jobs = []
    for block in re.findall(r"<li[^>]*>(.+?)</li>", page, re.DOTALL):
        link = re.search(r'base-card__full-link[^>]*href="([^"]+)"', block)
        title = re.search(r"base-search-card__title[^>]*>\s*([^<]+)", block)
        if not link or not title:
            continue
        company = re.search(r"base-search-card__subtitle[^>]*>\s*(?:<a[^>]*>)?\s*([^<]+)", block)
        place = re.search(r"job-search-card__location[^>]*>\s*([^<]+)", block)
        when = re.search(r"<time[^>]*>\s*([^<]+)", block)
        salary = re.search(r"job-search-card__salary-info[^>]*>\s*([^<]+)", block)
        jobs.append({
            "title": _clean(title.group(1)),
            "company": _clean(company.group(1)) if company else NS,
            "location": _clean(place.group(1)) if place else NS,
            # LinkedIn's list does not show the work type; the filter asked for it, so say that.
            "work_type": f"{work_type} (search filter)" if work_type in LINKEDIN_TYPES else NS,
            "salary": _clean(salary.group(1)) if salary else NS,
            "posted": _clean(when.group(1)) if when else NS,
            "summary": "",
            "url": html_lib.unescape(link.group(1)).split("?")[0],
            "source": "LinkedIn",
        })
    return jobs


# ── Victorian Government Careers ───────────────────────────────────────

def vic(keywords: str, work_type: str, where: str) -> list[dict[str, Any]]:
    page = _get("https://www.careers.vic.gov.au/jobs?" + urllib.parse.urlencode({"keyword": keywords}),
                "https://www.careers.vic.gov.au/", "text/html,application/xhtml+xml,*/*;q=0.8")
    blocks = re.findall(
        r'<div class="job-searchResult-header">(.+?)(?=<div class="job-searchResult-header"|</rpl-content>|$)',
        page, re.DOTALL)
    jobs = []
    for block in blocks:
        link = re.search(r'href="(/job/[^"]+)"[^>]*>\s*<h3>([^<]+)</h3>', block)
        if not link:
            continue
        dept = re.search(r'<p[^>]*class="[^"]*rpl-type-p-small[^"]*"[^>]*>([^<]+)</p>', block)
        salary = re.search(r"(\$[\d,]+(?:\.\d+)?\s*[-–]\s*\$[\d,]+(?:\.\d+)?)", block)
        jobs.append({
            "title": _clean(link.group(2)),
            "company": _clean(dept.group(1)) if dept else "Victorian Government",
            "location": NS,
            "work_type": NS,
            "salary": salary.group(1) if salary else NS,
            "posted": NS,
            "summary": "",
            "url": "https://www.careers.vic.gov.au" + link.group(1).strip(),
            "source": "Victorian Government Careers",
        })
    return jobs


SOURCES = {"seek": seek, "linkedin": linkedin, "vic": vic}


# ── seen list (memory store) ───────────────────────────────────────────

def load_seen(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in (data.get("seen") or {}).items()}
    except (json.JSONDecodeError, AttributeError):
        return {}


def save_seen(path: str, seen: dict[str, str]) -> None:
    items = sorted(seen.items(), key=lambda kv: kv[1])[-MAX_SEEN:]  # keep the newest
    Path(path).write_text(json.dumps({"seen": dict(items)}, indent=0) + "\n", encoding="utf-8")


# ── commands ───────────────────────────────────────────────────────────

def cmd_search(args: argparse.Namespace) -> dict[str, Any]:
    keywords = [k.strip() for k in args.keywords if k.strip()] or [""]
    sources = [s.strip() for s in args.sources.split(",") if s.strip() in SOURCES]
    seen = load_seen(args.seen)
    tasks = [(s, k) for s in sources for k in keywords]
    status: dict[str, str] = {}
    found: list[dict[str, Any]] = []

    def run(task: tuple[str, str]) -> tuple[str, str, list[dict[str, Any]] | str]:
        source, kw = task
        try:
            return source, kw, SOURCES[source](kw, args.type, args.where)
        except Exception as err:  # one failed source must not stop the others
            return source, kw, f"failed: {err}"

    with ThreadPoolExecutor(max_workers=6) as pool:
        for source, kw, result in pool.map(run, tasks):
            if isinstance(result, str):
                status.setdefault(source, result)
            else:
                status[source] = "ok"
                found.extend(result)

    jobs, urls, excluded = [], set(), 0
    for job in found:
        if job["url"] in urls:
            continue
        urls.add(job["url"])
        if _excluded(job["title"]):
            excluded += 1
            continue
        job["status"] = "seen" if job["url"] in seen else "new"
        jobs.append(job)

    jobs.sort(key=lambda j: (j["status"] != "new", "full" not in j["work_type"].lower()))
    # Interleave sources before the limit, so a source with less data in its list
    # (Vic Careers shows no work type) is not always cut off by the sort.
    by_source: dict[str, list[dict[str, Any]]] = {}
    for job in jobs:
        by_source.setdefault(job["source"], []).append(job)
    queues = list(by_source.values())
    jobs = [q[i] for i in range(max((len(q) for q in queues), default=0)) for q in queues if i < len(q)]
    return {
        "query": {"keywords": keywords, "type": args.type, "sources": sources},
        "source_status": status,
        "returned": len(jobs[: args.limit]),
        "total_found": len(jobs),
        "excluded_cleaning": excluded,
        "jobs": jobs[: args.limit],
    }


def cmd_remember(args: argparse.Namespace) -> dict[str, Any]:
    if not args.seen:
        return {"saved": 0, "note": "no --seen path; nothing saved"}
    seen = load_seen(args.seen)
    today = date.today().isoformat()
    for url in args.urls:
        seen[url.strip()] = today
    save_seen(args.seen, seen)
    return {"saved": len(args.urls), "seen_total": min(len(seen), MAX_SEEN)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="search job ads")
    s.add_argument("-k", "--keywords", action="append", default=[], help="keyword set; repeat for more")
    s.add_argument("--type", default="fulltime", choices=["fulltime", "parttime", "contract", "casual", "any"])
    s.add_argument("--where", default="Melbourne VIC", help="SEEK location text (LinkedIn uses Melbourne)")
    s.add_argument("--sources", default="seek,linkedin,vic", help="comma list: seek,linkedin,vic")
    s.add_argument("--seen", help="path of seen.json in the memory store")
    s.add_argument("--limit", type=int, default=40, help="max jobs in the output")

    r = sub.add_parser("remember", help="mark job URLs as seen")
    r.add_argument("--seen", help="path of seen.json in the memory store")
    r.add_argument("urls", nargs="+")

    args = parser.parse_args()
    result = cmd_search(args) if args.command == "search" else cmd_remember(args)
    json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
