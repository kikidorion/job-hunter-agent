"""Add postings you found yourself (any URL), scored like the rest:
    python -m jobhunt add yes URL [URL...]    # you want it: labeled 1, gets documents first on the next run
    python -m jobhunt add no URL [URL...]     # you don't: labeled 0, teaches calibration what to rank low
    python -m jobhunt add check URL [URL...]  # score only, no label
"""
import html
import json
import re

import httpx

from .common import load_config, load_profile
from .judge import judge_many
from .sources import _job, clean
from .store import connect, now

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/130 Safari/537.36"}


def _page_text(url: str) -> tuple[str, str]:
    t = httpx.get(url, headers=UA, timeout=30, follow_redirects=True).text
    title = html.unescape(re.search(r"(?is)<title>(.*?)</title>", t).group(1)).strip() if "<title" in t else url
    t = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", t)
    return title, clean(t)


def generic(url: str) -> list[dict]:
    title, text = _page_text(url)
    return [_job("manual", re.sub(r"\W+", "-", url)[-80:], title.split(" - ")[0][:60], title[:120], "", url, text[:15000])]


def greenhouse(url: str) -> list[dict]:
    """Greenhouse pages render with JS; the public board API has the full posting."""
    board, jid = re.search(r"greenhouse\.io/(?:embed/job_app\?for=)?([^/?&]+)/jobs/(\d+)", url).groups()
    d = httpx.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}", params={"pay_transparency": "true"},
                  headers=UA, timeout=30).json()
    pay = (d.get("pay_input_ranges") or [{}])[0]
    sal_txt = f"${pay['min_cents'] // 100:,}-${pay['max_cents'] // 100:,}" if pay.get("max_cents") else None
    return [_job("greenhouse", jid, d.get("company_name") or board, d["title"], (d.get("location") or {}).get("name", ""),
                 d.get("absolute_url") or url.split("?")[0], d.get("content"), d.get("first_published"), sal_txt,
                 pay["max_cents"] // 100 if pay.get("max_cents") else None)]


def workday(url: str) -> list[dict]:
    """Workday boards are JS-only; the CXS JSON API behind them is public."""
    m = re.match(r"https://([^.]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/]+)/(job/[^?]+)", url)
    tenant, wd, site, path = m.groups()
    d = httpx.get(f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/{path}",
                  headers={**UA, "Accept": "application/json"}, timeout=30).json()["jobPostingInfo"]
    return [_job("workday", f"{tenant}:{d['jobReqId']}", tenant.capitalize(), d["title"], d.get("location", ""),
                 d.get("externalUrl") or url.split("?")[0], d.get("jobDescription"), d.get("startDate"))]


def oracle(url: str) -> list[dict]:
    """Oracle HCM Candidate Experience boards (.../hcmUI/CandidateExperience/<lang>/sites/<SITE>/job/<ID>)."""
    host, site, rid = re.match(r"https://([^/]+)/hcmUI/CandidateExperience/[^/]+/sites/([^/]+)/job/(\d+)", url).groups()
    api = (f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
           f"?expand=all&onlyData=true&finder=ById;Id=%22{rid}%22,siteNumber={site}")
    d = httpx.get(api, headers=UA, timeout=30).json()["items"][0]
    desc = " ".join(d.get(k) or "" for k in ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr"))
    tenant = host.split(".")[0]  # a tenant code, not always the company name: fix it with `python -m jobhunt rename`
    return [_job("oracle", f"{tenant}:{rid}", tenant, d["Title"], d.get("PrimaryLocation") or "", url.split("?")[0], desc)]


def fetch(url: str) -> list[dict]:
    if "myworkdayjobs.com" in url:
        return workday(url)
    if "oraclecloud.com/hcmUI/CandidateExperience" in url or "/hcmUI/CandidateExperience/" in url:
        return oracle(url)
    if "greenhouse.io" in url and "/jobs/" in url:
        return greenhouse(url)
    return generic(url)


def add(label_word: str, urls: list[str]) -> None:
    label = {"yes": 1, "1": 1, "no": 0, "0": 0, "check": None, "-": None}[label_word]
    cfg, db = load_config(), connect()
    jobs = []
    for u in urls:
        if not u.startswith("http"):
            print(f"SKIPPED (not a link): {u}")
            continue
        try:
            got = fetch(u)
        except Exception as e:
            print(f"SKIPPED (could not read this page: {type(e).__name__}): {u}")
            continue
        if not got or len(got[0]["description"]) < 300:
            print(f"SKIPPED (page has no readable job text, likely built with JavaScript; look for the employer's own job board link): {u}")
            continue
        jobs += got
    if not jobs:
        return
    for j in jobs:
        db.execute("INSERT OR REPLACE INTO jobs (id, source, company, title, location, url, salary_text, salary_max, posted_at,"
                   " description, first_seen, status) VALUES (?,?,?,?,?,?,?,?,?,?,?, 'scored')",
                   (j["id"], j["source"], j["company"], j["title"], j["location"], j["url"], j.get("salary_text"),
                    j.get("salary_max"), j.get("posted_at"), j["description"], now()))
        if label is not None:
            db.execute("INSERT OR REPLACE INTO labels (job_id, label) VALUES (?, ?)", (j["id"], label))
    for jid, jd in judge_many(jobs, load_profile(), cfg).items():
        db.execute("UPDATE jobs SET judgments=? WHERE id=?", (json.dumps(jd), jid))
    db.commit()
    from .__main__ import apply_scores
    apply_scores(db, cfg)
    for j in jobs:
        r = db.execute("SELECT composite, tier FROM jobs WHERE id=?", (j["id"],)).fetchone()
        print(f"{r['tier'] or '-'} {r['composite'] or 0:.2f}  {j['company'][:20]:20} {j['title'][:60]}  id={j['id']}")
