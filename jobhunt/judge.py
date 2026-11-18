"""What YOU value in a role, as TypeSafe System One (Jev) judgments.

Jev answers narrow, typed questions about one posting (a 0-3 score, a choice from a fixed list, or a
yes/no probability called a Noul). Code owns everything else: weights, dealbreakers, salary math, dates.
Raw answers are stored per job, so re-weighting in config.yaml (`python -m jobhunt rescore`) never re-calls
the API.

Your industries, role families, home country, and years of experience come from config.yaml and
profile.yaml, so the same questions work for any candidate.
"""
from concurrent.futures import ThreadPoolExecutor

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from .common import log

DESC_CHARS = 12000  # benefits sections sit at the end of postings and they matter
SCORE_MAX = 3       # every Score below has 4 levels (0-3)


def candidate_summary(profile: dict) -> dict:
    """What Jev sees about you when judging fit and seniority."""
    js = profile.get("judge_summary", {})
    return {
        "years_of_experience": profile.get("years_experience"),
        "experience": js.get("experience") or "; ".join(f"{e['title']} at {e['company']}" for e in profile.get("experience", [])),
        "education": "; ".join(f"{e['degree']}, {e['school']}" for e in profile.get("education", [])),
        "skills": ", ".join(sum(profile.get("skills", {}).values(), [])),
        "independent_work": js.get("independent_work") or "; ".join(p["name"] for p in profile.get("projects", []) if p.get("include", True)),
    }


def build_questions(cfg: dict, profile: dict) -> dict:
    country = cfg.get("home_country", "the United States")
    years = profile.get("years_experience", "several")
    industries = {k: v["describe"] for k, v in cfg["industries"].items()}
    industries.setdefault("other", "Anything else")
    families = {k: v["describe"] for k, v in cfg["role_families"].items()}
    families.setdefault("other", "None of these")
    return {
        # ---- FLEXIBILITY ---------------------------------------------------------------
        "arrangement": Choice(
            instructions="Where and how often must the person in `job` work in person? Use `job.location` and `job.description`.",
            criteria={
                "remote_anywhere": f"Fully remote from anywhere in {country} (or anywhere), no required office days",
                "remote_restricted": "Remote, but limited to certain states, a region, a time zone, or with regular required travel",
                "hybrid_light": "In office 1-2 days per week, or only occasionally (e.g. monthly or quarterly)",
                "onsite_heavy": "In office or on site 3 or more days per week, or fully on site",
                "unclear": "The posting does not say",
            },
        ),
        "autonomy": Score(
            instructions="How much does the person in `job` choose which problems to work on and how to solve them, based only on `job.description`?",
            criteria=[
                "Ticket-taker: fulfills requests, reports, or tasks others define; close supervision",
                "Some ownership: owns recurring deliverables, but others set priorities and methods",
                "Strong ownership: owns projects end to end and chooses the methods",
                "Owns the roadmap: sets own agenda or strategy, founding/lead/first hire, or explicitly independent",
            ],
        ),
        "side_work_restricted": Noul(
            instructions="Does `job.description` say the employee must restrict personal securities trading, outside employment, outside business activities, or side projects, or claim ownership of inventions made outside work?",
            criteria={"true": "The posting states such a restriction or policy",
                      "false": "The posting says nothing like this, or explicitly allows outside work"},
        ),
        # ---- MISSION ----------------------------------------------------------------------
        "industry": Choice(
            instructions="Which sector does the WORK of this role in `job` serve? Judge by the team and subject matter of the role, not only the employer (e.g. a water team at a development bank is water).",
            criteria=industries,
        ),
        "equity_impact": Score(
            instructions="How directly does the work in `job` help underserved communities or advance equity and the public good?",
            criteria=[
                "None: the work serves revenue, ads, or engagement with no public-good angle",
                "Incidental: the company's product has some social benefit, but this role does not touch it",
                "Clear: the role supports a product or program that serves underserved people or the public",
                "Core: the role itself measures or improves equity, access, or public outcomes",
            ],
        ),
        # ---- STABILITY --------------------------------------------------------------------
        "layoff_risk": Score(
            instructions="How durable is this employer and position, judging only from signals in `job` (employer type, size, funding stage, contract terms)?",
            criteria=[
                "High risk: temporary contract, very early-stage startup, or signs of turmoil",
                "Uncertain: small or young company with no durability signals",
                "Durable: established or profitable company, or well-funded late-stage company, permanent role",
                "Very durable: government, public utility, university, or large long-established institution",
            ],
        ),
        "benefits": Score(
            instructions="How strong are the benefits described in `job.description` (health coverage, retirement match or pension, paid time off, parental leave)?",
            criteria=[
                "Not mentioned, or only a generic 'competitive benefits' line",
                "Standard: lists health insurance and retirement or PTO without specifics",
                "Strong: specific generous items, e.g. retirement match, fully paid premiums, 4+ weeks PTO, paid parental leave",
                "Exceptional: pension or very generous match plus several strong specifics",
            ],
        ),
        "workload": Score(
            instructions="How predictable and sustainable is the workload in `job`, based on `job.description`?",
            criteria=[
                "Crunch: long hours, weekends, on-call rotation, or 'hardcore/intense pace' language",
                "Demanding: 'fast-paced', tight deadlines, or occasional after-hours work mentioned",
                "Normal: no signals either way",
                "Sustainable: explicitly promotes work-life balance, no on-call, flexible or limited hours",
            ],
        ),
        # ---- FIT ----------------------------------------------------------------------------
        "role_fit": Score(
            instructions="How well does `candidate` match the core responsibilities and required skills in `job`?",
            criteria=[
                "Unrelated: the role needs a different profession",
                "Adjacent: related field, but most required skills are ones `candidate` lacks",
                "Partial: `candidate` has some of the required skills and experience",
                "Strong: `candidate` has most or all required skills and directly relevant experience",
            ],
        ),
        "mainly_swe": Noul(
            instructions="Is the main job in `job` building and operating production software or ML infrastructure (services, platforms, APIs, model serving, distributed systems), rather than analysis, statistical modeling, research, or data-driven decision support?",
            criteria={"true": "Mostly production software / ML platform engineering",
                      "false": "Mostly analysis, modeling, research, or analytics"},
        ),
        "seniority": Choice(
            instructions=f"How does the level of `job` compare with `candidate`'s roughly {years} years of experience and education?",
            criteria={
                "too_junior": "Entry-level or junior role, clearly below the candidate's level",
                "match": "A role at the candidate's level",
                "stretch": "One level up (e.g. staff, principal, or manager); a reasonable step",
                "too_senior": "Director or executive, or requires far more years than the candidate has",
            },
        ),
        "hard_requirement_gap": Noul(
            instructions="Does `job` list a REQUIRED qualification (not a 'preferred' or 'nice to have' one) that `candidate` clearly does not have, such as a PhD, a specific license, or years in a specific technology the candidate never used?"
        ),
        "role_family": Choice(
            instructions="Which kind of role is `job`? This decides which version of the resume to send.",
            criteria=families,
        ),
        "contract_or_temp": Noul(instructions="Is `job` a contract, temporary, part-time, or freelance position rather than permanent full-time?"),
        "requires_clearance": Noul(instructions="Does `job` require an active security clearance?"),
        "non_us": Noul(
            instructions=f"Is `job` located outside {country} with no option to work from {country}?",
            criteria={"true": f"Role is based in another country and work from {country} is not offered",
                      "false": f"Role is in {country}, or remote work from {country} is allowed"},
        ),
    }


def judge_job(client: TypeSafeClient, job: dict, cand: dict, questions: dict) -> dict:
    state = {
        "candidate": cand,
        "job": {
            "title": job["title"], "company": job["company"], "location": job["location"],
            "salary": job.get("salary_text") or "not listed",
            "description": job["description"][:DESC_CHARS],
        },
    }
    res = client.system_one(state=state, questions=questions)
    out = {"model": res.model}
    for k, a in res.scores.items():
        out[k] = {"score": a.score, "confidence": a.confidence}
    for k, a in res.choices.items():
        out[k] = {"choice": a.choice, "confidence": a.confidence, "probs": dict(a.probabilities)}
    for k, a in res.nouls.items():
        out[k] = {"p": a.noul}
    return out


def judge_many(jobs: list[dict], profile: dict, cfg: dict) -> dict[str, dict]:
    cand, questions = candidate_summary(profile), build_questions(cfg, profile)
    results = {}
    with TypeSafeClient(model=cfg["models"]["judge"]) as client:
        def one(job):
            try:
                return job["id"], judge_job(client, job, cand, questions)
            except Exception as e:
                log.warning("judge failed %s: %s", job["id"], e)
                return job["id"], None
        with ThreadPoolExecutor(8) as ex:
            for jid, j in ex.map(one, jobs):
                if j:
                    results[jid] = j
    return results


def comp_value(salary_max: int | None, target: int) -> float:
    if salary_max is None:
        return 0.5  # unknown: neutral
    return max(0.0, min(1.0, 0.4 + (salary_max - target) / 100_000))


def features(j: dict, job: dict, cfg: dict) -> dict[str, float]:
    """Each value in 0..1, higher = better for you. These are what the weights in config.yaml multiply."""
    s = lambda k: j[k]["score"] / SCORE_MAX
    industry = j["industry"]["choice"]
    restricted_prior = cfg.get("side_work", {}).get("restricted_industries", {}).get(industry, 0.0)
    return {
        "arrangement": cfg["arrangement_value"][j["arrangement"]["choice"]],
        "autonomy": s("autonomy"),
        "side_ventures": 1.0 - max(j["side_work_restricted"]["p"], restricted_prior),
        "industry": cfg["industries"].get(industry, {}).get("value", cfg.get("other_industry_value", 0.1)),
        "equity": s("equity_impact"),
        "layoff_safety": s("layoff_risk"),
        "benefits": s("benefits"),
        "workload": s("workload"),
        "role_fit": s("role_fit"),
        "comp": comp_value(job.get("salary_max"), cfg["hard_filters"].get("salary_target", cfg["hard_filters"]["salary_floor"])),
    }


def dealbreaker(j: dict, cfg: dict, title: str = "") -> str | None:
    db = cfg["dealbreakers"]
    if db.get("mainly_swe") and "software engineer" in title.lower():
        return "mainly_swe"
    if db.get("onsite_3plus_days") and j["arrangement"]["choice"] == "onsite_heavy" and j["arrangement"]["confidence"] >= 0.3:
        return "onsite_3plus_days"
    if db.get("mainly_swe") and j["mainly_swe"]["p"] >= db.get("mainly_swe_threshold", 0.5):
        return "mainly_swe"
    if j["role_fit"]["score"] / SCORE_MAX < cfg["hard_filters"]["min_role_fit"]:
        return "role_fit"
    return None


def composite(j: dict, job: dict, cfg: dict) -> tuple[float, dict]:
    """Policy lives here, not in the model. Returns (value, breakdown)."""
    feats = features(j, job, cfg)
    w = cfg["weights"]
    value = sum(w[k] * feats[k] for k in w) / sum(w.values())
    flags = []
    for k, mult in cfg["penalties"].items():
        if j[k]["p"] > 0.6:
            value *= mult
            flags.append(k)
    value *= cfg["seniority_multiplier"][j["seniority"]["choice"]]
    reject = dealbreaker(j, cfg, job.get("title", ""))
    if reject:
        value, flags = 0.0, flags + [f"DEALBREAKER:{reject}"]
    low_conf = [k for k in ("autonomy", "equity_impact", "role_fit", "arrangement") if j[k]["confidence"] < 0.35]
    return round(value, 4), {"parts": {k: round(v, 2) for k, v in feats.items()}, "flags": flags, "low_confidence": low_conf}
