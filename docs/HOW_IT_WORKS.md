# How it works

## 1. Collect and prefilter (free)

Sources are public job-board APIs only, with no logins and no scraping behind a sign-in.

A posting is dropped before any API call when:
- its title misses `title_keywords` or hits `exclude_title_keywords`
- its posted max pay is below `salary_floor`
- it's an aggregator listing older than `max_posting_age_days`
- it has no real description

Pay is parsed in code, never by the model: yearly ranges, "$120k", and hourly rates × 2080 hours.

## 2. Judge with Jev (one call per posting)

[TypeSafe](https://typesafe.ai) System One (`jev-latest`) answers **16 narrow questions in parallel**. Each answer comes back typed:

| Type | Returns | Used for |
|---|---|---|
| `Score` | 0–3 against four written levels, plus a confidence | autonomy, impact, layoff risk, benefits, workload, role fit |
| `Choice` | one option from a fixed list, with probabilities | work arrangement, industry (your list), seniority, role family (your list) |
| `Noul` | a probability that a yes/no statement is true | side-work restrictions, mainly software engineering, hard requirement gap, contract, clearance, outside your country |

Every level and option is spelled out in plain language in `jobhunt/judge.py`. Jev isn't asked "is this a good job?", which no model can answer for you. It's asked small factual questions it can answer well.

The raw answers are stored per job. **All policy lives in code and `config.yaml`**, which is why changing a weight costs nothing.

## 3. Score in code

```
value = Σ weight_i × feature_i / Σ weight_i         (features are 0..1, see CUSTOMIZE.md)
value ×= penalty for each flag whose probability > 0.6
value ×= seniority multiplier
value  = 0 if a dealbreaker hits
```

The tier comes from the value, and low-confidence judgments are listed in each `APPLY.md` so you know which parts to double-check.

**Calibration.** `add yes|no URL` labels real postings, and `calibrate` reports the AUC of your weights against those labels. The author's first hand-set weights scored **AUC 0.31**, worse than a coin flip, because what she said she wanted differed from what she picked. Re-weighting from her labels brought it to **0.88**.

## 4. Write: facts only, gaps bridged, no AI tells

The writer, any OpenRouter model, gets your profile filtered for the job (`show_for` / `highlight_for`) and the posting. It follows the rules in `jobhunt/writer.py`. The core ones:

- **Use only facts in the profile.** Never invent employers, titles, dates, numbers, tools, degrees, or outcomes. Every metric must appear in the profile.
- **Missing evidence becomes a question, not a claim.** If the job's key requirement has no evidence, the writer adds up to 2 short questions for you. They go to Telegram.
- **Bridge gaps, don't confess them.** The cover letter never volunteers a missing skill ("I have not...", "I lack..."). It names your closest real experience and how it transfers. A gap is mentioned only when the job lists it as a hard requirement *and* silence would look evasive, and then in one forward-looking clause.
- **Highlighted experience must appear.** An entry marked `highlight` for this job must be named in the letter and tied to the job.
- **Self-employment is labeled honestly:** company "Independent."
- **Human style:**
  - plain, specific sentences of varied length
  - first person in the letter, none in resume bullets
  - no em or en dashes, no semicolons in the letter, no exclamation points
  - a banned-word list of AI tells
- **Letter shape:** 3–4 short paragraphs, under 300 words. It opens with the specific role and one concrete reason the work matters to you, ties 2–3 of your facts to 2–3 named needs of the job, and names the company. It doesn't restate the resume.
- **Resume shape:**
  - headline and a two-sentence summary
  - skill groups ordered by relevance to the job
  - every role, in your order, with its most relevant bullets first, each starting with a past-tense verb
  - 0–3 relevant projects

## 5. Verify every claim (one Jev call per document set)

1. Code scrubs dashes, curly quotes and ellipses, and checks the banned words.
2. Jev checks **each resume bullet, the summary, and each letter paragraph**, in parallel: *is every fact about the candidate stated in or directly implied by the profile?*
3. A separate check asks whether the letter reads like template text that could go to any company.
4. Any failure sends specific feedback to the writer, and it gets **up to 2 revisions**.
5. After that, unsupported resume bullets are **dropped**. An unsupported summary or letter paragraph is **flagged in `APPLY.md`** for you to fix by hand.

## 6. Render ATS-ready files

ATS (applicant tracking system) parsers reward plain structure. Every document gets:

- [x] A single column, with no tables, text boxes, columns, headers or footers holding content
- [x] Standard section headings: Summary, Experience, Projects, Education, Skills
- [x] Selectable text in the PDF, not an image, printed by headless Chrome
- [x] A standard font (Georgia) and Letter size with normal margins
- [x] Plain hyphens in date ranges ("Jun 2021 - Present") and straight quotes
- [x] Metadata with only your name: PDF author, creator and producer are all set to you, and DOCX author and last-modified-by are you too. No "python-docx," no generator tags, no XMP block.
- [x] DOCX created and modified dates set to now (the default template would otherwise say 2013)
- [x] Both PDF and DOCX, since some portals parse one better than the other

Each role folder also keeps `doc.json`, the structured draft. That lets you re-render after fixing a typo without paying for a new draft.
