# Make it yours

Two files decide everything:
- **`profile.yaml`**: who you are. These are the only facts documents may use.
- **`config.yaml`**: what you want and where to look.

## 1. `profile.yaml`: your master facts

The writer may only **select, reorder, and rephrase** what is in this file. A verifier then checks every resume bullet and cover letter paragraph against it. So the rule is simple:

> Write every true, specific fact down once: numbers, tools, outcomes. Never write anything you would not defend in an interview.

**Tips**
- **Use metrics** where you have them. The writer can't invent numbers, so the ones you give it are all it will ever use.
- **Use more bullets than fit on one resume.** Write 4–6 per role. The writer picks the most relevant ones for each job.
- **Set `years_experience`.** Jev uses it to label each posting too junior, a match, a stretch, or too senior.
- **`judge_summary` is optional:** one or two lines Jev reads when judging fit. It defaults to your titles and project names.
- **Projects** need `include: true`. Set `include: false` to keep one off every document.
- **`application_defaults`** are your standard form answers: work authorization, salary expectation, start date. They're copied into each `APPLY.md`. Leave them `null`, and the agent asks you once on Telegram.
- **`extra_facts`** collects your Telegram answers automatically, saved in `data/answers.yaml`. Add true facts here yourself too.

### Show the right experience to the right employer

Some experience helps with some employers and distracts others: freelance work, a side business, a creative career. Two keys control it:

```yaml
  - company: Independent
    title: Futures Trader
    show_for: {families: [quant_research], industries: [finance]}     # appears ONLY for these
    highlight_for: {industries: [finance]}                            # letter must name it for these
```
`families` come from `role_families` in `config.yaml`, and `industries` come from `industries`. An entry with no `show_for` always appears.

### Employment gaps

Fill the gap with real work and the timeline stays continuous: contract work, teaching, volunteering, caregiving with a skill you used, a course with a project. Use `company: Independent` for self-employment. The writer is told to write it as "Independent" and never invent an employer.

## 2. `config.yaml`: what you value

### Weights
Ten features, each scored 0–1 per posting. The total score is their weighted average.

| Feature | Measures |
|---|---|
| `role_fit` | your skills vs the posting's requirements |
| `industry` | your `value` for the industry Jev picks |
| `arrangement` | remote / hybrid / onsite, scored by `arrangement_value` |
| `comp` | posted pay vs `salary_target` (unposted pay is neutral) |
| `layoff_safety` | employer durability signals |
| `autonomy` | how much you choose problems and methods |
| `benefits` | how specific and generous the benefits are |
| `workload` | sustainable hours vs crunch |
| `equity` | public-good impact of the work |
| `side_ventures` | freedom to keep outside work (lowered for industries in `side_work.restricted_industries`) |

Weights are relative, and 0 turns a feature off. After editing them, run `python -m jobhunt rescore`. It's free and instant.

### Industries and role families
These are **your categories.** Jev picks one per posting from your list, using each `describe` line.

```yaml
industries:
  water: {describe: "Water utilities, water technology, hydrology, sanitation", value: 1.0}
  music_audio: {describe: "Music, audio, tools for musicians", value: 1.0}
role_families:
  data_analyst: {describe: "Data/business/product analyst, BI, reporting"}
```
- Keep the lists short (5–10) and the descriptions distinct, so Jev can tell them apart.
- `other` is added automatically.
- **Editing these changes the questions Jev is asked**, so run `python -m jobhunt rejudge` afterwards. That re-calls the API for every scored job.

### Dealbreakers vs penalties
- **Dealbreakers** zero out a role.
- **Penalties** multiply its score down, for example `contract_or_temp: 0.9`.

Many people's real picks break their stated dealbreakers, so start with penalties and only escalate when the data agrees. `calibrate` shows you.

### Tiers
- **Tier A** (`tiers.A`) gets documents automatically, up to `max_docs_per_run`.
- **Tier B** appears in the digest only.
- Postings you label `yes` always get documents, whatever their score.

### Title filters
`title_keywords` and `exclude_title_keywords` are free code filters applied before any API call. They're whole-word and case-insensitive. Keep the include list broad; the scoring does the fine sorting.

## 3. Where to look: `sources`

| Source | Config | Find the token |
|---|---|---|
| Greenhouse | `ats.greenhouse: [token]` | `boards.greenhouse.io/<token>`; test at `https://boards-api.greenhouse.io/v1/boards/<token>/jobs` |
| Lever | `ats.lever: [token]` | `jobs.lever.co/<token>` |
| Ashby | `ats.ashby: [token]` | `jobs.ashbyhq.com/<token>` |
| Workday | `workday: [{tenant, wd, site, search}]` | from `https://<tenant>.<wd>.myworkdayjobs.com/<site>` |
| Oracle HCM | `oracle: [{host, site, company, search}]` | from `https://<host>/hcmUI/CandidateExperience/en/sites/<site>/...` |
| Remotive, RemoteOK, Himalayas | `true` / `false` | remote-job aggregators |

**Found a posting somewhere else?** `python -m jobhunt add yes <url>` scores it. Greenhouse, Workday and Oracle links are read through their APIs; other pages are read as plain text.

## 4. Calibrate on your own taste

What you *say* you value and what you actually pick differ. Calibration measures the gap:

1. Label 10–20 real postings, mixing ones you'd apply to and ones you wouldn't:
   `python -m jobhunt add yes <url>`, `python -m jobhunt add no <url>`
2. `python -m jobhunt calibrate` prints the **AUC**: how often your yes roles outrank your no roles. 0.5 is a coin flip, 1.0 is perfect.
3. Read the misranked rows. If your "no" roles score high on a feature, lower that weight. If a dealbreaker hides roles you said yes to, make it a penalty.
4. Run `rescore`, then `calibrate` again. Repeat until the order looks like your taste.

Write down why you set each value in the comments next to it. When your priorities change, you'll know which numbers to move.
