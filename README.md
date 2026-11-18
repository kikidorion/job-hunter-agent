# Job Hunter Agent

A personal job-search agent that runs on your own computer. Twice a day it:

1. **Finds** new postings on public company job boards (Greenhouse, Lever, Ashby, Workday, Oracle) and remote-job sites.
2. **Ranks them by what *you* value.** Remote work, industry, pay, stability and fit are each scored with typed AI judgments, then weighted by you.
3. **Drafts a tailored resume and cover letter** for the best matches. They're built only from facts you've written down, fact-checked sentence by sentence, and saved as clean, ATS-ready PDF and DOCX files.
4. **Messages you on Telegram** with the shortlist. It asks you questions when a posting needs a fact it doesn't have.

**It never applies for you.** You read every document and click apply yourself.

```
fetch ─► prefilter (code) ─► Jev judgments (16 typed questions) ─► your weights ─► tiers
                                                                          │
                     tier A ─► writer (facts only) ─► scrub AI tells ─► verify every claim ─► PDF + DOCX + APPLY.md
                                                                          │
                                                   Telegram digest + questions ◄┘
```

## Why it ranks better than keyword matching

Most job alerts match keywords. This agent asks [TypeSafe](https://typesafe.ai)'s **Jev** model narrow, typed questions about each posting:
- How many office days are required? (one of a fixed set of answers)
- How much ownership does the role have? (a 0–3 score)
- Is it really a software engineering job? (a probability)
- Which industry does the work serve? (from *your* list)

Code then combines the answers with your weights, so you control the policy and the model only supplies judgments. Answers are cached, so re-weighting is instant and free.

You can **check the ranking against your own taste.** Label real postings yes or no, and `calibrate` reports how often your yes roles outrank your no roles (AUC). The author tuned her own setup from **AUC 0.31 to 0.88** this way. → [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)

## Documents that sound like you and survive an ATS

- **Facts only.** The writer may select and rephrase facts from your `profile.yaml`, never invent them. A second model checks every bullet and paragraph against that file. It drops unsupported resume bullets and flags unsupported letter sentences for your review.
- **Gaps get bridged, not confessed.** The letter never volunteers a missing skill. It names your closest real experience and how it transfers. When a key requirement has no evidence at all, the agent asks *you* on Telegram instead of guessing.
- **No AI tells.** Em and en dashes and curly quotes are scrubbed, along with a list of overused AI words ("delve," "passionate," "tapestry"...). A generic-letter check forces a rewrite when the letter could have been sent to any company.
- **ATS-ready files.** Single column, standard section headings, real selectable text, and a standard font. File metadata carries only your name, with no generator or producer tags. DOCX dates are set to now.

## Quick start

```bash
git clone https://github.com/kikidorion/job-hunter-agent.git && cd job-hunter-agent
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp config.example.yaml config.yaml && cp profile.example.yaml profile.yaml && cp .env.example .env
# edit profile.yaml (your facts), config.yaml (your values), .env (your keys)
.venv/bin/python -m jobhunt check
.venv/bin/python -m jobhunt run
```

The full walkthrough covers keys, Chrome, scheduling, and Windows, Linux and Mac → **[docs/SETUP.md](docs/SETUP.md)**

| Guide | What's in it |
|---|---|
| [SETUP.md](docs/SETUP.md) | Install, API keys, first run, scheduling |
| [CUSTOMIZE.md](docs/CUSTOMIZE.md) | Your profile, your values, industries, role types, job sources |
| [TELEGRAM.md](docs/TELEGRAM.md) | Create a bot, connect it, answer the agent's questions |
| [HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) | Ranking with Jev, calibration, writer rules, ATS checklist |

## What it costs

- **TypeSafe (scoring and fact-checking):** one API call per new posting that passes the free code filters, plus one per document set. See typesafe.ai for pricing.
- **OpenRouter (writing):** about $0.04 per resume and cover letter pair with the default model. `max_docs_per_run` caps spending.
- Everything else is free and runs locally. Your profile, answers and documents never leave your machine except in those API calls.

## Commands

```
python -m jobhunt run                     fetch, score, write documents, send the digest
python -m jobhunt check                   verify config, profile, keys, Chrome, Telegram
python -m jobhunt add yes|no|check URL    score a posting you found (yes/no also trains calibration)
python -m jobhunt rescore                 re-rank after editing weights (free)
python -m jobhunt calibrate               how well your weights match your yes/no labels
python -m jobhunt applied|skip ID         track what you did
python -m jobhunt telegram-setup          connect Telegram
```
Open `queue/index.html` for a ranked dashboard. Each role gets a folder with the documents and an `APPLY.md`, which holds the link, the score breakdown, and your saved form answers.

## License

MIT. Built by [Kiara Dorion](https://linkedin.com/in/kiara-dorion).
