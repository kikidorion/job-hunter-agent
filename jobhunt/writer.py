"""Tailored resume + cover letter: an LLM drafts from profile facts only, code scrubs AI tells,
TypeSafe verifies every bullet/paragraph against the profile and the posting.

The rules in SYSTEM are the heart of the writer: facts only from your profile, bridge gaps instead of
confessing them, and no typographic or vocabulary tells of AI writing. Edit BANNED to add your own."""
import json
import os
import re

import httpx
import yaml
from typesafe_sdk import Noul, TypeSafeClient

from .common import log, writer_profile

BANNED = [
    "delve", "tapestry", "testament to", "passionate", "excited to", "thrilled", "i am writing to express",
    "resonates", "seamless", "robust", "cutting-edge", "synergy", "in today's", "fast-paced", "ever-evolving",
    "embark", "journey", "unwavering", "deeply aligned", "aligns perfectly", "i'm confident that",
    "i am confident that", "eager to contribute", "look forward to the opportunity", "holistic",
    "furthermore", "moreover", "additionally,", "harness", "empower", "elevate", "foster", "pivotal", "realm",
    "multifaceted", "intricate", "showcasing", "underscore", "vibrant", "profound", "invaluable", "meticulous",
]

SYSTEM = """You write job application documents for one real person. Output JSON only.

HARD RULES
- Use ONLY facts in PROFILE. Never invent employers, titles, dates, numbers, tools, degrees, or outcomes.
  You may select, reorder, merge, and rephrase facts to fit the job. Every metric must appear in PROFILE.
- If the job's key requirement has no evidence in PROFILE, do not claim it. Instead add a short yes/no or
  factual question for the candidate to "questions_for_candidate" (max 2, only when it would materially help).
- Gaps: do NOT volunteer missing skills or experience in the cover letter ("I have not...", "I lack...").
  Bridge instead: name the closest real PROFILE experience and how it transfers. Mention a gap only when the
  job lists it as a hard requirement AND silence would look evasive, and then in one forward-looking clause.
- An experience entry with "highlight": true must be named in the cover letter and tied to this job.
- Experience entries with company "Independent" are self-employment: write the company as "Independent".
- Human style: plain, specific, varied sentence length. First person in the cover letter, no first person in
  resume bullets. No em dashes or en dashes. No semicolons in the letter. No exclamation points.
- Never use these words/phrases: {banned}.
- Cover letter: 3-4 short paragraphs, under 300 words total. Open with the specific role and one concrete
  reason this work matters to the candidate; the middle ties 2-3 PROFILE facts to 2-3 named job needs; close
  plainly. Mention the company by name. Do not restate the resume.
- Resume: headline, 2-sentence summary, 3-4 skill groups ordered by job relevance, all PROFILE experience
  entries in PROFILE order with 2-5 bullets each (most relevant first; start bullets with a strong past-tense
  verb), 0-3 projects ranked by relevance (skip irrelevant ones).

JSON SHAPE
{{"headline": str, "summary": str,
  "skills": [{{"group": str, "items": [str]}}],
  "experience": [{{"company": str, "title": str, "dates": str, "bullets": [str]}}],
  "projects": [{{"name": str, "bullets": [str]}}],
  "cover_letter": {{"greeting": str, "paragraphs": [str], "closing": "Sincerely,"}},
  "questions_for_candidate": [str]}}"""


def _call_writer(model: str, profile_yaml: str, job: dict, family: str, feedback: str | None) -> dict:
    """Retry when the model returns malformed JSON (unescaped quote etc.); it is rare and random."""
    for attempt in range(3):
        try:
            return _call_writer_once(model, profile_yaml, job, family, feedback)
        except json.JSONDecodeError as e:
            log.warning("writer returned bad JSON for %s (try %d): %s", job["id"], attempt + 1, e)
    raise RuntimeError("writer returned malformed JSON 3 times")


def _call_writer_once(model: str, profile_yaml: str, job: dict, family: str, feedback: str | None) -> dict:
    user = (f"ROLE FAMILY (pick emphasis/headline accordingly): {family}\n\nPROFILE\n{profile_yaml}\n\n"
            f"JOB\nTitle: {job['title']}\nCompany: {job['company']}\nLocation: {job['location']}\n\n"
            f"{job['description'][:9000]}")
    if feedback:
        user += f"\n\nREVISION REQUIRED. Fix these problems from your previous draft:\n{feedback}"
    r = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        json={"model": model, "temperature": 0.6, "max_tokens": 4000,
              "messages": [{"role": "system", "content": SYSTEM.format(banned=", ".join(BANNED))},
                           {"role": "user", "content": user}]},
        timeout=180,
    )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def scrub(text: str) -> str:
    """Remove typographic AI tells. Dates keep a plain hyphen."""
    text = re.sub(r"(\d)\s*[–—]\s*(\d|Present)", r"\1 - \2", text)
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'").replace("…", "...")
    return re.sub(r"\s+,", ",", text).strip()


def _walk(doc: dict, fn) -> dict:
    if isinstance(doc, dict):
        return {k: _walk(v, fn) for k, v in doc.items()}
    if isinstance(doc, list):
        return [_walk(v, fn) for v in doc]
    return fn(doc) if isinstance(doc, str) else doc


def banned_hits(doc: dict) -> list[str]:
    blob = json.dumps(doc, ensure_ascii=False).lower()
    return [b for b in BANNED if re.search(r"(?<![a-z])" + re.escape(b) + r"(?![a-z])", blob)]


def _claims(doc: dict) -> list[tuple[str, str]]:
    out = [("summary", doc["summary"])]
    out += [(f"exp{i}.b{k}", b) for i, e in enumerate(doc["experience"]) for k, b in enumerate(e["bullets"])]
    out += [(f"proj{i}.b{k}", b) for i, p in enumerate(doc.get("projects", [])) for k, b in enumerate(p["bullets"])]
    out += [(f"cl.p{i}", p) for i, p in enumerate(doc["cover_letter"]["paragraphs"])]
    return out


def verify(ts: TypeSafeClient, doc: dict, profile: dict, job: dict) -> tuple[list[str], float]:
    """One parallel TypeSafe call: a support check per claim + a generic-letter check."""
    claims = _claims(doc)
    state = {"profile": profile, "job_posting": job["description"][:5000], "claims": [c for _, c in claims],
             "letter": "\n\n".join(doc["cover_letter"]["paragraphs"])}
    qs = {
        f"c{i}": Noul(
            instructions=f"Is every fact about the candidate in `claims[{i}]` (employers, titles, dates, numbers, tools, degrees, accomplishments) stated in or directly implied by `profile`? Statements about the employer may come from `job_posting`. Wording may differ.",
            criteria={"true": "All candidate facts are supported by `profile`",
                      "false": "At least one candidate fact, number, tool, or outcome is missing from `profile` or contradicts it"},
        )
        for i in range(len(claims))
    }
    qs["generic"] = Noul(instructions="Does `letter` read like template text that could be sent to any company, with vague praise and no specific details about this job or the candidate's actual work?")
    res = ts.system_one(state=state, questions=qs)
    unsupported = [claims[i][0] for i in range(len(claims)) if res.nouls[f"c{i}"].noul < 0.5]
    return unsupported, res.nouls["generic"].noul


def _drop_ids(doc: dict, ids: list[str]) -> dict:
    ids = set(ids)
    for i, e in enumerate(doc["experience"]):
        kept = [b for k, b in enumerate(e["bullets"]) if f"exp{i}.b{k}" not in ids]
        e["bullets"] = kept or e["bullets"][:1]  # never leave a job with zero bullets
    for i, p in enumerate(doc.get("projects", [])):
        p["bullets"] = [b for k, b in enumerate(p["bullets"]) if f"proj{i}.b{k}" not in ids]
    doc["projects"] = [p for p in doc.get("projects", []) if p["bullets"]]
    return doc


def write_documents(job: dict, family: str, profile: dict, cfg: dict, industry: str | None = None) -> tuple[dict, dict]:
    """Returns (doc, report). Up to 2 revision rounds, then drops still-unsupported resume bullets."""
    facts = writer_profile(profile, family, industry)
    profile_yaml = yaml.safe_dump(facts, sort_keys=False, allow_unicode=True)
    feedback, report = None, {}
    with TypeSafeClient(model=cfg["models"]["judge"]) as ts:
        for attempt in range(3):
            doc = _walk(_call_writer(cfg["models"]["writer"], profile_yaml, job, family, feedback), scrub)
            hits = banned_hits(doc)
            unsupported, generic = verify(ts, doc, facts, job)
            report = {"attempt": attempt + 1, "banned": hits, "unsupported": unsupported, "generic_p": round(generic, 2)}
            log.info("writer %s attempt %d: %s", job["id"], attempt + 1, report)
            if not hits and not unsupported and generic < 0.6:
                break
            texts = dict(_claims(doc))
            feedback = "\n".join(
                [f"- Remove banned words: {', '.join(hits)}"] * bool(hits)
                + [f"- Not supported by PROFILE, rewrite using only PROFILE facts or remove: \"{texts[c]}\"" for c in unsupported]
                + ["- The cover letter is generic. Name specific needs from the job and specific candidate work."] * (generic >= 0.6)
            )
    doc = _drop_ids(doc, [u for u in report["unsupported"] if not u.startswith(("cl.", "summary"))])
    report["needs_review"] = [u for u in report["unsupported"] if u.startswith(("cl.", "summary"))]
    return doc, report
