# Prompt 4: fact-check every claim

The agent checks each bullet and paragraph separately, because a model reviewing a whole document tends to skim past the one invented number. This prompt makes the model go line by line.

**For the best results, use a different model or a fresh chat** from the one that wrote the documents.

---

```
You are a strict fact-checker. Check the DOCUMENTS against MY MASTER FACTS, one line at a time.

For EVERY resume bullet, the resume summary, and EVERY cover letter sentence:
- Quote it.
- Verdict: SUPPORTED, or NOT SUPPORTED.
  SUPPORTED means every fact about me in it (employers, titles, dates, numbers, tools, degrees,
  accomplishments, team sizes, scope) is stated in or directly implied by my facts. Wording may differ.
  Statements about the employer may come from the JOB posting.
- If NOT SUPPORTED: name the exact unsupported part, and give a rewrite that uses only my facts, or say
  "delete".

Also check:
- Any of these words or phrases: delve, tapestry, testament to, passionate, excited to, thrilled,
  resonates, seamless, robust, cutting-edge, synergy, fast-paced, embark, journey, unwavering,
  aligns perfectly, eager to contribute, holistic, furthermore, moreover, harness, empower, elevate,
  foster, pivotal, realm, multifaceted, intricate, showcasing, underscore, vibrant, profound,
  invaluable, meticulous. Also flag any em dashes or en dashes.
- GENERIC TEST: could this cover letter be sent to a different company with only the name changed?
  Answer yes/no and why.
- Does the letter volunteer a missing skill ("I have not", "I lack", "although I don't")? Quote it.

End with a count: X supported, Y not supported, and the corrected lines only.

MY MASTER FACTS:
[PASTE]

JOB:
[PASTE]

DOCUMENTS:
[PASTE THE RESUME AND COVER LETTER]
```

---

Fix or delete every NOT SUPPORTED line before sending. If a flagged line is actually true, add that fact to your master facts so it's supported next time.
