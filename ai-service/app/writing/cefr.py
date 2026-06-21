# IELTS band → CEFR mapping.
# Source: British Council official IELTS-CEFR correspondence table.
# Cambridge English Research Notes Issue 56 (2014), updated 2022.
#
# PRD §7.1 uses A1→C2 with C1+ as a sub-level for the adaptive engine.
# The 7.0-7.5 vs 8.0-8.5 distinction matters for SRS scheduling —
# a C1 learner at Band 7.0 needs different practice content than
# a C1 learner at Band 8.5 who is approaching C2.

def band_to_cefr(band: float) -> str:
    """
    Maps IELTS overall band score to CEFR level.

    British Council official mapping:
      9.0       → C2    (mastery — native-equivalent)
      8.5       → C2    (proficient — near-native)
      8.0       → C1+   (advanced upper — strong C1)
      7.0–7.5   → C1    (advanced — standard C1)
      5.5–6.5   → B2    (upper intermediate)
      4.0–5.0   → B1    (intermediate)
      3.0–3.5   → A2    (elementary)
      0.0–2.5   → A1    (beginner)

    Note: C1+ is a LinguaMentor sub-level used by the adaptive engine
    to distinguish high-C1 learners from standard-C1 learners.
    It is not an official CEFR designation.
    """
    if band >= 8.5:
        return "C2"
    elif band >= 8.0:
        return "C1+"   # Upper C1 — distinct content in adaptive engine
    elif band >= 7.0:
        return "C1"
    elif band >= 5.5:
        return "B2"
    elif band >= 4.0:
        return "B1"
    elif band >= 3.0:
        return "A2"
    else:
        return "A1"


def cefr_to_band_range(cefr: str) -> tuple[float, float]:
    """
    Returns the (min, max) IELTS band range for a CEFR level.
    Used by the readiness engine for projection confidence intervals.
    """
    return {
        "C2":  (8.5, 9.0),
        "C1+": (8.0, 8.5),
        "C1":  (7.0, 7.5),
        "B2":  (5.5, 6.5),
        "B1":  (4.0, 5.0),
        "A2":  (3.0, 3.5),
        "A1":  (0.0, 2.5),
    }.get(cefr, (0.0, 9.0))
