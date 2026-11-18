"""Job Hunter: finds roles, ranks them by what YOU value, drafts tailored documents. Never applies for you.

    python -m jobhunt run                     fetch, score, write documents for top roles, send the digest
    python -m jobhunt check                   verify config, profile, API keys, Chrome, and Telegram
    python -m jobhunt add yes|no|check URL..  score a posting you found (yes/no also labels it for calibration)
    python -m jobhunt rescore                 re-apply config.yaml weights to every scored job (no API calls)
    python -m jobhunt rejudge                 re-ask Jev about every scored job (after editing questions)
    python -m jobhunt calibrate               how well your weights rank your own yes/no labels (AUC)
    python -m jobhunt applied ID|FOLDER       mark a role applied
    python -m jobhunt skip ID|FOLDER          mark a role skipped
    python -m jobhunt rename ID "Company"     fix a company name
    python -m jobhunt status                  counts by status and tier
    python -m jobhunt dashboard               rebuild queue/index.html
    python -m jobhunt telegram-setup          connect your Telegram bot (docs/TELEGRAM.md)
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from . import judge, telegram
from .common import QUEUE, kw_pattern, load_config, load_env, load_profile, log, setup_logging
from .store import connect, kv_get, kv_set, upsert_new

DEFAULT_PROMPTS = {
    "work_authorization": "Are you authorized to work in the country where you are applying? (yes/no)",
    "requires_sponsorship": "Will you now or later need visa sponsorship? (yes/no)",
    "earliest_start": "Earliest start date you want forms to say (e.g. '2 weeks notice')?",
    "salary_expectation": "Salary expectation for forms (e.g. '$140k-$165k base')?",
    "pronouns": "Pronouns for forms that ask (or 'skip')?",
}
AGGREGATORS = {"remotive", "remoteok", "himalayas"}


def _age_ok(posted_at: str | None, max_days: int) -> bool:
    if not posted_at:
        return True
    try:
        ts = datetime.fromisoformat(str(posted_at).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts >= datetime.now(timezone.utc) - timedelta(days=max_days)
    except ValueError:
        return True


def prefilter(job: dict, cfg: dict) -> str | None:
    """Cheap code rules. Returns reject reason or None."""
    hf = cfg["hard_filters"]
    title = job["title"]
    if not kw_pattern(cfg["title_keywords"]).search(title):
        return "title"
    if kw_pattern(cfg["exclude_title_keywords"]).search(title):
        return "title_excluded"
    if job.get("salary_max") and job["salary_max"] < hf["salary_floor"]:
        return f"salary<{hf['salary_floor']}"
    # company boards only list open roles, so age only matters for aggregators that keep dead listings
    if job["source"] in AGGREGATORS and not _age_ok(job.get("posted_at"), hf["max_posting_age_days"]):
        return "stale"
    if len(job["description"]) < 300:
        return "no_description"
    return None


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:50]


def queue_job(db, row, j: dict, breakdown: dict, profile: dict, cfg: dict) -> None:
    from .render import render_all
    from .writer import write_documents

    job = dict(row)
    family = j["role_family"]["choice"]
    if family not in cfg["role_families"]:
        family = next(iter(cfg["role_families"]))
    doc, report = write_documents(job, family, profile, cfg, j["industry"]["choice"])
    folder = QUEUE / f"{datetime.now():%Y-%m-%d}_{_slug(job['company'])}_{_slug(job['title'])}"
    render_all(doc, profile, job, folder)
    defaults = profile.get("application_defaults", {})
    (folder / "APPLY.md").write_text(
        f"# {job['title']} at {job['company']}\n\n"
        f"**Apply:** {job['url']}\n\n**Location:** {job['location']}  \n**Salary:** {job.get('salary_text') or 'not listed'}\n\n"
        f"**Value score:** {row['composite']:.2f} (tier {row['tier']})  \n**Parts:** {json.dumps(breakdown['parts'])}  \n"
        f"**Flags:** {', '.join(breakdown['flags']) or 'none'}  \n**Low-confidence judgments:** {', '.join(breakdown['low_confidence']) or 'none'}\n\n"
        f"**Arrangement:** {j['arrangement']['choice']} · **Industry:** {j['industry']['choice']} · **Resume variant:** {family}\n\n"
        f"## Form answers\n" + "".join(f"- {k}: {v}\n" for k, v in defaults.items()) +
        f"\n## Writer QA\n```\n{json.dumps(report, indent=2)}\n```\n"
        + ("\n**⚠ Review before sending:** cover letter/summary sections flagged as not fully supported: "
           + ", ".join(report["needs_review"]) + "\n" if report["needs_review"] else "")
    )
    for q in doc.get("questions_for_candidate", [])[:2]:
        telegram.ask(db, "extra_facts", None, f"For {job['company']} ({job['title']}): {q}")
    db.execute("UPDATE jobs SET status='queued', queue_dir=? WHERE id=?", (str(folder), row["id"]))
    db.commit()
    log.info("queued %s -> %s", row["id"], folder)


def apply_scores(db, cfg: dict) -> None:
    for row in db.execute("SELECT * FROM jobs WHERE judgments IS NOT NULL").fetchall():
        value, breakdown = judge.composite(json.loads(row["judgments"]), dict(row), cfg)
        tier = "A" if value >= cfg["tiers"]["A"] else "B" if value >= cfg["tiers"]["B"] else "C"
        db.execute("UPDATE jobs SET composite=?, tier=?, filter_reason=? WHERE id=?",
                   (value, tier, json.dumps(breakdown), row["id"]))
    db.commit()


def dashboard(db) -> None:
    QUEUE.mkdir(exist_ok=True)
    rows = db.execute("SELECT * FROM jobs WHERE tier IN ('A','B') AND status NOT IN ('skipped') ORDER BY composite DESC LIMIT 150").fetchall()
    def docs_link(r) -> str:
        if not r["queue_dir"]:
            return ""
        return '<a href="' + r["queue_dir"].replace(os.sep, "/").split("/queue/")[-1] + '/APPLY.md">docs</a>'

    trs = "".join(
        f"<tr class='{r['status']}'><td>{r['composite']:.2f}</td><td>{r['tier']}</td><td>{r['status']}</td>"
        f"<td><a href='{r['url']}'>{r['title']}</a></td><td>{r['company']}</td><td>{r['location']}</td>"
        f"<td>{r['salary_text'] or ''}</td><td>{', '.join(json.loads(r['filter_reason'])['flags'])}</td>"
        f"<td>{docs_link(r)}</td></tr>"
        for r in rows)
    (QUEUE / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Job Hunter</title><style>body{font:14px system-ui;margin:16px;background:#fff;color:#111}"
        "@media(prefers-color-scheme:dark){body{background:#111;color:#eee}a{color:#8ab4ff}}table{border-collapse:collapse;width:100%}"
        "td,th{padding:4px 8px;border-bottom:1px solid #8884;text-align:left}.applied{opacity:.45}</style>"
        f"<h1>Job Hunter</h1><p>Updated {datetime.now():%Y-%m-%d %H:%M}</p><table><tr><th>Value</th><th>Tier</th><th>Status</th>"
        f"<th>Role</th><th>Company</th><th>Location</th><th>Salary</th><th>Flags</th><th>Docs</th></tr>{trs}</table>")


def _writer_has_credit() -> bool:
    import httpx
    try:
        d = httpx.get("https://openrouter.ai/api/v1/credits", timeout=15,
                      headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}).json()["data"]
        return d["total_credits"] - d["total_usage"] > 0.25
    except Exception:
        return True  # unknown: let the writer try


def run() -> None:
    cfg, db = load_config(), connect()
    if not os.environ.get("TYPESAFE_API_KEY"):
        if not kv_get(db, "warned_no_key"):
            telegram.send("Job Hunter paused: add TYPESAFE_API_KEY to .env (create one at console.typesafe.ai).")
            kv_set(db, "warned_no_key", True); db.commit()
        log.error("TYPESAFE_API_KEY missing; skipping run")
        return
    got = telegram.collect_answers(db)
    db.commit()
    profile = load_profile()

    for key, val in profile.get("application_defaults", {}).items():
        if val is None and key in DEFAULT_PROMPTS:
            telegram.ask(db, "application_defaults", key, DEFAULT_PROMPTS[key])
    db.commit()

    from .sources import fetch_all
    new = 0
    for job in fetch_all(cfg):
        if upsert_new(db, job):
            new += 1
            reason = prefilter(job, cfg)
            if reason:
                db.execute("UPDATE jobs SET status='filtered', filter_reason=? WHERE id=?", (reason, job["id"]))
    db.commit()

    pending = [dict(r) for r in db.execute("SELECT * FROM jobs WHERE status='new'").fetchall()]
    log.info("%d new postings, %d passed prefilter -> Jev", new, len(pending))
    for jid, j in judge.judge_many(pending, profile, cfg).items():
        db.execute("UPDATE jobs SET judgments=?, status='scored' WHERE id=?", (json.dumps(j), jid))
    db.commit()
    apply_scores(db, cfg)

    # roles you said yes to go first, whatever their score; then tier A by value
    to_queue = db.execute(
        "SELECT j.* FROM jobs j LEFT JOIN labels l ON l.job_id = j.id WHERE j.status='scored' AND j.judgments IS NOT NULL"
        " AND (l.label = 1 OR (j.tier='A' AND l.label IS NULL)) ORDER BY COALESCE(l.label, 0) DESC, j.composite DESC LIMIT ?",
        (cfg["max_docs_per_run"],)).fetchall()
    queued = []
    if to_queue and not _writer_has_credit():
        log.error("OpenRouter has no credit; %d tier-A roles wait for documents", len(to_queue))
        telegram.send(f"Job Hunter: {len(to_queue)} top roles ready but OpenRouter credit is $0. "
                      "Add credit at openrouter.ai/settings/credits; documents generate next run.")
        to_queue = []
    for row in to_queue:
        try:
            queue_job(db, row, json.loads(row["judgments"]), json.loads(row["filter_reason"]), profile, cfg)
            queued.append(row)
        except Exception as e:
            log.exception("queue failed %s: %s", row["id"], e)
    dashboard(db)

    b_new = db.execute("SELECT * FROM jobs WHERE tier='B' AND status='scored' AND first_seen >= datetime('now','-13 hours') "
                       "ORDER BY composite DESC LIMIT 8").fetchall()
    if queued or b_new:
        lines = [f"🎯 Job Hunter: {len(pending)} new roles scored, {len(queued)} ready to apply"]
        for r in queued:
            lines.append(f"\n✅ {r['composite']:.2f} {r['title']} @ {r['company']}\n   {r['location']} | {r['salary_text'] or 'pay n/a'}\n   {r['url']}")
        if b_new:
            lines.append("\nWorth a look (tier B):")
            lines += [f"• {r['composite']:.2f} {r['title']} @ {r['company']} {r['url']}" for r in b_new]
        lines.append(f"\nDocuments: queue/ folder  (answers received this run: {got})")
        telegram.send("\n".join(lines))
    log.info("run done: new=%d scored=%d queued=%d", new, len(pending), len(queued))


def check() -> None:
    """Preflight: everything a first run needs, with the fix for each problem."""
    ok = True

    def report(good: bool, what: str, fix: str = "") -> None:
        nonlocal ok
        ok &= good
        print(("  ok   " if good else "  FIX  ") + what + ("" if good else f"\n         -> {fix}"))

    try:
        cfg = load_config(); report(True, "config.yaml")
        for key in ("industries", "role_families", "weights"):
            report(key in cfg, f"config.yaml has `{key}`", "compare with config.example.yaml")
    except SystemExit as e:
        report(False, "config.yaml", str(e)); cfg = None
    try:
        p = load_profile(); report(True, "profile.yaml")
        report(bool(p.get("name")) and bool(p.get("experience")), "profile has a name and experience", "fill in profile.yaml")
        report(isinstance(p.get("years_experience"), (int, float)), "profile has years_experience", "add years_experience: <number>")
    except SystemExit as e:
        report(False, "profile.yaml", str(e))
    report(bool(os.environ.get("TYPESAFE_API_KEY")), "TYPESAFE_API_KEY", "create at console.typesafe.ai, add to .env")
    report(bool(os.environ.get("OPENROUTER_API_KEY")), "OPENROUTER_API_KEY", "create at openrouter.ai/keys, add to .env")
    try:
        from .render import chrome_path
        report(True, f"Chrome for PDFs: {chrome_path()}")
    except SystemExit as e:
        report(False, "Chrome for PDFs", str(e))
    if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
        report(bool(telegram._call("getMe")), "Telegram bot token", "run: python -m jobhunt telegram-setup")
    else:
        print("  --   Telegram not set up (optional): python -m jobhunt telegram-setup")
    print("\nReady. Try: python -m jobhunt run" if ok else "\nFix the items above, then run check again.")


def main() -> None:
    setup_logging()
    load_env()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    args = sys.argv[2:]
    if cmd == "run":
        run()
    elif cmd == "check":
        check()
    elif cmd == "add" and len(args) >= 2:
        from .manual import add
        add(args[0], args[1:])
    elif cmd == "rejudge":
        cfg, db = load_config(), connect()
        rows = [dict(r) for r in db.execute("SELECT * FROM jobs WHERE judgments IS NOT NULL AND status='scored'")]
        for jid, j in judge.judge_many(rows, load_profile(), cfg).items():
            db.execute("UPDATE jobs SET judgments=? WHERE id=?", (json.dumps(j), jid))
        db.commit(); apply_scores(db, cfg); dashboard(db)
        print(f"rejudged {len(rows)}")
    elif cmd == "calibrate":
        from .calibrate import report
        report()
    elif cmd == "rescore":
        db = connect(); apply_scores(db, load_config()); dashboard(db)
        print("rescored")
    elif cmd == "dashboard":
        dashboard(connect())
    elif cmd in ("applied", "skip") and args:
        db = connect()
        cur = db.execute("UPDATE jobs SET status=? WHERE id=? OR queue_dir LIKE ?",
                         ("applied" if cmd == "applied" else "skipped", args[0], f"%{args[0]}%"))
        db.commit(); dashboard(db)
        print(f"marked {cur.rowcount} role(s) {cmd}" if cur.rowcount else f"no role matched '{args[0]}'")
    elif cmd == "rename" and len(args) == 2:
        db = connect()
        cur = db.execute("UPDATE jobs SET company=? WHERE id=?", (args[1], args[0])); db.commit()
        print(f"renamed {cur.rowcount} role(s)")
    elif cmd == "status":
        db = connect()
        for r in db.execute("SELECT status, tier, COUNT(*) n FROM jobs GROUP BY status, tier ORDER BY status"):
            print(r["status"], r["tier"], r["n"])
    elif cmd == "telegram-setup":
        telegram.setup()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
