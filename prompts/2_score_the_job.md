# Prompt 2: score the job before you spend time on it (optional)

This is the agent's ranking method done by hand. The model answers narrow questions about the posting, each with a fixed set of answers, instead of the unanswerable "is this a good job for me?" **You** decide what matters.

Fill in **WHAT I VALUE** first. Example: *"Remote matters most, I want climate or health work, my floor is $110k, I won't do on-call."*

---

```
Answer narrow questions about the JOB below. Use only what the posting says. If it doesn't say, answer
"not stated" rather than guessing. Give each answer with a one-line quote or reason from the posting.

1. ARRANGEMENT: remote anywhere / remote but restricted (states, region, time zone, travel) /
   hybrid 1-2 days / onsite 3+ days / not stated
2. AUTONOMY (0-3): 0 ticket-taker, 1 owns recurring deliverables, 2 owns projects end to end and picks
   methods, 3 sets own agenda or strategy
3. ROLE FIT vs MY FACTS (0-3): 0 different profession, 1 adjacent but I lack most required skills,
   2 I have some, 3 I have most or all. List each REQUIRED qualification as: have it / closest real
   experience I have / missing.
4. SENIORITY vs my years: too junior / match / one level up / far too senior
5. INDUSTRY the work itself serves (judge the team's subject, not just the employer)
6. PAY: posted range, or "not stated". Below my floor?
7. STABILITY (0-3): 0 temp or very early startup, 1 small/young, 2 established, 3 government, utility,
   university, or long-established institution
8. BENEFITS (0-3): 0 not mentioned, 1 standard, 2 specific and generous, 3 exceptional
9. WORKLOAD (0-3): 0 crunch or on-call, 1 "fast-paced"/deadlines, 2 no signals, 3 explicitly sustainable
10. YES/NO with probability: restricts side work or personal trading? contract or temporary? requires
    security clearance? mainly building production software rather than analysis? a hard requirement I
    clearly don't meet?

Then, using WHAT I VALUE, give a verdict: APPLY / MAYBE / SKIP, with the two biggest reasons and the
one question I should ask the recruiter.

WHAT I VALUE:
[YOUR PRIORITIES, DEALBREAKERS, PAY FLOOR]

MY MASTER FACTS:
[PASTE]

JOB:
[PASTE THE FULL POSTING, INCLUDING BENEFITS AND PAY SECTIONS]
```
