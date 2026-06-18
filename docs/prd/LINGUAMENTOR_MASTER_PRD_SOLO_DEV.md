# LinguaMentor — Master PRD (Solo-Dev Edition)

**AI-Powered Language Proficiency & Exam Acceleration Platform**

---

## Version & Metadata

- **Project Name:** LinguaMentor
- **Author:** TETSOPGUIM Kefoueg Frank P.
- **Role:** Software Engineer (full stack) — Solo Developer / Product Owner
- **Original Date:** 2025-10-23 · **This revision:** 2026-06-18
- **Status:** Pre-Development — Architecture Re-baselined for Solo Operation
- **Edition:** Solo-Dev. This document supersedes the team-scoped Master PRD for build and operations purposes. Product strategy, AI engine design, data model, and the calibration gate are carried over unchanged. Deployment topology, infrastructure, scaling, disaster recovery, observability, CI/CD, AI provider selection, and cost architecture are rewritten for a single operator on a minimal budget.

---

## Revision Summary — What Changed and Why

This edition keeps the product and its AI/domain design intact and re-engineers only the parts that assumed a funded team (the original estimate explicitly assumed *2 backend + 1 frontend + 0.5 DevOps + 0.5 AI/ML*). The guiding constraints for this revision are: **one developer, infrastructure under ~$50/month, thousands of users in the first six months, and no loss of the robustness that actually protects users or the product's credibility.**

| Area | Original (team edition) | This edition (solo) | Reason |
|---|---|---|---|
| Service topology | 13 independently deployed microservices (~25+ pods at idle) | 3 deployable units (Node front-door, Python AI monolith, async worker) — same logical boundaries internally | "Microservice" here was a deployment choice, not a domain requirement. Logical modules are preserved; physical fragmentation is removed. |
| Orchestration | Kubernetes (EKS/GKE/AKS) + Helm + Terraform + ArgoCD + Argo Rollouts | Docker Compose on a single VPS, managed by Coolify or Dokploy | A solo dev cannot operate a K8s GitOps stack; it adds cost and ops burden with zero user-facing benefit at this scale. |
| Hosting | Cloud-agnostic K8s cluster (3 worker nodes) | One Hetzner CX32-class box (~$8–12/mo); second small box optional for staging | One box runs the full stack at this scale. |
| TTS provider | ElevenLabs primary | OpenAI TTS or Inworld primary; ElevenLabs as Pro-only premium voice | ElevenLabs is ~10–20× the cost of alternatives — the single most expensive line item in the original. |
| STT provider | Whisper + Speechmatics + Google | gpt-4o-mini-transcribe primary (managed); Whisper fallback. No self-hosting. | Self-hosting STT only pays off above ~2,400 audio-hours/month — far beyond launch volume. |
| Disaster recovery | Multi-region warm standby, cross-region replication, quarterly failover drills | Nightly Postgres dumps + Redis RDB snapshots to object storage; annual restore drill | Enterprise BCP is inappropriate pre-revenue; backup-and-restore is the right tier. |
| On-call / incidents | 24/7 PagerDuty, two engineers, P1–P4 hierarchy | Uptime Kuma + webhook alerts (Telegram/Discord); single operator | There is no second engineer. |
| Observability | Prometheus + Grafana + Loki + Jaeger self-hosted | Structured logging + free hosted tier (Grafana Cloud / Better Stack / Axiom free); no distributed tracing | In a monolith you have stack traces; a self-hosted observability stack is itself an ops burden. |
| CI/CD | Blue-green/canary, Pact, OWASP ZAP, Semgrep, mTLS | GitHub Actions: lint + unit tests + Trivy image scan + gitleaks; health-checked rolling restart | Right-sized quality gates without canary theater. |
| Postgres | Primary + read replica, multi-AZ | Single Postgres (containerized at launch); managed Postgres as the documented next step; read replica deferred | Dashboard reads are already Redis-cached; a replica is premature. |
| Scaling targets | 1,000 concurrent users, 200 concurrent voice, HPA everywhere | Single box handles realistic launch concurrency (dozens of voice sessions); documented horizontal scale-out path preserved | Redis-backed sessions already make scale-out trivial later; build for now, not for a hypothetical. |

**Preserved unchanged (load-bearing):** the AI Provider abstraction layer, the Phase 0 calibration gate (Pearson ≥ 0.85), AIModelRun traceability, idempotent/retryable async workers, graceful AI degradation and provider failover, output-schema validation, Cloudflare at the edge, the freemium cost-gating model, prompt-prefix caching, and the per-user AI cost ceiling.

---

# PART I · PRODUCT FOUNDATION

## 1. Executive Summary

### 1.1 What LinguaMentor Is
LinguaMentor is a web-first, AI-driven language proficiency acceleration platform focused initially on English and French. It is not a vocabulary-drill app or a gamified engagement tool. It is an **AI-Orchestrated Language Proficiency Evaluation and Adaptation System** — a platform that teaches, evaluates, adapts, and predicts exam readiness autonomously, at scale, aligned to the rubrics of internationally recognized language proficiency examinations.

The system integrates five core AI-powered engines: a real-time Voice Agent over WebSockets, a rubric-aligned Writing Evaluation Engine, an Exam Simulation Engine covering official test formats, a reinforcement-driven Adaptive Learning Engine with spaced repetition, and a probabilistic Readiness Prediction Engine that forecasts a learner's exam band with a confidence interval.

The architecture separates **deterministic orchestration (Node.js)** from **probabilistic AI inference (Python)**, with strict model-version traceability, streaming-first response delivery, and comprehensive audit logging across every AI interaction. In this edition those layers are deployed as a small number of cooperating processes rather than a microservice fleet (see Part VIII).

### 1.2 The Problem It Solves
Learners preparing for high-stakes exams face a fragmented market that fails them three ways:

- **The Gamification Trap** — Apps like Duolingo optimize for daily active users via streaks and XP. A learner can finish 300 lessons and still fail IELTS Writing Task 2 because they have never written a timed, rubric-graded academic essay.
- **The Simulation Gap** — Official practice materials are static PDFs: questions with no intelligent feedback, no adaptive difficulty, no readiness forecasting.
- **The Accessibility Gap** — Quality exam prep needs human tutors at $30–80/hour, excluding most learners in Africa, Southeast Asia, and Latin America — precisely where certification has the highest life impact.

### 1.3 Why Now
- LLMs now produce instructional feedback measurably correlated with human expert grading (Pearson 0.85+ is achievable and validatable).
- Real-time ASR/TTS APIs support low-latency, multi-accent speech, making fluent AI voice tutoring feasible.
- Demand for English/French certification is accelerating (immigration, university admission, corporate training).

## 2. Vision, Mission & Market

- **Vision:** Become the world's most trusted AI language mentor — professional-level exam prep for every learner, regardless of geography or income.
- **Mission:** Build an intelligent digital tutor that teaches, assesses, adapts, and predicts — exam-grade evaluation at the cost of a monthly subscription.

**Market context:** 1.5B+ active language learners worldwide; ~$61.5B market (2024) projected to ~$127B by 2032; IELTS ~3.5M candidates/year; TOEFL ~1.4M/year; DELF/DALF ~500K/year; human tutoring $30–80/hour. LinguaMentor occupies the uncontested middle ground: adaptive, AI-scored, rubric-aligned practice with readiness forecasting.

## 3. Core Value Proposition

| Audience | Value | Differentiator |
|---|---|---|
| Learner | End-to-end prep — conversation practice, grammar correction, speaking evaluation, official exam simulation, daily progress | The only tool that both *teaches* and *predicts* your exam score |
| Institution | Scalable AI tutoring with class-level CEFR analytics and cohort readiness (post-MVP) | Replace expensive human tutors with measurable AI outcomes |
| Investor | Large market, subscription-ready, low incremental cost via AI, defensible calibrated-scoring moat | High-margin SaaS with no dominant AI-native competitor |

### 3.2 Dual-Track Product Model
- **Fluency Track** — general conversational practice, daily CEFR progression, vocabulary. Drives top-of-funnel and habit formation. No exam pressure.
- **Exam Track** — timed mock exams, rubric scoring, band prediction, section-by-section analysis. Targets learners with a specific exam date and target score.

The two tracks share the same AI infrastructure, data model, and skill-measurement engine; only the learner's goal and interface emphasis differ.

### 3.4 Defensible Differentiators
- AI calibrated to real exam rubrics with **transparent correlation scores shown on every evaluation**.
- **Four-dimensional CEFR profiling** (Speaking, Listening, Reading, Writing independently).
- **Readiness prediction with confidence intervals**, updated after every session.
- **Accent-relative pronunciation scoring** (en-US, en-UK, fr-FR, fr-CA), not an absolute native baseline.
- **Socratic dialogue mode** — the Voice Agent proactively targets detected weaknesses.
- **Spaced repetition at the skill level** — a forgetting-curve scheduler that picks the daily priority dimension.

## 4. Competitive Landscape

| Capability | Duolingo | Magoosh | E2Language | Preply | LinguaMentor |
|---|---|---|---|---|---|
| Real-time AI voice tutor | No | No | Partial | Yes (human) | **Yes — full AI** |
| Rubric-aligned writing scoring | No | Partial | Yes (human) | Yes (human) | **Yes — AI automated** |
| 4-Dimensional CEFR profiling | No | No | No | No | **Yes — all 4 skills** |
| Exam band prediction | No | No | No | No | **Yes — with CI** |
| Skill-level spaced repetition | No | No | No | No | **Yes — SRS engine** |
| Accent-relative pronunciation | No | No | No | Partial | **Yes — configurable** |
| Score appeal & transparency | No | No | No | No | **Yes — calibration shown** |
| PWA offline mode | Yes | No | No | No | **Yes — lesson cache** |
| Cost (monthly, pro tier) | $7 | $15 | $25+ | $30+/hr | **$15–20 target** |

**Positioning:** *"LinguaMentor is the AI alternative to expensive human tutors — delivering exam-grade evaluation, real-time voice coaching, and probabilistic readiness forecasting at the cost of a monthly subscription, for learners anywhere in the world."* Pricing is anchored against human-tutor rates ($30–80/hr), not Duolingo ($7/mo).

## 5. Business Model

### 5.1 Freemium Boundary
The freemium boundary is defined by the **AI cost drivers**. The most expensive operations — Voice sessions and full essay scoring — sit behind the Pro paywall. **This gating is the single most important cost-control mechanism in the system and must not be weakened** (see §55).

| Feature | Free | Pro |
|---|---|---|
| Writing evaluations | 3 / month | Unlimited |
| AI Mentor (chat) | Text-only | Text + Voice Agent |
| Teaching persona | Companion only | Coach, Companion, Examiner |
| CEFR dashboard | Single overall level | 4D radar chart |
| Readiness prediction | Not available | Full band projection + CI |
| Mock exams | 1 / month | Unlimited |
| Exam types | English only | English + French |
| SRS scheduler | Basic daily prompt | Full SRS engine |
| Score appeal | Not available | Available on all evaluations |
| Offline mode | Both tiers | Both tiers |
| PDF reports | Not available | Downloadable after each exam |
| Share Your Score | Both tiers | Both tiers |

### 5.2 Plans
- **Individual Monthly:** $15–18/mo, full Pro, cancel anytime.
- **Individual Annual:** $120–150/yr (~25% saving).
- **Institution / Volume:** custom per-seat (post-MVP) — dashboard, cohort analytics, admin tools.
- **Add-Ons:** certificates, AI coaching session packs, enterprise dashboards.

### 5.4 Virality — Share Your Score
After a mock exam, learners generate a branded score card (band + improvement delta) shareable via WhatsApp, LinkedIn, X, Instagram Stories. Free marketing; no account needed to view a shared card. Logged as `ShareEvent` for viral attribution.

## 6. Product Category & The Five Engines

**Formal category:** AI-Orchestrated Language Proficiency Evaluation & Adaptation System. Deterministic orchestration at the Node layer; probabilistic inference at the Python layer.

| Engine | Responsibility |
|---|---|
| 1. AI Voice Agent | Real-time conversational evaluation over WebSocket — Socratic follow-ups, accent-relative pronunciation scoring, fluency assessment. |
| 2. Writing Evaluation | Rubric-aligned essay scoring, grammar correction, CEFR classification, structured JSON feedback. Async, target < 6s. |
| 3. Exam Simulation | Timed, section-based mock exams (IELTS, TOEFL, DELF). Objective sections sync; subjective delegated to Writing/Voice. |
| 4. Adaptive Learning | 6-dimensional skill vector, trend-based weakness detection, skill-level spaced repetition, Daily Diagnostic. |
| 5. Readiness Prediction | Weighted readiness score + projected band with confidence interval. |

> **Note for this edition:** these five engines remain the logical decomposition of the system. They are implemented as **modules within one Python service**, not five separately deployed services (Part VIII).

## 7. Language & Exam Scope

**Phase 1: English and French only** — to allow deep rubric calibration before expanding.

| Language | Scope & Configuration |
|---|---|
| English | General fluency + IELTS Academic / TOEFL iBT. Accents: en-US (default), en-UK. Rubric: Task Response, Coherence & Cohesion, Lexical Resource, Grammatical Range & Accuracy. |
| French | General fluency + DELF B1/B2. Accents: fr-FR (default), fr-CA (future-ready). Rubric: Pertinence, Cohérence, Richesse lexicale, Correction grammaticale. |

**Accent configuration is a first-class system parameter.** Every voice session, pronunciation evaluation, and ASR model selection is parameterized by the learner's chosen target accent. Pronunciation is scored *relative to* the target accent baseline, not an absolute native standard (pedagogically correct; fairer for global learners).

Future scope (carried over): TCF (Phase 2, fr-CA), Cambridge B2/C1 and Spanish DELE (Phase 3), HSK/JLPT (Phase 4).

## 9. Technical Success Metrics

### 9.1 Performance Targets (production requirements, not aspirations)

| Metric | Target |
|---|---|
| API latency (non-AI routes) | < 300 ms |
| Voice Agent round-trip | < 2.5 s |
| Streaming first token | < 500 ms |
| Essay scoring (async) | < 6 s |
| Lesson/chat response (sync) | < 2 s |
| Readiness recompute (async) | < 4 s |
| Dashboard load (cached) | < 500 ms |

### 9.2 Voice Latency Budget
Capture/upload ~400 ms · ASR ~600 ms · LLM ~900 ms (first token ~500 ms) · post-processing ~300 ms · TTS ~300 ms (overlaps LLM) → **< 2.5 s** round-trip.

### 9.3 AI Accuracy (quality floor — no launch below these)

| Metric | Method | Target |
|---|---|---|
| Writing vs human grader | Pearson correlation | ≥ 0.85 |
| Speaking eval stability | Variance on identical inputs | < 10% |
| CEFR classification accuracy | vs human baseline | ≥ 90% |
| Readiness band deviation | Predicted vs actual | ± 0.5 band |
| Speech recognition WER | Across accents | < 10% |

### 9.4 Business & Retention
90-day retention > 45% · daily return rate > 30% · satisfaction ≥ 4.2/5 · free→Pro conversion > 8% · appeal resolution within SLA > 95% · calibration ≥ 0.85 sustained.

---

# PART II · NON-FUNCTIONAL REQUIREMENTS & CONSTRAINTS

## 10. Non-Functional Requirements

### 10.1 Performance & Latency
No AI call is synchronous unless the UX requires it. Heavy operations (essay scoring, readiness recompute, full exam evaluation) are always async with client notification on completion. Latency budgets as §9.1.

### 10.2 Scalability Targets — Re-baselined for Solo Operation

> **CHANGED.** The original targeted 1,000 concurrent users and 200 concurrent voice sessions across an HPA-autoscaled cluster. For launch, the realistic figure is *thousands of registered users with single-digit-to-dozens concurrent voice sessions*. The design below runs on one box and preserves a clean scale-out path.

| Requirement | Specification |
|---|---|
| Registered users (6-month) | Thousands; handled comfortably on a single VPS |
| Concurrent voice sessions (launch) | Dozens, on one box. Session state in Redis enables horizontal scale-out when needed. |
| Stateless tier | Node front-door (HTTP/WS/SSE) and Python AI service are stateless apart from Redis-stored session state → can be replicated across boxes later with no code change. |
| Stateful services | PostgreSQL and Redis — scale vertically first; managed Postgres + Redis replica is the documented next step (§48.4). |
| Scale-out trigger | When one box's CPU/connection limits are reached, add a second app box behind Cloudflare; sessions already recover from Redis. |

### 10.3 Availability & Graceful Degradation

| Requirement | Specification |
|---|---|
| Uptime target | Best-effort ~99%. **No contractual SLA at launch.** Restore-from-backup is the recovery tier. |
| AI provider fallback | **KEEP** — primary LLM/ASR/TTS failure triggers automatic switch to a backup provider via the abstraction layer. |
| ASR failure | **KEEP** — voice session falls back to text input; user notified. |
| LLM timeout | **KEEP** — partial grammar feedback returned; full scoring queued for retry. |
| Partial scoring error | **KEEP** — session data preserved; retry without re-submitting content. |
| RTO / RPO | RTO: a few hours (restore from latest backup). RPO: ≤ 24h (nightly DB dump) / ≤ 5 min for in-flight Redis state via RDB snapshots. Acceptable pre-revenue. |

### 10.4 Security Requirements (kept; trimmed where team-only)

| Requirement | Specification |
|---|---|
| Authentication | JWT access tokens (15-min) with refresh-token rotation (7-day). Refresh tokens in HTTP-only secure cookies. |
| Authorization | RBAC: Learner, Admin, Institution Admin (post-MVP). Enforced in the Node front-door. |
| Transport | TLS 1.2+, HTTPS enforced, HSTS. TLS terminated at Cloudflare/ingress. |
| Encryption at rest | AES-256 for DB storage; audio blobs encrypted in object storage. |
| AI-specific | Prompt-injection filtering on all user input before LLM calls; output-schema validation on all AI responses before forwarding. |
| Rate limiting | Redis token bucket per user per endpoint tier (Standard 60 AI calls/hr, Pro 300/hr). |
| Secrets | No secrets in version control. Stored in the platform's secret store (Coolify/Dokploy secrets or a cloud secret manager). Rotate API keys/DB creds. **(mTLS between services removed — not applicable in a monolith.)** |

### 10.5 Data Privacy (unchanged — load-bearing)
Full GDPR compliance with a synchronous right-to-erasure endpoint (deletes PII, removes audio blobs, anonymizes AIModelRun logs, retains only aggregated anonymized metrics). CCPA opt-out. Explicit opt-in consent before storing any voice recording (tracked per user). PII stored only in the `USER` entity; downstream entities reference `user_id`. Model-retraining opt-out respected in pipelines. Audio retained 90 days then deleted unless the user opts into longer retention.

### 10.6 Offline & Low-Connectivity Mode (first-class feature — kept)
The target markets have connectivity variability, so PWA offline mode is a competitive necessity. Next.js PWA with a Service Worker for request interception and IndexedDB for local storage. Offline availability: last 3 lessons (full text), recent vocabulary, prior feedback summaries, last cached dashboard. AI features are unavailable offline (Voice, essay eval, exam sim, readiness) — buttons disabled with a graceful message and a persistent offline banner. Queued offline events sync on reconnect; skill-vector deltas reconciled server-side.

### 10.7 Cost Constraints (cost controls are structural — expanded in §55)
AI inference is the primary recurring cost and is managed structurally at three levels: **model routing** (task complexity → model tier), **caching** (static prompt-prefix caching + Redis result caching of identical inputs), and **async batching** (off-peak SRS/analytics). Plus a **per-user AI cost ceiling** by tier and abuse-detection alerts.

## 11. System Constraints & Design Assumptions

### 11.1 Web-First
All Phase 1 interaction is via the browser. No native app. Voice capture uses WebRTC/MediaRecorder; real-time comms use WebSockets; the PWA gives installable mobile behavior without native development.

### 11.2 Portable, Not "Cloud-Agnostic via Kubernetes"

> **CHANGED.** The original mandated provider-agnosticism through Kubernetes. This edition keeps portability through **Docker + Docker Compose** and the storage/queue/AI abstraction interfaces — so the stack runs on any VPS or cloud VM (Hetzner, DigitalOcean, AWS Lightsail, GCP) without code changes, and without operating Kubernetes.

### 11.3 AI Provider Abstraction Layer (UNCHANGED — the best decision in the document)
LLM, ASR, and TTS are accessed exclusively through an internal **AI Provider Interface Layer** that handles provider selection, failover, version management, and response normalization. **No module calls a provider directly.** This enables provider switching, A/B testing, cost routing, and failover without touching engine logic — and it is exactly what makes the provider swaps in §55 a configuration change rather than a rewrite.

| Component | Provider strategy (this edition) |
|---|---|
| LLM | OpenAI GPT (primary); Anthropic Claude (fallback); a fine-tuned small/open model is a Phase 3+ cost option. |
| ASR | **gpt-4o-mini-transcribe (primary)**; Whisper / Speechmatics (fallback for accent-specific accuracy). Managed only — no self-hosting. |
| TTS | **OpenAI TTS or Inworld TTS (primary)**; ElevenLabs as an optional **Pro-only premium voice**; Azure Neural as fallback. |
| Failover trigger | HTTP 429, HTTP 503, or latency > 2× target → automatic provider switch. |
| Version traceability | `model_name` + `model_version` logged in `AIModelRun` for every inference call. |

### 11.4 Real-Time Communication (kept)
The Voice Agent needs a persistent, low-latency bidirectional channel → **WebSocket** (not polling/SSE). WebSocket session state is stored in **Redis**, so any app process can serve any session and state recovers from the shared store. Session IDs persist across reconnections within the TTL window. *(This is also what makes future horizontal scale-out free.)*

### 11.5 Model Version Traceability (UNCHANGED — load-bearing)
Every inference call is fully traceable for audit, regression detection, and drift comparison. The `AIModelRun` entity captures, per call: `model_name`, `model_version`, `prompt_hash`, `input_token_count`, `output_token_count`, `latency_ms`, `streaming_first_token_ms`, `response_hash`, `user_reference_id`, `task_type`, `calibration_version`, `persona_config`.

### 11.6 Streaming-First Responses (kept)
All user-facing AI responses stream from the first ~500 ms. Chat uses SSE; voice uses WebSocket chunk push, with TTS synthesis beginning from the first complete sentence (sentence-boundary flush to avoid broken-word audio). Streamed voice responses are never cached; identical chat prompts may serve a cached full-text non-streamed response. On stream failure, the client retries silently for ~2 s, then requests a full synchronous response.

## 12. Explicitly Excluded Scope — Phase 1 MVP
Deliberate exclusions to prevent over-engineering before core scoring quality is validated: Listening module (Phase 2), Reading auto-question generation (Phase 3), full analytics dashboards (Phase 2), institution admin dashboard (post-MVP), subscription billing automation (post-MVP — MVP uses manual/waitlist access), multi-language beyond EN/FR (Phase 3). **Architecture rule (kept):** Phase 1 must not depend on any excluded feature; module boundaries, data schemas, and API contracts remain extensible so later modules attach without modifying Phase 1 code.

---

# PART III · FUNCTIONAL SPECIFICATIONS

## 13. Primary Actors & Roles

| Actor | Description | RBAC role |
|---|---|---|
| Learner (primary user) | End-user: signup, placement, lessons, voice practice, exam sim, dashboard, PDF export, score sharing. | `learner` |
| AI Mentor (autonomous agent) | The AI system that teaches, evaluates, generates content, and adapts. A logical agent composed of structured prompt roles — **implemented as modules within the Python AI service.** | `system` (internal) |
| Admin (operator) | Monitors platform health, AIModelRun audit, calibration, anonymized analytics, incident response. No access to individual user content. | `admin` |
| Institution Admin (post-MVP) | Class-level CEFR distributions, cohort readiness, bulk reports, volume licenses. No individual session content. | `institution_admin` |

## 14. Learner Journey — 7 Stages
A continuous loop (not linear); each session feeds the adaptive engine, which drives the next.

1. **Onboarding & Placement** — capture goal/exam target; AI placement test (writing + speaking samples) → 4D CEFR profile, personalized roadmap, SRS initialized.
2. **Track + Persona Selection** — Fluency/Exam track; Companion/Coach/Examiner persona (tier-gated) loaded into the prompt system.
3. **Personalized Dashboard** — 4D radar chart, Daily Diagnostic CTA, readiness score + CI, streak tracker; updated after each session.
4. **AI Lesson / Voice Session** — chat (text/voice), streaming responses (< 500 ms first token), pronunciation recorder, inline corrections, Socratic follow-up targeting detected weakness.
5. **Adaptive Feedback & SRS** — skill-vector update, difficulty adjustment, SRS interval recompute, next challenge targets the lowest dimension.
6. **Exam Simulation** — timed sections, auto-save, objective scored sync, subjective async; rubric-aligned report; appeal option; readiness updated.
7. **Analytics & Share** — 4D breakdown, longitudinal chart, PDF export (Pro), Share Your Score card, next study path.

**Admin journey:** secure login (OIDC/OAuth2, MFA); a single operations dashboard monitoring app health, queue depth, DB response times, WebSocket session health, AIModelRun audit, and calibration drift.

---

# PART IV · AI SYSTEM ENGINEERING

## 17. High-Level System Components

> **CHANGED — deployment view.** The system is organized in five **logical** layers (Client, Gateway, Service, Engine, Data). In this edition the Gateway + Service layers are implemented in **one Node.js application** ("the front-door"), the Engine layer is **one Python application** with internal engine modules, and heavy async work runs in **one worker process**. The logical layering below is unchanged; only the physical packaging is consolidated.

| Logical component | Implemented in | Notes |
|---|---|---|
| API Gateway (REST + SSE + WS upgrade, JWT, rate limit, streaming proxy) | Node front-door | Cloudflare-fronted |
| WebSocket / Voice session routing | Node front-door | Redis-backed session state |
| Exam lifecycle + auto-save | Node front-door | Mostly CRUD |
| Report & Share (PDF/PNG card) | Node front-door (gen offloaded to worker) | |
| AI Orchestrator (prompt assembly, routing, schema validation, AIModelRun logging) | Python AI service | Hub for all engines |
| Writing / Voice / Adaptive / Readiness / SRS / Calibration engines | Python AI service modules | Internal function calls, not network hops |
| Async jobs (writing_eval, appeal_eval, readiness_compute, daily_srs_gen, report_gen) | Worker process | BullMQ on Redis |
| Calibration drift check | Scheduled cron job | Was a standalone service; now a periodic task |
| Data | PostgreSQL · Redis · S3-compatible object storage | |

## 19. AI Orchestration Architecture (UNCHANGED — this is good)

### 19.1 Principles
The orchestration layer receives input, constructs prompts via the layered architecture, routes to the appropriate model tier, enforces output-schema validation, logs every call to `AIModelRun`, and returns structured results. **No module calls an LLM provider directly** — all inference flows through this layer.

- **Deterministic orchestration** — routing rules are deterministic code; no LLM decides which LLM to call.
- **Model-tier routing** — task complexity selects the model tier.
- **Streaming-first** — SSE for chat, WS chunks for voice.
- **Schema enforcement** — every output validated against a JSON schema; invalid outputs trigger a corrective retry.
- **Full traceability** — every call logged to `AIModelRun`.
- **Provider abstraction** — providers injected via interface.

### 19.2 Multi-Agent Logical Model
Eight "agents" are **prompt configurations within the orchestration layer**, not separate processes: Conversational, Writing Evaluation, Grammar Correction, CEFR Classification, Exam Simulation, Readiness Analysis, Socratic Follow-Up, Daily Diagnostic. Each has a defined task instruction, rubric injection, and output schema; all share the same LLM infrastructure.

### 19.3 LLM Routing Strategy (kept; biased harder toward the cheap tier — see §55)

| Task | Model tier | Temp | Rationale |
|---|---|---|---|
| Grammar correction | Mid-tier | 0.2 | Deterministic corrections |
| **Writing scoring** | **High-tier** | 0.1 | High-stakes rubric scoring — moat |
| Conversation (Mentor) | Balanced | 0.6 | Natural flow |
| **Readiness forecasting** | **High-tier** | 0.0 | Deterministic projection — moat |
| Socratic follow-up | Mid-tier | 0.4 | Targeted but varied |
| Daily diagnostic | Mid-tier | 0.3 | Batch off-peak |
| CEFR classification | High-tier | 0.1 | Core accuracy metric |
| Exam question generation | Balanced | 0.5 | Varied within format |

> **Cost note:** push everything possible to the mid/cheap tier; reserve the high tier strictly for **writing scoring, CEFR classification, and readiness forecasting** — the three outputs that constitute the product's credibility.

### 19.4 Prompt Layering (8 layers, version-controlled, assembled in order)
1. System Layer (platform identity, non-overridable)
2. Policy & Guardrails (never fabricate scores, no discrimination, no copyrighted reproduction)
3. Teaching Persona (Coach / Companion / Examiner — tone, correction style, Socratic flag)
4. Task Instruction
5. Rubric Injection (exam-specific descriptors and weights)
6. User Context (4D CEFR, skill vector, exam target, language, accent, SRS state)
7. Dynamic Session (bounded conversation history, current session state)
8. Output Schema (the required JSON contract)

## 20. AI Voice Agent

Multi-stage pipeline targeting a 2.5 s round-trip, parameterized by the learner's accent target.

| Stage | Component | Target | Notes |
|---|---|---|---|
| 1. Capture | MediaRecorder → WebSocket upload | < 400 ms | WebRTC; no native SDK |
| 2. ASR | gpt-4o-mini-transcribe (primary); Whisper/Speechmatics fallback; model by accent | < 600 ms | en-UK → en-GB-tuned model where available |
| 3. Text analysis | Orchestrator grammar + fluency + weakness detection | < 200 ms | Shared with step 4 inference |
| 4. LLM | Streaming response; Socratic follow-up if weakness detected | < 900 ms (first token < 500 ms) | Dialogue state machine selects response type |
| 5. Post-processing | Schema validation · skill-vector update · AIModelRun log | < 300 ms | Async; non-blocking |
| 6. TTS | **OpenAI TTS / Inworld (primary)**, ElevenLabs (Pro premium), Azure (fallback); sentence streaming | < 300 ms (overlaps LLM) | Begins before full response ready |

**Dialogue state machine** (deterministic) includes a `SOCRATIC_FOLLOWUP` state branching from `FEEDBACK` when a weakness is detected, turn count < max, and persona ≠ Examiner.

**Socratic mode:** triggers when `weakness score < threshold AND turn_count < max_socratic_turns (default 3) AND persona != Examiner`. Targets the detected weakness (e.g., 'th'-dense vocabulary for weak 'th' pronunciation). Max 3 follow-ups per topic. State persisted in Redis `voice_state:{session_id}`. **Examiner persona disables Socratic mode** (it evaluates, it doesn't guide).

**Accent-relative pronunciation:** target accent set at profile creation (changeable in Settings), included in every voice session context (Layer 6). ASR model and phoneme baseline are selected per accent. Score (0.0–1.0) stored in `SpeakingMetrics` with `accent_target`; transparency shown to the learner ("rated against en-UK standard").

## 21. Writing Evaluation Engine
Async pipeline: submission returns a `job_id` immediately; full evaluation completes < 6 s; client notified via poll/push.

- **IELTS rubric:** Task Response · Coherence & Cohesion · Lexical Resource · Grammatical Range & Accuracy (25% each).
- **DELF rubric:** Pertinence · Cohérence & cohésion · Richesse lexicale · Correction grammaticale (25% each).
- **Composite:** equal-weighted by default; weights are exam configuration, never hardcoded. Score 0.0–9.0 (IELTS band scale); DELF percentage mapped to band for unified display.
- **Calibration transparency (kept):** every report shows the current AI-to-human correlation and sample size, e.g. *"This score was calibrated against 247 human-graded IELTS essays. AI-to-human correlation: 0.88."*
- **Score Appeal (kept):** a secondary async evaluation (different prompt config + temperature) runs < 60 s; the result and discrepancy feed the calibration monitor.

## 22. Four-Dimensional CEFR Profiling
A single CEFR level masks asymmetric proficiency. The 4D profile tracks Speaking, Listening, Reading, Writing independently.

| Dimension | Source |
|---|---|
| Speaking | Voice Agent session data (pronunciation, fluency, coherence, interaction) |
| Listening | Phase 2 module; Phase 1 proxy from speaking |
| Reading | Phase 3 module; Phase 1 proxy from writing |
| Writing | Writing Evaluation Engine |

Displayed as a dashboard radar chart with current level per axis and a week-over-week delta.

## 23. Adaptive Learning Engine

- **Skill vector (6 normalized dims):** `{grammar, vocabulary, coherence, pronunciation, fluency, comprehension}`, each 0.0–1.0. Updated by weighted moving average: `New = (Previous × 0.8) + (Recent × 0.2)`.
- **Weakness detection:** `metric < threshold AND trend decreasing over last 3 sessions`. Thresholds — grammar 0.65, vocabulary 0.60, coherence 0.55, pronunciation 0.70, fluency 0.60, comprehension 0.55. Tags carry dimension, severity, timestamp. Response: reduce difficulty on the dimension, reset SRS interval to 1 day, activate Socratic mode next voice session. Recovery: tag cleared after 3 consecutive above-threshold sessions.
- **SRS at skill level:** `Priority = (days_since_last_practice × 0.4) + ((1 − last_skill_score) × 0.4) + (volatility_factor × 0.2)`. Interval doubles on success (max 30 days), resets to 1 day on failure. State on `SkillVector` and cached in Redis `srs_state:{learner_id}`. SRS evaluated nightly per learner; next-day Daily Diagnostic pre-generated and cached (served on login).

## 24. Exam Simulation System
Lifecycle: `INIT → SECTION_START → TIMER_RUNNING → ANSWER_SUBMISSION → SECTION_END → FINAL_EVALUATION → RESULT_REPORT`. Auto-save every 60 s for writing; no pause (mirrors real exam). Objective scored sync; subjective delegated to Writing/Voice async. Phase 1 covers Writing + Speaking (~50% of IELTS weight); Phase 2 adds Listening (75%); Phase 3 adds Reading (100%). Equal section weights by default, configurable per exam standard.

## 25. Readiness Prediction Engine
`Readiness Index = weighted_skill_average × trend_factor × stability_factor`; `Projected Band = Base + Trend Adjustment ± Confidence Interval`. Trend factor positive if last 3 sessions improving; stability from score variance (high variance widens CI). After every session (including Daily Diagnostic) the index is recomputed and the delta shown: *"You improved +0.2 bands today. Current projection: IELTS Band 6.5 ± 0.5 (85% confidence)."*

## 26. AI Ethics, Bias Controls & Governance (kept)
Quarterly linguistic-bias audits; accent fairness verified per target; fully transparent scoring (rubric breakdown + correlation + model version on every report); score-appeal pathway with human review on significant discrepancies; retraining opt-out respected; differential privacy on aggregate analytics; **model-version freeze during scheduled exam periods** (no provider model swap mid-exam-window).

## 27. AI Evaluation Calibration Process (NON-NEGOTIABLE — UNCHANGED)

> **Phase 0 — Calibration must complete before the Writing Engine goes live. No user-facing essay evaluation launches until Pearson correlation ≥ 0.85 is confirmed against human IELTS graders. This is the single non-negotiable gate in the entire plan and the foundation of the product's credibility.**

**Phase 0 protocol:** collect 50–100 essays per exam type (human-graded by certified examiners, inter-rater reliability > 0.8); run AI scoring; compute Pearson correlation per category and overall (target ≥ 0.85); tune rubric injection prompts and re-run until met; parallel accent calibration (50 speech samples per accent, WER < 10%); store `calibration_version='v1.0-launch'` as immutable baseline; signed GO/NO-GO gate.

**Ongoing drift monitoring:** weekly correlation check on 10 recent essays (alert if drop > 0.05); full recalibration required before activating any new provider model version; drift alert → scoring frozen until investigated; quarterly recalibration; current `calibration_version` + correlation shown on every report.

---

# PART V · DATA ARCHITECTURE

## 28. Storage Architecture (three tiers — design kept; topology simplified)

| Tier | Use | This edition |
|---|---|---|
| PostgreSQL (relational) | Users, profiles, sessions, skill vectors, evaluations, exam attempts, AI inference logs. ACID for score writes. | **Single instance** (containerized at launch). Read replica deferred; dashboard reads are Redis-cached. Documented upgrade path to managed Postgres (§48.4). |
| Redis (in-memory cache + state) | WebSocket voice session state, SRS schedule cache, persona config, rate-limit token buckets, BullMQ queues. TTL-managed. | Single instance/container at launch. |
| S3-compatible object storage | Audio blobs, generated PDF reports, profile photos (post-MVP). Encrypted at rest; CDN distribution for reports. | AWS S3 or **Backblaze B2 / MinIO** (cheaper, S3-compatible). 90-day lifecycle expiry on audio. |

### 28.2 Design Principles (unchanged)
PII only in `USER`; downstream entities reference `user_id`. No evaluation result without an `AIModelRun` record (enforced at app layer). Soft deletes for user-facing entities; hard deletes only for GDPR erasure (retaining anonymized aggregates). All timestamps UTC. Scores stored as `NUMERIC(4,2)` (never float) to prevent calibration rounding drift. **Additive-only migrations in Phase 1** — no column drops/renames — to keep deployments zero-downtime.

### 28.3 Domains & Key Entities
Six logical domains (Identity, Learning, Evaluation, Exam, Analytics, Sharing) map to the engine modules. Key entities include: `User`, `LearnerProfile`, `SkillVector`, `SpeakingMetrics`, `AIModelRun`, `DailySession`, `ScoreAppeal`, `ReadinessSnapshot`, `ShareEvent`, and exam attempt/section records. Cross-domain links are FK references only.

## 33. Caching & Offline Architecture

### 33.1 Redis Key Architecture (`{domain}:{identifier}`)

| Key | TTL | Purpose |
|---|---|---|
| `session:{session_id}` | 2h | WebSocket voice session state |
| `voice_state:{session_id}` | 2h | Dialogue state + context buffer |
| `persona:{session_id}` | 2h | Active teaching persona config |
| `user_rate:{user_id}` | 1h | Rate-limit token bucket |
| `srs_state:{learner_id}` | 1h | SRS priorities and intervals |
| `srs_daily:{learner_id}` | 24h | Pre-generated daily micro-session |
| `lesson_cache:{hash}` | 7d | Cached lesson content by prompt hash |
| `cefr_classify:{hash}` | 24h | CEFR result for identical input |
| `grammar_cache:{hash}` | 6h | Grammar result for identical text |
| `readiness_cache:{learner_id}` | 1h | Cached readiness snapshot |

### 33.2 PWA Offline Sync
Service Worker intercepts requests; IndexedDB stores offline content (lessons 7-day TTL, feedback 30 days, vocabulary 14 days). Offline queue (`offline_queue`, auto-increment `event_id`) holds `{event_type, payload, timestamp}` and syncs on reconnect; skill-vector deltas reconciled server-side.

## 34. API Architecture
RESTful HTTP (JSON) for most operations; WebSocket for voice; SSE for chat streaming. JWT Bearer on protected routes; refresh token via HTTP-only cookie. Consistent error envelope `{error: {code, message, field?}}`; strict status codes (400/401/403/404/429/500). Rate limiting via Redis token bucket (Standard 60/hr, Pro 300/hr; `Retry-After` on 429). **Idempotency-Key** header on scoring/financial POSTs (24h dedupe window) — *load-bearing for the retryable worker design.* OpenAPI 3.0 spec served at `/api/docs` (staging only). Health check `GET /health`.

**Endpoint groups (unchanged):** Auth (`/auth/*`), User & Profile (`/user/*`, including GDPR `DELETE /user/me`), Session & Adaptive (`/session/*`, persona), Writing (`/writing/submit|result/:job_id|appeal/:id|calibration`), Exam (`/exam/start|section/:id/submit|attempt/:id|report|share/:id`), Analytics & Readiness (`/analytics/*`). WebSocket at `wss://.../voice` with `session_start` / `audio_chunk` / `session_end` client messages and `transcript` / `ai_response_chunk` / `feedback` / `socratic_followup` / `session_summary` server messages.

---

# PART VII · UX (Summary)

- **Teaching Persona UI:** three cards at onboarding and in Settings; Companion pre-selected (free, zero friction); locked cards open a specific-benefit upgrade modal (not a hard gate). Mid-session switch takes effect from the next AI turn with full context preserved. Persona is a Layer-3 prompt config — **zero additional infrastructure**, switchable at the cost of prompt tokens only. Examiner disables Socratic mode.
- **Navigation:** persistent sidebar (desktop) / bottom bar (mobile). Top bar: logo, 4D CEFR badge, persona selector, notifications, profile. Primary sections: Dashboard, Practice (Fluency), Exam Prep, Progress, Settings — each one click away.
- **Accessibility:** WCAG 2.1 AA (4.5:1 body / 3:1 large text), full keyboard nav, ARIA + live regions for streaming responses, breakpoints 375/768/1024, base 16px (min 14px), reflow to 200% zoom, `prefers-reduced-motion` respected, RTL-ready via CSS logical properties, 44×44px touch targets.
- **Edge UX:** AI-latency staged messaging (2s "thinking" → 6s "taking longer" → 15s retry toast); silent stream reconnect (2s) then sync fallback; exam connectivity loss → immediate auto-save, timer continues, restores within 5 min; appeal pending badge with async result; mid-session persona switch transition message; placement-test resume; session timeout warning at 25 min.

---

# PART VIII · INFRASTRUCTURE & OPERATIONS (Fully Rewritten for Solo Operation)

## 48. Deployment Architecture

> LinguaMentor runs as a small set of Docker containers on a single VPS, managed by a lightweight self-hosted PaaS (Coolify or Dokploy). Everything is defined in code (Docker Compose + a Git repo). There is **no Kubernetes, Helm, Terraform, ArgoCD, or service mesh.** Fault isolation is achieved by separating the always-on web tier from the retryable async worker, and by graceful AI degradation — not by a pod fleet.

### 48.1 Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 PWA (App Router, `next-pwa` Service Worker, Tailwind). Deployed to **Cloudflare Pages or Vercel free/hobby tier**. |
| Node front-door | Node.js (Fastify). JWT middleware, rate limiting via `ioredis`, SSE streaming proxy, WebSocket upgrade handling. Cloudflare-fronted. |
| Python AI service | Python 3.11 + FastAPI + Uvicorn. **One service** containing all engine modules (Writing, Voice, Adaptive, Readiness, SRS, Calibration) behind the AI Orchestrator and provider abstraction. Async inference. |
| Worker | Node or Python process consuming BullMQ queues: `writing_eval`, `appeal_eval`, `readiness_compute`, `daily_srs_gen`, `report_gen`. Priority queue for Pro appeals. |
| Databases | PostgreSQL 16 (single instance at launch). Redis 7 (session state, rate limiting, SRS state, queues, LRU cache). |
| Object storage | S3-compatible — Backblaze B2 / AWS S3 / MinIO. AES-256 SSE. 90-day audio lifecycle. |
| Edge / WAF / CDN | **Cloudflare (free tier)** — static asset delivery, DDoS protection, edge caching, TLS termination, WAF rules including prompt-injection signatures at the edge. |
| Process management / deploy | **Coolify or Dokploy** — git-push deploys, TLS via Let's Encrypt, health checks, one-click rollback, secret storage. |
| CI | **GitHub Actions** — lint, unit tests, Trivy image scan, gitleaks. |
| Observability | Structured JSON logs; **Uptime Kuma** for uptime checks; a free hosted metrics/log tier (Grafana Cloud / Better Stack / Axiom) optional. Alerts to Telegram/Discord webhook. |

### 48.2 Deployment Topology — Three Units on One Box

```
                 Cloudflare (CDN · WAF · DDoS · TLS)
                              │
        ┌─────────────────────┴─────────────────────┐
        │              Single VPS (Hetzner)          │
        │  ┌──────────────┐  ┌────────────────────┐  │
        │  │ Node          │  │ Python AI service  │  │
        │  │ front-door    │──▶ (Orchestrator +    │  │
        │  │ REST/WS/SSE   │  │  all engine modules)│  │
        │  └──────┬───────┘  └─────────┬──────────┘  │
        │         │                    │             │
        │  ┌──────▼─────────┐   ┌──────▼─────────┐   │
        │  │ Worker (BullMQ)│   │ Cron: SRS gen, │   │
        │  │ async scoring  │   │ calibration chk│   │
        │  └──────┬─────────┘   └────────────────┘   │
        │         │                                   │
        │  ┌──────▼──────┐  ┌──────────┐              │
        │  │ PostgreSQL  │  │  Redis   │              │
        │  └─────────────┘  └──────────┘              │
        └───────────────────────┬─────────────────────┘
                                 │
                  S3-compatible object storage (B2/S3)
                  + nightly DB/Redis backups
```

Front-door (A) and AI service (B) talk over localhost; the worker (C) is separate so async scoring fails/retries independently of live traffic. PDF/report generation is offloaded to the worker.

### 48.3 Service Inventory (replaces the 13-service/pod-count table)

| Unit | Process | Always-on? | Responsibility |
|---|---|---|---|
| A | Node front-door | Yes | All inbound REST + WS + SSE; auth; rate limiting; exam lifecycle; streaming proxy |
| B | Python AI service | Yes | Orchestration + all five engines + provider abstraction + AIModelRun logging |
| C | Worker | Yes | `writing_eval`, `appeal_eval`, `readiness_compute`, `report_gen` |
| — | Cron jobs | Scheduled | `daily_srs_gen` (off-peak), weekly calibration correlation check |
| — | PostgreSQL, Redis | Yes | Data + state |

### 48.4 Documented Scale-Out Path (when, not now)
1. **Vertical first** — bump the VPS (Hetzner allows near-zero-downtime resize).
2. **Split data tier** — move Postgres to a managed provider (Neon/Supabase/Crunchy) and add a Redis replica; the app changes nothing because of the abstraction layer.
3. **Add an app box** — run a second copy of A+B behind Cloudflare; voice sessions already recover from Redis, so no sticky sessions needed.
4. **Only then** consider a read replica and per-engine service extraction (the module seams already exist).

## 49. Containerisation (no Kubernetes)
One multi-stage Dockerfile per unit (A, B, C). `docker-compose.yml` defines the full stack including Postgres and Redis. Coolify/Dokploy handles deploy, TLS, health checks, and rollback. Staging is either a second cheap box or a separate Compose project on the same box. Production secrets live in the PaaS secret store, never in Git.

## 50. Scaling Strategy
- **WebSocket scaling:** session state in Redis → any app process serves any session. Single box handles dozens of concurrent voice sessions; scale-out per §48.4.
- **Worker scaling:** increase worker concurrency or run a second worker container; BullMQ distributes jobs. Appeal queue gets priority.
- **Streaming routes:** ingress/proxy timeout raised for `/ws/*` and `/stream/*` (300s vs 60s default) — configured in Cloudflare + the front-door.
- **No HPA, no pod pre-warming.** Always-on processes already keep provider connections warm.

## 51. Performance & Caching
Latency budgets per §9. Caching layers: Cloudflare edge (static + cacheable GET), Redis result caches (`lesson_cache`, `cefr_classify`, `grammar_cache`, `readiness_cache`), LLM provider **prompt-prefix caching** for static system/rubric layers (target > 70% hit rate on repetitive evaluation prefixes), and pre-generated daily SRS content.

## 52. Security Architecture
Cloudflare WAF + TLS at the edge; HTTPS/HSTS enforced. JWT + refresh rotation; RBAC in the front-door. Secrets in the PaaS secret store with rotation. Prompt-injection filtering before LLM calls; output-schema validation after. AES-256 at rest; audio encrypted in object storage. **Removed (team-only):** inter-pod mTLS, Kubernetes NetworkPolicies, CSI secret driver — irrelevant in a single-host monolith. The VPS firewall exposes only 443 (via Cloudflare) and a locked-down SSH; databases bind to localhost only.

## 53. Observability
- **Logging:** structured JSON to stdout, shipped to a free hosted log tier (or rotated on-box). Every `AIModelRun` produces a log line with `model_name`, `task_type`, `streaming_first_token_ms`, token counts.
- **Uptime:** Uptime Kuma pings `/health` and the WS endpoint; alerts to Telegram/Discord.
- **Metrics & alerts (lightweight):** queue depth (`writing_eval` > 500 → alert), appeal backlog (> 50 over 30 min → alert), 5xx rate (> 2% over 5 min), `streaming_first_token_ms` P95 (> 700 ms), voice round-trip P95 (> 2,500 ms), DB connection saturation, **per-user daily token cost (> 3× average → abuse investigation)**, calibration correlation drop (> 0.05).
- **Removed:** Jaeger distributed tracing (stack traces suffice in a monolith); self-hosted Prometheus/Grafana/Loki (use a free hosted tier instead).

## 54. CI/CD Pipeline
1. **Lint + test** — ESLint/Prettier + Jest (frontend/Node), Pylint/Black + pytest (Python). Coverage gate on new code.
2. **Security scan** — Trivy image scan (fail on HIGH/CRITICAL), gitleaks for committed secrets. (Optional Semgrep SAST.)
3. **Build + push** — Docker multi-stage build, tagged by commit SHA, pushed to a registry (GHCR free for private at low volume).
4. **Deploy** — Coolify/Dokploy pulls and performs a **health-checked rolling restart** with automatic rollback to the previous image if `/health` fails.
5. **DB migrations** — forward-only, additive, run as a pre-deploy step; dry-run in staging first.

> **Removed:** blue-green/canary via Argo Rollouts, Pact contract tests, OWASP ZAP DAST, the named-reviewer manual approval gate. A solo dev with health checks + instant rollback has adequate safety without canary theater.

## 56. Backup & Disaster Recovery (right-sized)
- **PostgreSQL:** nightly `pg_dump` to object storage (B2/S3), 30-day retention, encrypted. (Enable WAL/PITR once on managed Postgres.)
- **Redis:** RDB snapshot every 5 min + AOF for durability; daily snapshot copied to object storage. Most Redis data is reconstructible cache/state.
- **Object storage:** versioning + lifecycle rules; optional cross-region copy is a later, optional step (not required at launch).
- **RTO/RPO:** RTO a few hours (provision box → restore dump → redeploy via Compose); RPO ≤ 24h DB / ≤ 5 min Redis.
- **Restore drill:** **annual** (not quarterly) full restore to an isolated box — confirm the app starts, authenticates, retrieves data, and accepts a writing sample.

> **Removed:** multi-region warm standby, a pre-deployed secondary cluster, S3 cross-region replication, quarterly failover drills. These protect contractual SLAs you do not yet have.

## 57. Incident Response (solo)
- **Severity:** P1 full outage/data breach · P2 major feature down (voice/writing) · P3 degraded single area · P4 minor with workaround.
- **On-call:** you. Uptime Kuma + webhook alerts page your phone. No PagerDuty rotation.
- **GDPR breach (unchanged):** Article 33 DPA notification within 72h, Article 34 user notification if high risk; templates maintained.
- **Runbooks (kept, condensed):** service restart, AI model drift (calibration freeze), credential rotation, DB restore, WebSocket cascade. The drift runbook is the most important: on a correlation drop > 0.05, freeze scoring (optionally downgrade Writing to synchronous review) and investigate before resuming.

---

# PART IX · COST ARCHITECTURE, MVP & DELIVERY

## 55. Cost Architecture (the decisive section)

> **AI inference — not infrastructure — is the dominant variable cost.** Hosting is ~$15–25/month; the AI bill is whatever your gating and provider choices make it. The two levers that keep this project solvent are (a) **rigorous freemium gating** and (b) **provider selection through the abstraction layer**.

### 55.1 AI Inference Cost Model
`Monthly AI cost/user = (avg_tokens/session × sessions/month × token_rate) + (voice_minutes/month × [ASR + TTS rate]) + (essays/month × essay_eval_cost)`.

Controls (kept and sharpened):
- **LLM routing by complexity** — cheap mid-tier for grammar, conversation, SRS, daily diagnostics; high tier only for writing scoring, CEFR classification, and readiness. (~40% saving vs uniform high-tier.)
- **Output token caps** — grammar 200 · writing eval 600 · voice turn 150 · readiness 250.
- **Prompt-prefix caching** — static system + rubric layers cached (> 70% target).
- **Result caching** — identical inputs served from Redis (`grammar_cache`, `cefr_classify`).
- **Async batching** — off-peak SRS pre-generation and analytics.
- **Per-user cost ceiling** — monthly AI cost/user kept below ~40% of Pro revenue; dynamic downgrade + alert if any user exceeds 3× average daily cost. **Enforced as a tested feature, not a future task.**

### 55.2 Provider Selection — the order-of-magnitude decisions

> Prices below are current as of mid-2026 and will drift; treat them as ratios, not contracts. Verify before launch.

- **TTS (biggest risk).** The original specified **ElevenLabs as primary** — the most expensive option in the document. ElevenLabs Multilingual runs roughly **$180–206 per 1M characters** (Flash ~$103/1M), versus **OpenAI TTS ~$15/1M** and **Inworld ~$10/1M**; self-hosted Kokoro is ~$0.70/1M but needs a GPU. For a tutor where learners hear a lot of generated speech, **make OpenAI TTS or Inworld primary and keep ElevenLabs as a Pro-only premium voice.** This single change can cut voice cost ~10–20× with negligible learning-context quality loss.
- **STT.** Use **gpt-4o-mini-transcribe (~$0.003/min)** as primary; Whisper (~$0.006/min) as fallback. **Do not self-host** — self-hosting only pays off above ~2,400 audio-hours/month, far beyond launch, and a solo dev should not run GPU infra.
- **LLM.** Push everything to a cheap tier (e.g. GPT-4o-mini class, ~$0.15/1M input · $0.60/1M output, cached input cheaper); reserve a top model strictly for writing scoring, CEFR classification, and readiness.

### 55.3 Infrastructure Cost Targets (this edition)

| Resource | Sizing | ~Monthly |
|---|---|---|
| VPS (A+B+C+Postgres+Redis) | 1× Hetzner CX32-class (4 vCPU / 8 GB) | ~$8–12 |
| Backups (object storage) | Nightly dumps + audio blobs (90-day lifecycle) | ~$2–10 |
| Cloudflare | Free tier | $0 |
| Frontend hosting | Cloudflare Pages / Vercel hobby | $0 |
| Observability / alerting | Uptime Kuma + free hosted tier | $0 |
| Domain + misc | | ~$2 |
| **Infrastructure subtotal** | | **~$15–25/mo** |
| **AI inference (variable)** | Governed by §55.1–55.2 and freemium gating | usage-driven |

**The survival math:** a free user must cost ≈ $0 (text-only, mid-tier model, hard rate limits) → thousands of free users cost tens of dollars, not thousands. A Pro user's AI cost must stay under ~40% of ~$15 revenue (target < $2.00/Pro-user/month). Voice and full essay scoring stay Pro-only. **If free users ever reach voice or premium TTS, the model breaks.**

## 58. MVP Definition
The MVP is the complete core product, not a reduced one: calibrated scoring, real-time voice practice, spaced repetition, readiness tracking. "Done" = all §59 features built and tested, Phase 0 calibration gate passed, latency targets met under realistic load, GDPR verified, deploys with health-checked rollback working. Beta = private, 100–500 invited users, manual/waitlist access (no billing automation in MVP).

## 59. MVP Feature Scope (definitive)
JWT auth + RBAC · 4D CEFR profile · AI placement test · Daily Diagnostic micro-session · teaching personas (Companion free; Coach/Examiner Pro) · streaming LLM responses (SSE chat, WS voice; first token < 500 ms) · Writing Evaluation (async, calibrated, transparency shown) · Score Appeal flow · AIModelRun logging (all fields) · calibration drift monitor · SRS scheduler · Voice Agent (ASR + LLM + TTS, accent-relative, Socratic mode) · Exam Simulation (Writing + Speaking) · Readiness Engine (band + CI + daily delta) · Share Your Score card · PDF reports (Pro) · PWA offline mode · **per-user AI cost ceiling + rate limiting (enforced, tested).**

## 61. Implementation Phases — Solo Sequencing

> **CHANGED.** The original assumed a 4–6-person team running phases partly in parallel (18–25 weeks). Solo, phases run **sequentially**; calendar time is longer and that is expected. Build in this order; ship the calibration gate before any user-facing scoring.

| Phase | Focus | Solo scope notes |
|---|---|---|
| **0 · Calibration** | Collect graded essays, tune rubric prompts to Pearson ≥ 0.85, accent WER < 10%, store `v1.0-launch` baseline, GO/NO-GO. | Can run in background while building Phase 1; **gates all scoring.** |
| **1 · Core platform** | Auth/RBAC/GDPR erasure · 4D CEFR + placement pipeline · Writing eval (async queue, rubric, CEFR) · calibration transparency · score appeal · AIModelRun logging · drift monitor · SRS scheduler · personas · Daily micro-session (pre-gen off-peak) · SSE streaming · full Postgres schema · **Docker Compose stack on one box via Coolify/Dokploy** (replaces "K8s base + Helm charts"). | |
| **2 · Voice Agent** | WebSocket lifecycle + state machine · ASR (gpt-4o-mini-transcribe primary) with failover · accent routing · Socratic agent (max 3 turns) · WS LLM streaming · **TTS (OpenAI/Inworld primary; ElevenLabs Pro premium)** · persona-matched voice. Validate round-trip P95 < 2.5 s under realistic concurrency (dozens). | |
| **3 · Exam Simulation** | Attempt lifecycle, section-locked timed UI, 60s auto-save, async eval wired to Writing/Voice, appeal on result screen, Share card, Pro PDF report, calibration confidence indicator. | |
| **4 · Readiness + PWA Offline** | Readiness index + trend + CI + daily delta · ReadinessSnapshot · Service Worker offline detection · IndexedDB cache + TTL · sync manager + reconciliation · offline UX. | |

## 62. Acceptance Criteria (per phase — adjusted)
- **Phase 0:** Pearson ≥ 0.85 all exam types; WER < 10% all accents; baseline stored; GO/NO-GO signed.
- **Phase 1:** auth end-to-end; writing eval scored result < 6 s P95; SRS schedule correct per learner; chat first token < 500 ms; appeal resolves < 60 s; all entities populate correctly; **stack deploys and rolls back via health check.**
- **Phase 2:** voice round-trip P95 < 2.5 s under realistic concurrent sessions; ASR failover tested; accent-relative scoring validated per accent; Socratic activates on weakness; persona voice distinguishable; **TTS cost-per-minute within budget on the chosen primary provider.**
- **Phase 3:** full exam lifecycle; timer + auto-save on connectivity drop verified; appeal correct; Share card renders on WhatsApp/LinkedIn; Pro PDF downloads.
- **Phase 4:** readiness matches reference fixture; CI widens with low session count; daily delta shows after session; offline lessons accessible with AI disabled; sync completes on reconnect; IndexedDB TTL tested.

## 63. Risk Register (updated for this edition)

| Risk | L | I | Mitigation |
|---|---|---|---|
| Calibration fails to reach 0.85 | H | H | Rubric prompt tuning across Phase 0 iterations; if unmet, delay launch (don't cancel). |
| Voice round-trip > 2.5 s P95 | M | H | Parallel ASR + LLM; cheaper/faster TTS primary; sentence-stream TTS; synchronous fallback if needed. |
| LLM/TTS provider outage | M | H | Multi-provider fallback via abstraction layer; circuit breaker at Orchestrator; voice degrades to feedback-only; non-AI features stay up. |
| **AI cost overrun (free-tier abuse / wrong TTS)** | **M** | **H** | **Hard freemium gating + per-user ceiling + cheap-provider primaries (§55). The dominant financial risk for a solo operator.** |
| Single-box failure | M | M | Nightly backups + documented ~few-hour restore; vertical resize headroom; scale-out path ready. |
| SRS pre-gen cron fails silently | M | M | Alert on success rate < 99%; on-demand generation < 2 s as cold-miss fallback. |
| Streaming SSE drops | M | M | Client 2 s reconnect then sync fallback. |
| Audio storage cost creep | L | M | 90-day lifecycle; reduce to 30 days if exceeded; opt-in extension. |
| GDPR erasure delay | L | H | Synchronous PII deletion in one transaction; audio deleted within 24 h via job; confirmation email. |
| **Solo bandwidth / bus factor** | **M** | **M** | **Boring tech, minimal moving parts, IaC in Git, documented runbooks; the whole point of this edition is to keep ops survivable for one person.** |

## 64. Pre-Launch Checklist (revised — no item waived without written sign-off)

**AI quality & calibration:** correlation ≥ 0.85 all exam types (non-negotiable) · WER < 10% per accent · accent-relative scoring shows no systematic bias > 0.2 bands · CEFR classification ≥ 90% on holdout · `calibration_version='v1.0-launch'` stored and referenced.

**Performance:** voice round-trip P95 < 2.5 s under realistic concurrency · streaming first token P95 < 500 ms · essay scoring P95 < 6 s under concurrent submissions · dashboard < 500 ms with Redis cache · 5xx rate < 0.5% under expected peak.

**Feature completeness:** score appeal end-to-end < 60 s · SRS intervals correct vs fixtures · Daily Diagnostic cron at off-peak over 3 nights · 4D placement profiles correct on 20 diverse samples · PWA offline functional on iOS/Android · Share card renders on WhatsApp/LinkedIn/X · personas distinguishable on identical input.

**Infrastructure & security (revised):** **DB backup restore drill completed** (app functional post-restore) · **per-user AI cost ceiling + rate limiting enforced and tested** · Trivy + gitleaks clean · **health-checked rolling deploy with automatic rollback validated (rollback < 2 min)** · GDPR erasure end-to-end (PII removed, audio deleted, AIModelRun anonymized, confirmation sent) · Cloudflare WAF active, only 443 + locked SSH exposed, DBs bound to localhost.

> **Removed checklist items:** Kubernetes HPA scaling validation, mTLS between service pairs, canary deployment validation — none apply to a single-host monolith.

## 65. Post-MVP Roadmap (sequence preserved; cost-optimizations promoted)
- **Listening module** (next) — TTS-generated passages (using the chosen cost-effective TTS primary) + AI comprehension questions; activates `cefr_listening`; brings exam coverage to 75%.
- **Full analytics dashboard** — longitudinal charts, percentile cohort position, per-dimension readiness breakdown, monthly PDF, AI study-plan recommendations.
- **Institution dashboard (B2B)** — class CEFR radar, cohort readiness, top-3 weak areas, consent-gated drill-down, bulk export, volume-license management, `institution_admin` role.
- **Reading module** — AI-generated passages + question variety; activates `cefr_reading`; full four-skill simulation.
- **Gamification & referral** — XP/levels, opt-in leaderboards, referral (Pro days), Share→referral attribution.
- **Scale & multi-language + advanced cost optimization** — **fine-tuned small/open models for grammar + CEFR classification (40–60% inference saving), hybrid hosting (internal mid-tier, external high-tier only)**, Spanish DELE + TCF (fr-CA), Stripe billing automation, enterprise SLA dashboards, React Native app. *(Several of these cost optimizations are pulled forward conceptually into §55; the model retraining infrastructure remains post-MVP.)*

## 66. Strategic Success Criteria — 12-Month Targets

| Metric | Target | Primary driver |
|---|---|---|
| Registered users | 10,000+ | Organic + Share Your Score + referral |
| Pro subscribers | 1,500+ | 8%+ conversion; exam proximity drives upgrade |
| 90-day retention | 45%+ | Daily Diagnostic SRS loop |
| Daily return rate | 30%+ | 5-minute daily habit anchor |
| Exam skill coverage | 3 of 4 (Writing, Speaking, Listening) | Listening module next |
| Writing calibration | ≥ 0.85 sustained, no drift events | Monthly recalibration check |
| Institution clients | 3–5 pilots | B2B dashboard post-MVP |
| **AI cost per Pro user** | **< $2.00 / active Pro user / month** | **Model routing + caching + cheap-provider primaries + SRS pre-gen (§55)** |
| Share card virality | 200+ monthly shares → tracked signups | Share→referral pipeline |
| Infrastructure cost | **~$15–25/month at launch scale** | Single-box modular monolith (Part VIII) |

---

## Closing Note
This Solo-Dev edition is the single source of truth for building and operating LinguaMentor as one developer. The product strategy, AI engine design, data model, and — above all — the **calibration gate (Pearson ≥ 0.85)** are carried over from the original and remain non-negotiable. What changed is the cost of building and running the thing: thirteen services became three, a Kubernetes platform became one well-managed box, and the most expensive provider in the document was demoted to an optional premium. The result is intended to serve thousands of real users robustly while staying within reach of a single operator on a minimal budget. Any change to scope, architecture, or approach should be reflected here before it reaches code; version history lives in the repository alongside the codebase.
