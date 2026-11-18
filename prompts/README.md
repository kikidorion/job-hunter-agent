# Prompts only: use the method without installing anything

Each prompt below is ready to copy into ChatGPT, Claude, or Gemini. They follow the same rules the agent uses: facts only from your own list, gaps bridged rather than confessed, no AI tells, and every claim checked.

Use them in order, in **one chat per job**, so the job description stays in context:

| Step | Prompt | What you get |
|---|---|---|
| 1. Once | [1_build_master_facts.md](1_build_master_facts.md) | Your **master facts** file: every true, specific fact about your work, in one place. Reuse it for every job. |
| 2. Per job, optional | [2_score_the_job.md](2_score_the_job.md) | A scored read on the posting: remote, fit, red flags, seniority. Decide if it's worth applying. |
| 3. Per job | [3_tailor_resume_and_letter.md](3_tailor_resume_and_letter.md) | A tailored resume and cover letter built only from your facts, plus questions about any gaps. |
| 4. Per job | [4_fact_check.md](4_fact_check.md) | Every bullet and sentence checked against your facts. Fix anything flagged. |
| 5. Before you send | [5_ats_export_checklist.md](5_ats_export_checklist.md) | How to format and export so applicant tracking systems read it correctly and the file carries no tool metadata. |

## Three rules that make this work

1. **Your master facts are the only source.** The model may choose, reorder, and rephrase them, never add to them. Put metrics in the facts, because it can't invent any.
2. **Check before you send.** Step 4 is not optional. Models invent things quietly, especially numbers and tools.
3. **Read it out loud.** If a sentence isn't something you'd say, change it. These prompts get you a strong draft, not a finished one.

Want this automated, with the job search, ranking and Telegram alerts included? See the main [README](../README.md).
