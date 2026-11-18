# Setup

About 20 minutes. You need Python 3.11+, Google Chrome (or Chromium/Edge), and two API keys.

## 1. Install

```bash
git clone https://github.com/kikidorion/job-hunter-agent.git
cd job-hunter-agent
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt          # Windows: .venv\Scripts\pip install -r requirements.txt
cp config.example.yaml config.yaml
cp profile.example.yaml profile.yaml
cp .env.example .env
```

`config.yaml`, `profile.yaml`, `.env`, `data/`, and `queue/` are git-ignored, so your personal data never gets committed.

## 2. API keys (in `.env`)

| Key | What it does | Where |
|---|---|---|
| `TYPESAFE_API_KEY` | Jev: scores every posting and fact-checks every document | [console.typesafe.ai](https://console.typesafe.ai) |
| `OPENROUTER_API_KEY` | The writer that drafts resumes and letters (any model; set in `config.yaml`) | [openrouter.ai/keys](https://openrouter.ai/keys), add a few dollars of credit |

If OpenRouter runs out of credit, the agent keeps scoring and tells you on Telegram. Documents resume once you add credit.

## 3. Your profile and values

Fill in `profile.yaml` with your real facts and `config.yaml` with what you care about. This step matters most, and **[CUSTOMIZE.md](CUSTOMIZE.md)** walks through it.

## 4. Check, then run

```bash
.venv/bin/python -m jobhunt check     # lists anything missing, with the fix
.venv/bin/python -m jobhunt run
```

The first run scores every open posting on your boards, so it takes longer and costs more than later runs, which only see new postings. To start small, list only a few boards in `sources`.

Results:
- `queue/index.html`: the ranked dashboard
- `queue/<date>_<company>_<role>/`: the resume and cover letter as PDF and DOCX, plus `APPLY.md`
- `logs/jobhunt.log`: what happened

## 5. Telegram (optional, recommended)

Telegram gives you the digest on your phone, and lets you answer the agent's questions with a reply. → **[TELEGRAM.md](TELEGRAM.md)**

## 6. Schedule it

**macOS:** runs at 7:00 and 16:00. Edit `HOURS` in the script to change the times.
```bash
bash scripts/install_schedule_mac.sh
```

**Linux:** run `crontab -e` and add:
```
0 7,16 * * * /full/path/to/job-hunter-agent/scripts/run.sh
```

**Windows:** in Task Scheduler, create a task that runs
`C:\path\to\job-hunter-agent\.venv\Scripts\python.exe -m jobhunt run`, with *Start in* set to the repo folder.

`scripts/run.sh` waits for the network after the computer wakes, and uses a lock so runs never overlap. Logs go to `logs/scheduler.log`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `config.yaml not found` | Copy the `.example.yaml` files (step 1) |
| `Chrome or Chromium is needed` | Install Chrome, or set `CHROME_PATH=` in `.env` to its full path |
| No roles in tier A | Lower `tiers.A`, widen `title_keywords`, or add boards. See `queue/index.html` for tier B |
| Good roles score low | Label them with `add yes URL`, then follow the calibration steps in [CUSTOMIZE.md](CUSTOMIZE.md#4-calibrate-on-your-own-taste) |
| `source ... failed` in the log | That board token is wrong or the company moved boards. Remove it |
