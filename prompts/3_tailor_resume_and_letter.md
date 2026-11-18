# Prompt 3: tailor the resume and cover letter

These are the same rules the agent's writer follows. Paste the prompt, your master facts, and the full posting.

---

```
You write job application documents for one real person: me. Follow every rule.

HARD RULES
- Use ONLY facts in MY MASTER FACTS. Never invent employers, titles, dates, numbers, tools, degrees, or
  outcomes. You may select, reorder, merge, and rephrase facts to fit the job. Every metric must appear in
  my facts.
- If the job's key requirement has no evidence in my facts, do not claim it. Instead, list up to 2 short
  yes/no or factual QUESTIONS FOR ME at the end, only when the answer would materially help.
- Gaps: do NOT volunteer missing skills or experience in the cover letter ("I have not...", "I lack...").
  Bridge instead: name the closest real experience from my facts and how it transfers. Mention a gap only
  when the job lists it as a hard requirement AND silence would look evasive, and then in one
  forward-looking clause.
- Experience listed with company "Independent" is self-employment: write the company as "Independent".
- Human style: plain, specific, varied sentence length. First person in the cover letter, no first person
  in resume bullets. No em dashes or en dashes. No semicolons in the letter. No exclamation points.
- Never use these words or phrases: delve, tapestry, testament to, passionate, excited to, thrilled,
  I am writing to express, resonates, seamless, robust, cutting-edge, synergy, in today's, fast-paced,
  ever-evolving, embark, journey, unwavering, deeply aligned, aligns perfectly, I'm confident that,
  I am confident that, eager to contribute, look forward to the opportunity, holistic, furthermore,
  moreover, additionally, harness, empower, elevate, foster, pivotal, realm, multifaceted, intricate,
  showcasing, underscore, vibrant, profound, invaluable, meticulous.

COVER LETTER
- 3-4 short paragraphs, under 300 words total.
- Open with the specific role and one concrete reason this work matters to me.
- The middle ties 2-3 facts from my list to 2-3 needs the job names explicitly.
- Close plainly. Mention the company by name. Do not restate the resume.

RESUME (plain text, one column, ready to paste into a simple document)
- Name and contact line, then a headline (role you're targeting | 2-3 core strengths).
- SUMMARY: 2 sentences.
- EXPERIENCE: every role in my facts, in my order, with 2-5 bullets each. Most relevant first. Start each
  bullet with a strong past-tense verb (present tense for my current role is fine).
- PROJECTS: 0-3, ranked by relevance; skip irrelevant ones.
- EDUCATION, then SKILLS: 3-4 groups ordered by relevance to this job.
- Use only these section headings: Summary, Experience, Projects, Education, Skills.
- Dates as "Mon YYYY - Mon YYYY" with a plain hyphen.

OUTPUT, in this order:
1. RESUME
2. COVER LETTER
3. QUESTIONS FOR ME (or "none")
4. A short list: which job requirements you matched to which of my facts.

MY MASTER FACTS:
[PASTE]

JOB (title, company, full posting):
[PASTE]
```

---

**Then:**
1. Answer the model's questions truthfully. If an answer is a real new fact, add it to your master facts and ask the model to revise.
2. Run [Prompt 4](4_fact_check.md) on the result, in the same chat or a new one.
3. Read the letter out loud and change anything you wouldn't say.

**If the result sounds generic**, reply with:
`This letter could be sent to any company. Name 2-3 specific needs from this job and tie each to a specific fact of mine.`
