"""
WER (Word Error Rate) computation engine for ASR validation.

WER = (Substitutions + Insertions + Deletions) / N
where N = total words in the reference transcript.

Uses dynamic programming (Levenshtein distance) for optimal alignment
between reference and hypothesis word sequences — the industry standard
approach per ITU-T P.10/G.100 and NIST speech evaluation methodology.

Text normalisation is applied before computation per WER best practice:
- Lowercase conversion
- Punctuation removal (except apostrophes in contractions)
- Number normalisation (optional, disabled by default)

Reference: https://docs.speechmatics.com/speech-to-text/accuracy-benchmarking
"""

import logging
import re
import uuid as uuid_module
from dataclasses import dataclass

import asyncpg

logger = logging.getLogger(__name__)

# Gate: WER must be below this threshold for all accent targets
WER_THRESHOLD = 0.10


@dataclass
class WERResult:
    """WER computation result for a single reference/hypothesis pair."""
    reference:      str
    hypothesis:     str
    wer:            float
    substitutions:  int
    insertions:     int
    deletions:      int
    ref_word_count: int


@dataclass
class AccentWERReport:
    """WER results for one accent target across all its clips."""
    accent_target:  str
    wer_mean:       float
    wer_min:        float
    wer_max:        float
    clip_count:     int
    passed:         bool
    worst_clips:    list[dict]  # top 3 worst WER clips for debugging


@dataclass
class WERValidationReport:
    """Complete WER validation report for one run."""
    run_id:         str
    asr_model:      str
    accents:        list[AccentWERReport]
    passed_overall: bool
    verdict:        str

    def summary(self) -> str:
        lines = [
            f"\n{'='*65}",
            f"  WER VALIDATION REPORT",
            f"  Run: {self.run_id[:8]}...",
            f"  ASR Model: {self.asr_model}",
            f"  Threshold: WER < {WER_THRESHOLD:.0%}",
            f"{'='*65}",
        ]
        for a in self.accents:
            status = "✅ PASS" if a.passed else "❌ FAIL"
            lines.append(
                f"{status}  {a.accent_target:<8}  "
                f"WER={a.wer_mean:.4f} ({a.wer_mean:.1%})  "
                f"n={a.clip_count}"
            )
        lines += [
            f"{'─'*65}",
            f"  VERDICT: {self.verdict}",
            f"{'='*65}",
        ]
        return "\n".join(lines)


def normalise_text(text: str) -> str:
    """
    Normalises text before WER computation.

    Per WER best practice:
    - Lowercase all text
    - Remove punctuation except apostrophes in contractions
    - Collapse multiple spaces
    - Strip leading/trailing whitespace

    This ensures 'Hello, world.' and 'hello world' are treated
    identically — punctuation differences should not count as errors.
    """
    # Lowercase
    text = text.lower()
    # Remove punctuation except apostrophes (don't → don t would be wrong)
    text = re.sub(r"[^\w\s']", "", text)
    # Collapse multiple whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compute_wer(reference: str, hypothesis: str) -> WERResult:
    """
    Computes WER between reference and hypothesis using
    Levenshtein (edit) distance on word sequences.

    This is the standard WER computation used by NIST, Speechmatics,
    and all major ASR benchmarks. Dynamic programming finds the
    minimum number of word-level edits required to transform the
    hypothesis into the reference.

    Args:
        reference:  Human-produced ground truth transcript (normalised)
        hypothesis: ASR system output (normalised)

    Returns:
        WERResult with WER value and error breakdown
    """
    ref_words  = normalise_text(reference).split()
    hyp_words  = normalise_text(hypothesis).split()

    n = len(ref_words)
    m = len(hyp_words)

    if n == 0:
        # Empty reference — undefined WER, return 0 to avoid division by zero
        logger.warning("Empty reference text — WER undefined, returning 0.0")
        return WERResult(
            reference=reference, hypothesis=hypothesis,
            wer=0.0, substitutions=0, insertions=0, deletions=0,
            ref_word_count=0
        )

    # Dynamic programming table
    # dp[i][j] = min edits to align ref[:i] with hyp[:j]
    # Also track edit type for error breakdown
    dp = [[0] * (m + 1) for _ in range(n + 1)]

    # Initialise: aligning with empty sequence requires i deletions / j insertions
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j

    # Fill DP table
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]          # correct — no edit
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],      # deletion  (ref word not in hyp)
                    dp[i][j - 1],      # insertion (hyp word not in ref)
                    dp[i - 1][j - 1],  # substitution
                )

    # Backtrack to count error types
    substitutions = insertions = deletions = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref_words[i - 1] == hyp_words[j - 1]:
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            substitutions += 1
            i -= 1
            j -= 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + 1:
            insertions += 1
            j -= 1
        else:
            deletions += 1
            i -= 1

    total_errors = substitutions + insertions + deletions
    wer = total_errors / n

    return WERResult(
        reference=reference,
        hypothesis=hypothesis,
        wer=round(wer, 4),
        substitutions=substitutions,
        insertions=insertions,
        deletions=deletions,
        ref_word_count=n,
    )


async def compute_run_wer(
    conn: asyncpg.Connection,
    run_id: str,
) -> WERValidationReport:
    """
    Computes aggregated WER per accent target for a completed run.

    Fetches all transcription results for the run, groups by accent,
    computes mean WER per accent, checks against threshold.
    """
    rows = await conn.fetch(
        """
        SELECT
            s.accent_target,
            r.wer,
            r.substitutions,
            r.insertions,
            r.deletions,
            s.reference_text,
            r.hypothesis_text,
            s.id::text AS sample_id
        FROM linguamentor.wer_transcription_results r
        JOIN linguamentor.wer_audio_samples s ON s.id = r.sample_id
        WHERE r.run_id = $1
        ORDER BY s.accent_target, r.wer DESC
        """,
        uuid_module.UUID(run_id),
    )

    if not rows:
        raise ValueError(
            f"No transcription results found for run {run_id}. "
            f"Ensure ASR scoring completed before running WER computation."
        )

    # Get run metadata
    run_row = await conn.fetchrow(
        "SELECT asr_model FROM linguamentor.wer_validation_runs WHERE id = $1",
        uuid_module.UUID(run_id),
    )
    asr_model = run_row["asr_model"] if run_row else "unknown"

    # Group by accent target
    accent_data: dict[str, list[float]] = {}
    accent_clips: dict[str, list[dict]] = {}

    for row in rows:
        accent = row["accent_target"]
        if accent not in accent_data:
            accent_data[accent]  = []
            accent_clips[accent] = []
        accent_data[accent].append(float(row["wer"]))
        accent_clips[accent].append({
            "sample_id":    row["sample_id"],
            "wer":          float(row["wer"]),
            "reference":    row["reference_text"][:100],
            "hypothesis":   row["hypothesis_text"][:100],
        })

    accent_reports = []
    all_passed     = True

    for accent, wer_values in accent_data.items():
        n        = len(wer_values)
        mean_wer = sum(wer_values) / n
        passed   = mean_wer < WER_THRESHOLD

        if not passed:
            all_passed = False

        # Top 3 worst clips for debugging
        worst = sorted(
            accent_clips[accent],
            key=lambda x: x["wer"],
            reverse=True
        )[:3]

        accent_reports.append(AccentWERReport(
            accent_target=accent,
            wer_mean=round(mean_wer, 4),
            wer_min=round(min(wer_values), 4),
            wer_max=round(max(wer_values), 4),
            clip_count=n,
            passed=passed,
            worst_clips=worst,
        ))

    # Update validation run with results
    wer_by_accent = {r.accent_target: r.wer_mean for r in accent_reports}

    await conn.execute(
        """
        UPDATE linguamentor.wer_validation_runs SET
            wer_en_us        = $1,
            wer_en_gb        = $2,
            wer_fr_fr        = $3,
            wer_fr_ca        = $4,
            passed_threshold = $5,
            completed_at     = NOW()
        WHERE id = $6
        """,
        wer_by_accent.get("en-US"),
        wer_by_accent.get("en-GB"),
        wer_by_accent.get("fr-FR"),
        wer_by_accent.get("fr-CA"),
        all_passed,
        uuid_module.UUID(run_id),
    )

    verdict = (
        "✅ PASSED — All accent targets below 10% WER. Ready for Go/No-Go."
        if all_passed else
        "❌ FAILED — One or more accent targets exceed 10% WER threshold."
    )

    report = WERValidationReport(
        run_id=run_id,
        asr_model=asr_model,
        accents=accent_reports,
        passed_overall=all_passed,
        verdict=verdict,
    )

    logger.info(report.summary())
    return report


async def store_wer_baseline(
    conn: asyncpg.Connection,
    run_id: str,
    report: WERValidationReport,
    approved_by: str,
    validation_version: str = "v1.0-launch",
) -> str:
    """
    Stores the immutable WER baseline after Go/No-Go approval.
    Only callable when all accent targets have passed threshold.
    """
    if not report.passed_overall:
        raise ValueError(
            "Cannot store WER baseline — not all accent targets passed. "
            "All four accent targets must achieve WER < 10%."
        )

    clips_count = await conn.fetchval(
        "SELECT clips_scored FROM linguamentor.wer_validation_runs WHERE id = $1",
        uuid_module.UUID(run_id),
    )

    wer_by_accent = {r.accent_target: r.wer_mean for r in report.accents}

    await conn.execute(
        """
        INSERT INTO linguamentor.wer_baseline (
            id, validation_version, run_id,
            wer_en_us, wer_en_gb, wer_fr_fr, wer_fr_ca,
            clips_count, asr_model, approved_by, approved_at
        ) VALUES (
            uuid_generate_v4(), $1, $2,
            $3, $4, $5, $6,
            $7, $8, $9, NOW()
        )
        """,
        validation_version,
        uuid_module.UUID(run_id),
        wer_by_accent.get("en-US", 0),
        wer_by_accent.get("en-GB", 0),
        wer_by_accent.get("fr-FR", 0),
        wer_by_accent.get("fr-CA", 0),
        clips_count,
        report.asr_model,
        approved_by,
    )

    logger.info(
        f"✅ WER baseline stored: {validation_version} | "
        f"asr_model={report.asr_model} | "
        f"approved_by={approved_by}"
    )
    return validation_version
