"""How well your config.yaml weights rank the postings YOU labeled yes/no (`add yes|no URL`).

AUC = the chance a random "yes" scores above a random "no". 0.5 is a coin flip, 1.0 is perfect.
Workflow: label 10-20 real postings, run this, adjust weights/values in config.yaml, `rescore`, repeat.
Look at the misranked rows: if your "no" roles score high on a feature, that feature's weight is too big."""
import json

from .common import load_config
from .judge import composite
from .store import connect


def report() -> None:
    cfg, db = load_config(), connect()
    rows = db.execute("SELECT j.*, l.label FROM jobs j JOIN labels l ON l.job_id = j.id WHERE j.judgments IS NOT NULL").fetchall()
    scored = [(composite(json.loads(r["judgments"]), dict(r), cfg)[0], r["label"], r["company"], r["title"][:40]) for r in rows]
    pos = [s for s, lab, *_ in scored if lab]
    neg = [s for s, lab, *_ in scored if not lab]
    if not pos or not neg:
        print(f"Need at least one 'yes' and one 'no' label (have {len(pos)} yes, {len(neg)} no). "
              "Label postings with: python -m jobhunt add yes|no URL")
        return
    auc = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))
    print(f"AUC {auc:.2f} on {len(pos)} yes / {len(neg)} no  (1.0 = every yes ranks above every no)")
    for s, lab, company, title in sorted(scored, reverse=True):
        print(f"  {s:.2f} {'YES' if lab else ' no'} {company[:14]:14} {title}")
