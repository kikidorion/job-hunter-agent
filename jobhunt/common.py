import logging
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
QUEUE = ROOT / "queue"
LOGS = ROOT / "logs"

log = logging.getLogger("jobhunt")


def setup_logging() -> None:
    LOGS.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOGS / "jobhunt.log"), logging.StreamHandler()],
    )
    for noisy in ("httpx", "httpcore", "httpx2"):  # their INFO lines print full URLs incl. the bot token
        logging.getLogger(noisy).setLevel(logging.WARNING)


def load_env() -> None:
    """Read .env into the environment. Real environment variables win; commented lines are ignored."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if val and key not in os.environ:
            os.environ[key] = val


def set_env_value(key: str, value: str) -> None:
    """Write or replace KEY=value in .env (used by telegram-setup)."""
    path = ROOT / ".env"
    lines = path.read_text().splitlines() if path.exists() else []
    lines = [ln for ln in lines if not ln.strip().startswith(f"{key}=")] + [f"{key}={value}"]
    path.write_text("\n".join(lines) + "\n")


def _require(name: str) -> Path:
    path = ROOT / name
    if not path.exists():
        raise SystemExit(f"{name} not found. Copy {name.replace('.yaml', '.example.yaml')} to {name} and edit it "
                         "(see docs/CUSTOMIZE.md).")
    return path


def load_config() -> dict:
    return yaml.safe_load(_require("config.yaml").read_text())


def load_profile() -> dict:
    """profile.yaml merged with answers you gave over Telegram (data/answers.yaml)."""
    profile = yaml.safe_load(_require("profile.yaml").read_text())
    answers_path = DATA / "answers.yaml"
    if answers_path.exists():
        answers = yaml.safe_load(answers_path.read_text()) or {}
        for key, val in answers.get("application_defaults", {}).items():
            profile.setdefault("application_defaults", {})[key] = val
        profile["extra_facts"] = profile.get("extra_facts", []) + answers.get("extra_facts", [])
    return profile


def save_answer(section: str, key: str | None, value) -> None:
    DATA.mkdir(exist_ok=True)
    answers_path = DATA / "answers.yaml"
    answers = yaml.safe_load(answers_path.read_text()) if answers_path.exists() else {}
    answers = answers or {}
    if key is None:
        answers.setdefault(section, []).append(value)
    else:
        answers.setdefault(section, {})[key] = value
    answers_path.write_text(yaml.safe_dump(answers, sort_keys=False, allow_unicode=True))


def kw_pattern(words: list[str]) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(w) for w in words) + r")(?![A-Za-z])", re.I)


def title_ok(title: str, cfg: dict) -> bool:
    """Cheap title gate: must contain a wanted keyword and no excluded one."""
    return bool(kw_pattern(cfg["title_keywords"]).search(title)) and not kw_pattern(cfg["exclude_title_keywords"]).search(title)


def _matches(rule: dict | None, family: str | None, industry: str | None) -> bool:
    return bool(rule) and (family in rule.get("families", []) or industry in rule.get("industries", []))


def experience_for(profile: dict, family: str | None = None, industry: str | None = None) -> list[dict]:
    """show_for entries appear only when the job matches; a matching highlight_for becomes highlight: true."""
    out = []
    for e in profile.get("experience", []):
        if e.get("show_for") and not _matches(e["show_for"], family, industry):
            continue
        entry = {k: v for k, v in e.items() if k not in ("show_for", "highlight_for")}
        if _matches(e.get("highlight_for"), family, industry):
            entry["highlight"] = True
        out.append(entry)
    return out


def writer_profile(profile: dict, family: str | None = None, industry: str | None = None) -> dict:
    """Profile as the writer and verifier see it: excluded projects removed, no form answers or judge notes."""
    p = {k: v for k, v in profile.items() if k not in ("application_defaults", "judge_summary")}
    p["projects"] = [pr for pr in profile.get("projects", []) if pr.get("include", True)]
    p["experience"] = experience_for(profile, family, industry)
    return p
