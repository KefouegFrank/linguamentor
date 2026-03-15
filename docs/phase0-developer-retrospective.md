# Phase 0 Developer Retrospective

**Author:** TETSOPGUIM Kefoueg Frank P.  
**Written:** 2026-03-15  
**Context:** Personal retrospective on implementing Phase 0 of LinguaMentor

---

I want to write this while it's still fresh. Phase 0 took longer than I expected and hit more walls than I anticipated. Some of those walls taught me things I won't forget. This is my honest account of what happened.

---

## What Phase 0 Was Actually About

On paper, Phase 0 is two validation gates: writing evaluation accuracy (Pearson ≥ 0.85) and ASR accuracy (WER < 10%). Clean requirements, measurable outcomes. I went in thinking this would be the straightforward part before the real product work in Phase 1.

I was wrong.

Phase 0 forced me to build a complete offline ML evaluation pipeline from scratch, integrate with three different AI providers, debug silent failures at the database layer, discover a fundamental bias problem in the AI scoring that the primary gate didn't even catch, and make a dozen judgment calls that the PRD didn't have answers for.

By the end of it I understood something I hadn't fully grasped at the start: Phase 0 isn't preliminary work. It's the foundation that determines whether LinguaMentor can make its core product claim — that AI scores essays as accurately as a certified human examiner. Everything in Phase 1 and beyond is built on that claim. If Phase 0 is weak, the whole product is.

---

## The Calibration Pipeline — What I Built and Why

The pipeline has five stages: fetch essays, build an 8-layer prompt, call the AI provider, validate the response schema, store the result. That sounds simple written out. Building it was not.

### The 8-layer prompt

The PRD specified a layered prompt architecture but didn't define what each layer should contain or how they should interact. I had to work that out from the calibration requirements and the IELTS rubric specifications.

Layer 1 establishes identity. Layer 2 sets hard policy constraints. Layer 3 sets the examiner persona. Layer 4 gives the task instruction. Layer 5 injects the rubric. Layer 6 provides user context. Layer 7 provides session context. Layer 8 is the actual essay.

The reason for this ordering is that earlier layers set constraints that later layers cannot override. User input — the essay — is always last and can never modify the rubric or the scoring policy. This matters because without strict layer ordering, a manipulative essay could potentially shift the model's scoring behaviour mid-evaluation.

I also added a calibration mode flag that activates at Layer 4. In calibration mode, the model is told explicitly that its scores will be compared against certified human examiners and to prioritise precision over speed. This produced noticeably more careful scoring than the default mode.

### The AI provider abstraction

Nothing calls an LLM provider directly in this codebase. Everything goes through `AIProviderBase`. I built OpenAI, Anthropic, Gemini, and Groq implementations behind that interface.

The reason I insisted on this abstraction even at Phase 0 — when I only needed one provider to work — is that I watched myself switch providers three times during this phase alone. Started with the deprecated `google.generativeai` package (which didn't work), then tried Gemini 2.0 Flash (wrong API version for my key), then switched to Groq (hit daily token limits), then ended up using Groq successfully after fixing the rate limiting. If I had been calling the SDK directly in the pipeline, each of those switches would have required touching multiple files. With the abstraction, I changed one function.

In production, this same abstraction is how we'll route high-stakes essay scoring to GPT-4o while keeping the calibration pipeline on cheaper models.

---

## The Bugs That Took Longest to Find

### The asyncpg UUID binding issue

This one cost me most of a day.

The `fetch_pending_essays` function was returning zero essays on every run. The database had the essays. The query was correct. The WHERE clause was right. But the pipeline consistently reported "Found 0 essays pending."

I ruled out the obvious things first: checked that `grading_complete = TRUE`, verified the exam type filter, confirmed the database had data. All fine.

The actual problem was subtle: passing a UUID as a Python string with a `$N::uuid` cast inside a subquery causes asyncpg to silently mishandle the parameter binding on Windows. The subquery evaluates to NULL for every row, which means `NOT IN (NULL)` evaluates to NULL for every row, which filters everything out. No error raised. Zero rows returned. The query succeeds from asyncpg's perspective.

The fix was to split the subquery into two separate flat queries and do the exclusion in Python using a set lookup. This completely bypasses the problematic parameter binding pattern. I then applied the same fix everywhere in the codebase that passed UUID strings with inline casts.

The lesson: asyncpg on Windows has parameter binding quirks with UUID types inside subqueries. Always pass `uuid.UUID(str_id)` as the Python value, never a string with a `::uuid` cast.

### The missing import that scored zero essays

After fixing the UUID issue, the pipeline found essays correctly but scored zero. Every essay failed with `name 'RubricScores' is not defined`. 

`RubricScores` was used inside `MockProvider` but the import at the top of `ai_provider.py` only imported `AIEvaluationResponse`. One word. Half a day of debugging the UUID issue had conditioned me to look for complex database problems, so I initially looked in the wrong place.

The lesson: always read the error message first. The actual error was in the first line of the stack trace, not buried somewhere deep.

### The Gemini 404 — deprecated SDK

Switched to Gemini 1.5 Flash because Google offered a free tier. Installed `google-generativeai`, implemented `GeminiProvider`, everything looked right. Every call returned `404 models/gemini-1.5-flash is not found`.

The `google.generativeai` package had been fully deprecated. Google had been sending deprecation warnings in every API call header but not in the response body, so my error handling wasn't surfacing them clearly. The correct package is `google-genai` with a completely different SDK interface.

The larger lesson here is about reading deprecation warnings seriously. I had seen the `FutureWarning` about the deprecated package in the logs and moved past it because the API calls appeared to be going through. They weren't — they were hitting the wrong API version entirely.

---

## The Bias Problem — The Most Important Finding

This is what I most want to document because it nearly slipped through.

The calibration run passed the Pearson gate with r=0.9338. Every category cleared 0.85. The Go/No-Go verdict was PASSED. I was ready to move on.

Then I ran the tuning analysis endpoint and looked at the actual numbers:

```
Task Response:      AI = 7.646  Human = 6.604  Bias = +1.042
Coherence:          AI = 7.917  Human = 6.500  Bias = +1.417
Lexical Resource:   AI = 7.562  Human = 6.531  Bias = +1.031
Grammatical Range:  AI = 7.583  Human = 6.344  Bias = +1.240
Overall:            AI = 7.688  Human = 6.552  Bias = +1.135
```

The AI was scoring every single category approximately one full band above the human examiners. A Band 6.5 essay was being scored as Band 7.5. Pearson correlation measures whether scores move in the same direction — it doesn't catch systematic overestimation. We had passed the gate while having a fundamental accuracy problem that would mislead every learner who used the product.

The root cause is RLHF. Language models trained with reinforcement learning from human feedback develop a positive bias because human raters in their training pipeline preferred responses that were encouraging and generous. That bias bleeds into scoring tasks. LLaMA 3.3 70B was being a generous examiner rather than a strict one.

The fix was a Layer 4 prompt modification — explicit anti-inflation anchors:

- Remind the model that most IELTS test-takers score between Band 5.0 and 7.0
- Tell it to award the LOWER band when uncertain between two adjacent bands
- Explicitly prohibit generous rounding

This is documented in prompt variant `v1.1-bias-correction` and a MAE gate (threshold ≤ 0.50) has been added to the correlation engine so this pattern cannot pass undetected in future calibration runs.

I haven't been able to verify whether `v1.1-bias-correction` resolved the bias because the Groq daily token limit (100,000 tokens/day) was exhausted during development. That run needs to happen before writing evaluation ships to users. It's Condition C1 in the Go/No-Go report.

---

## Provider Switching — Groq TPD Limits

The Groq free tier has a 100,000 token-per-day limit (TPD). Our prompts are approximately 1,600 tokens each. 29 essays = ~46,400 tokens. That should fit comfortably in the daily limit.

What I didn't account for was that I ran the calibration pipeline multiple times during debugging — every failed run still consumed tokens even though it scored zero essays, because the Groq API was being called. By the time I had all the bugs fixed and the pipeline was working correctly, I had exhausted the daily limit.

The last 5 essays — all from the Band 8.5 tier — didn't get scored. This matters because research on automated essay scoring consistently shows that AI models struggle most at the highest band levels, where differences are subtle and require expert-level judgment. Not having Band 8.5 coverage in the baseline is a genuine gap, even though the overall Pearson result was strong.

The practical lesson: for any API with daily limits, run a single test with one or two samples first before running the full pipeline. Validate that the pipeline works end to end on a small sample before spending your entire daily budget.

---

## The WER Validation

The WER pipeline came together more smoothly than the writing calibration. Having already built the provider abstraction and pipeline patterns once, the second time was faster and cleaner.

The Levenshtein-based WER computation I implemented from scratch rather than pulling in a dependency. The algorithm is straightforward enough to implement directly — dynamic programming, O(n×m) space, backtrack to count substitution/insertion/deletion types. Having the implementation in our own code means we can see exactly what's happening when a clip scores unexpectedly high.

One thing I discovered during the WER run that I didn't expect: gTTS regional accents are not particularly distinct. The "British English" TTS and the "American English" TTS sound more similar than real British and American speakers do. The Groq Whisper results showing 0.00% WER for en-US and fr-FR, and only 3.4% for en-GB, reflects that the synthetic audio was clean and accent-neutral rather than genuinely accent-specific.

The synthetic baseline (`v1.0-synthetic`) proves the pipeline works. It does not prove the ASR meets threshold for real accented speech. That's Condition C2 — collecting real audio from LibriSpeech and Common Voice and re-running the pipeline before the Voice Service ships.

---

## What I'd Do Differently

**Run smaller test batches first.** Every time I had a bug, I discovered it after running the full 29-essay pipeline and wasting API tokens. A two-essay smoke test would have caught most of the issues at a fraction of the cost.

**Add the MAE gate from day one.** Pearson correlation alone is an incomplete success criterion for scoring accuracy. I should have known this going in — the research literature on automated essay scoring is clear that correlation and bias are separate concerns. I added the MAE gate only after discovering the problem post-hoc.

**Set up logging levels earlier.** The Groq SDK was emitting debug-level HTTP logs that included every request header, cookie, and rate limit state. This produced thousands of log lines per calibration run and made it hard to see the actual application logs. Suppressing third-party debug logging should be done at the start of a project, not as a cleanup step.

**Document the Windows/asyncpg UUID issue as an ADR immediately.** I found the bug, fixed it, and moved on. I should have written an ADR the moment I understood the root cause. It took me a few minutes to write ADR-002 for the PYTHONPATH issue — I should have done the same for the UUID binding pattern.

---

## What I Learned

**Calibration is not preliminary work.** I came in thinking Phase 0 was the setup before the real product work. It turned out to be one of the most technically demanding parts of the build. The calibration pipeline is more complex than most of Phase 1 will be. That complexity is justified — the entire product promise rests on these numbers.

**Pearson correlation is necessary but not sufficient.** Strong correlation tells you the AI is ranking essays in the same order as human examiners. It does not tell you whether the absolute scores are accurate. Both measures matter. A product that correctly identifies which essay is better while consistently overestimating both by one band will mislead every learner who uses it.

**Provider diversity is a feature, not a complication.** Having OpenAI, Anthropic, Gemini, and Groq all behind the same interface meant I could switch providers as constraints changed — budget, rate limits, model availability — without touching the core pipeline logic. This paid off multiple times during development and will continue to pay off in production.

**The PRD is architecture, not implementation.** The PRD specified what needed to be true. It said nothing about how to build it, which API to use, how to handle rate limits, what to do when a provider is deprecated, or how to detect systematic bias that the primary gate misses. Those were all judgment calls made during implementation. That's what engineering is.

---

## Current State

The infrastructure is solid. The writing calibration pipeline works and produced a strong result. The WER pipeline works and is ready for real audio. Two conditions remain before production can use AI-generated scores:

1. Run v1.1-bias-correction calibration and verify MAE ≤ 0.50
2. Replace synthetic TTS with real accent audio for WER validation

Phase 1 starts now. The foundation holds.

---

*Written from memory and logs, 2026-03-15*
