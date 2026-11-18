"""Job sources: public ATS board APIs + remote-job aggregators. No login scraping (no ToS risk, no bans).

To add a source: write a generator `name(client, cfg)` that yields `_job(...)` dicts and register it in fetch_all."""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import httpx

from .common import log, title_ok

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
TAG_RE = re.compile(r"<[^>]+>")
MONEY_RE = re.compile(r"\$\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?[kK])(?:\s*(?:-|–|—|to)\s*\$?\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?[kK]))?")
HOURLY_RE = re.compile(r"\$\s?(\d{2,3}(?:\.\d{2})?)\s*(?:-|–|to)?\s*\$?\s?(\d{2,3}(?:\.\d{2})?)?\s*(?:/|per\s)\s*(?:hr|hour)", re.I)


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(html.unescape(text))
    text = re.sub(r"<(br|/p|/li|/h\d|/div)[^>]*>", "\n", text, flags=re.I)
    text = TAG_RE.sub(" ", text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _money(tok: str) -> int:
    tok = tok.replace(",", "").replace(" ", "")
    return int(float(tok[:-1]) * 1000) if tok[-1] in "kK" else int(tok)


def parse_salary_max(text: str) -> int | None:
    """Largest annual figure in a posting. Arithmetic stays in code, never in the model."""
    if not text:
        return None
    vals = []
    for lo, hi in MONEY_RE.findall(text):
        for tok in (lo, hi):
            if tok:
                v = _money(tok)
                if 30_000 <= v <= 1_500_000:
                    vals.append(v)
    for lo, hi in HOURLY_RE.findall(text):
        for tok in (lo, hi):
            if tok and 15 <= float(tok) <= 500:
                vals.append(int(float(tok) * 2080))
    return max(vals) if vals else None


def _salary_snippet(text: str) -> str | None:
    m = MONEY_RE.search(text) or HOURLY_RE.search(text)
    if not m:
        return None
    return text[max(0, m.start() - 60): m.end() + 40].replace("\n", " ").strip()


def _job(source, native_id, company, title, location, url, description, posted_at=None, salary_text=None, salary_max=None):
    description = clean(description)
    salary_text = salary_text or _salary_snippet(description)
    return {
        "id": f"{source}:{native_id}",
        "source": source,
        "company": (company or "").strip(),
        "title": (title or "").strip(),
        "location": (location or "").strip(),
        "url": url,
        "description": description,
        "posted_at": posted_at,
        "salary_text": salary_text,
        "salary_max": salary_max or parse_salary_max(salary_text or "") or parse_salary_max(description),
    }


def _iso_ms(ms) -> str | None:
    return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).isoformat() if ms else None


def greenhouse(client, token):
    r = client.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs", params={"content": "true"})
    for j in r.json().get("jobs", []):
        yield _job("greenhouse", j["id"], j.get("company_name") or token, j["title"],
                   (j.get("location") or {}).get("name", ""), j["absolute_url"], j.get("content"),
                   j.get("first_published") or j.get("updated_at"))


def lever(client, token):
    r = client.get(f"https://api.lever.co/v0/postings/{token}", params={"mode": "json"})
    for j in r.json():
        sr = j.get("salaryRange") or {}
        sal_txt = f"${sr['min']:,}-${sr['max']:,} {sr.get('interval', '')}" if sr.get("max") else None
        lists = "\n".join(f"{x.get('text')}\n{x.get('content')}" for x in j.get("lists", []))
        cats = j.get("categories") or {}
        loc = cats.get("location", "")
        if j.get("workplaceType"):
            loc = f"{loc} ({j['workplaceType']})"
        yield _job("lever", j["id"], token, j["text"], loc, j["hostedUrl"],
                   f"{j.get('descriptionPlain', '')}\n{lists}\n{j.get('additionalPlain', '')}",
                   _iso_ms(j.get("createdAt")), sal_txt,
                   sr.get("max") if sr.get("interval", "").startswith("per-year") else None)


def ashby(client, token):
    r = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{token}", params={"includeCompensation": "true"})
    for j in r.json().get("jobs", []):
        if not j.get("isListed", True):
            continue
        comp = j.get("compensation") or {}
        sal_txt = comp.get("scrapeableCompensationSalarySummary") or comp.get("compensationTierSummary")
        loc = j.get("location", "")
        if j.get("workplaceType"):
            loc = f"{loc} ({j['workplaceType']})"
        yield _job("ashby", j["id"], token, j["title"], loc, j["jobUrl"], j.get("descriptionPlain"),
                   j.get("publishedAt"), sal_txt)


def remotive(client, _cfg=None):
    for cat in ("data", "software-dev", "finance-legal", "all-others"):
        r = client.get("https://remotive.com/api/remote-jobs", params={"category": cat})
        for j in r.json().get("jobs", []):
            yield _job("remotive", j["id"], j["company_name"], j["title"],
                       f"Remote ({j.get('candidate_required_location', '')})", j["url"], j.get("description"),
                       j.get("publication_date"), j.get("salary") or None)


def remoteok(client, _cfg=None):
    r = client.get("https://remoteok.com/api")
    for j in r.json()[1:]:  # element 0 is the API notice
        sal_max = j.get("salary_max") or None
        yield _job("remoteok", j["id"], j.get("company"), j.get("position"),
                   f"Remote ({j.get('location') or 'anywhere'})", j.get("url"), j.get("description"),
                   j.get("date"), f"${j['salary_min']:,}-${sal_max:,}" if sal_max else None, sal_max)


def himalayas(client, _cfg=None):
    for offset in range(0, 400, 20):
        r = client.get("https://himalayas.app/jobs/api", params={"limit": 20, "offset": offset})
        jobs = r.json().get("jobs", [])
        if not jobs:
            break
        for j in jobs:
            mx = j.get("maxSalary")
            posted = datetime.fromtimestamp(int(j["pubDate"]), timezone.utc).isoformat() if j.get("pubDate") else None
            yield _job("himalayas", j["guid"], j.get("companyName"), j.get("title"),
                       "Remote (" + ", ".join(j.get("locationRestrictions") or ["anywhere"]) + ")",
                       j.get("applicationLink"), j.get("description"), posted,
                       f"${j['minSalary']:,}-${mx:,}" if mx and j.get("minSalary") else None,
                       mx if (j.get("salaryPeriod") or "annual") == "annual" else None)


def oracle(client, cfg: dict):
    """Oracle HCM Candidate Experience boards (common at universities, banks, and large employers).
    config: sources.oracle: [{host: careersearch.stanford.edu, site: CX_1, company: Stanford University, search: [data, analyst]}]"""
    for b in cfg["sources"].get("oracle", []):
        api = f"https://{b['host']}/hcmRestApi/resources/latest/"
        seen = set()
        for kw in b.get("search", ["analyst", "data"]):
            # Oracle hangs if ';' and '=' inside `finder` are percent-encoded, so build the URL by hand
            r = client.get(api + "recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;"
                           f"siteNumber={b['site']},keyword=%22{kw.replace(' ', '%20')}%22,limit=100,sortBy=POSTING_DATES_DESC", timeout=90)
            for req in r.json()["items"][0]["requisitionList"]:
                if req["Id"] in seen or not title_ok(req["Title"], cfg):
                    continue
                seen.add(req["Id"])
                try:
                    d = client.get(api + "recruitingCEJobRequisitionDetails?expand=all&onlyData=true&finder=ById;"
                                   f"Id=%22{req['Id']}%22,siteNumber={b['site']}", timeout=60).json()["items"][0]
                except (httpx.HTTPError, KeyError, IndexError) as e:
                    log.warning("oracle %s %s skipped: %s", b["host"], req["Id"], e)
                    continue
                desc = " ".join(d.get(k) or "" for k in ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr"))
                where = d.get("PrimaryLocation") or ""
                if d.get("WorkplaceType"):
                    where = f"{where} ({d['WorkplaceType']})"
                yield _job("oracle", f"{b['host'].split('.')[0]}:{req['Id']}", b.get("company", b["host"]), d["Title"], where,
                           f"https://{b['host']}/hcmUI/CandidateExperience/en/sites/{b['site']}/job/{req['Id']}/",
                           desc, req.get("PostedDate"))


def workday(client, cfg: dict):
    """Workday CXS search API (public JSON behind *.myworkdayjobs.com boards).
    config: sources.workday: [{tenant: acme, wd: wd5, site: Acme_Careers, search: [analyst], facets: {...}}]"""
    from .manual import workday as detail
    for b in cfg["sources"].get("workday", []):
        base = f"https://{b['tenant']}.{b['wd']}.myworkdayjobs.com"
        seen = set()
        for term in b.get("search", ["analyst", "data"]):
            r = client.post(f"{base}/wday/cxs/{b['tenant']}/{b['site']}/jobs", timeout=30,
                            json={"appliedFacets": b.get("facets", {}), "limit": 20, "offset": 0, "searchText": term})
            for p in r.json().get("jobPostings", []):
                if p["externalPath"] in seen or not title_ok(p["title"], cfg):
                    continue
                seen.add(p["externalPath"])
                try:
                    yield from detail(f"{base}/{b['site']}{p['externalPath']}")
                except Exception as e:
                    log.warning("workday %s skipped: %s", p["externalPath"], e)


def fetch_all(cfg: dict) -> list[dict]:
    src = cfg["sources"]
    ats = src.get("ats") or {}
    tasks = [(greenhouse, t) for t in ats.get("greenhouse") or []]
    tasks += [(lever, t) for t in ats.get("lever") or []]
    tasks += [(ashby, t) for t in ats.get("ashby") or []]
    tasks += [(fn, cfg) for name, fn in {"remotive": remotive, "remoteok": remoteok, "himalayas": himalayas}.items() if src.get(name)]
    tasks += [(fn, cfg) for name, fn in {"oracle": oracle, "workday": workday}.items() if src.get(name)]

    def run(task):
        fn, arg = task
        try:
            with httpx.Client(headers=UA, timeout=30, follow_redirects=True) as client:
                return list(fn(client, arg))
        except Exception as e:  # one dead board must not kill the run
            log.warning("source %s:%s failed: %s", fn.__name__, arg if isinstance(arg, str) else "", e)
            return []

    with ThreadPoolExecutor(12) as ex:
        jobs = [j for batch in ex.map(run, tasks) for j in batch]
    log.info("fetched %d postings from %d sources", len(jobs), len(tasks))
    return jobs
