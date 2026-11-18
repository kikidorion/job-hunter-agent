# Telegram setup

Telegram is optional but makes the agent much more useful:
- **The digest:** after each run, the roles with documents ready and the ones worth a look.
- **Questions:** when a strong role asks for something your profile doesn't show, the agent asks you. For example: "Have you used dbt, even in a side project?"
- **Your answers** are saved and used in every later document.

## 1. Create a bot (2 minutes)

1. In Telegram, open a chat with **@BotFather** (the official one, with a blue check).
2. Send `/newbot`.
3. Choose a display name (e.g. `My Job Hunter`) and a username ending in `bot` (e.g. `jordan_jobhunter_bot`).
4. BotFather replies with a **token** like `123456789:AAH...`. Treat it like a password.

**Use a new bot just for this agent.** If another program reads the same bot's messages, the two steal each other's messages and your answers go missing.

## 2. Connect it

```bash
.venv/bin/python -m jobhunt telegram-setup
```
1. Paste the token when asked, or put `TELEGRAM_BOT_TOKEN=...` in `.env` first.
2. Open your new bot in Telegram, press **Start**, and send it any message.
3. The command picks up your chat id, saves `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to `.env`, and sends you a test message.

Run `python -m jobhunt check` to confirm it shows **ok**.

## 3. Answering questions

Questions look like this:

> ❓ Job Hunter needs input
>
> For Acme (Senior Data Analyst): Have you built dashboards in Looker, even in a side project?
>
> ↩️ Reply to THIS message with your answer.

**Swipe left on the message (or long-press → Reply) and answer.** Replies only count when they are replies to that question. Answers are collected at the start of the next run.

- Answer with facts you'd defend in an interview: "Yes, 2 years at Denver Public Health", or "No".
- Answers about form defaults (salary, start date, sponsorship) go into every `APPLY.md`.
- Answers about experience become facts the writer may use from then on.
- The agent never asks the same question twice. Pending and past questions are in `data/jobs.db`, and saved answers are in `data/answers.yaml`, which you can edit by hand.

## Privacy

- Only your chat is accepted: replies from any other chat are ignored.
- The bot token and chat id live only in your `.env`, which git ignores.
- The digest contains job titles, companies and links, never your documents.
