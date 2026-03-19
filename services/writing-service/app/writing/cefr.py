# Maps IELTS/TOEFL band scores to CEFR levels.
# Mapping source: British Council IELTS-CEFR correspondence table.
# PRD §7.1 — 4D CEFR profile, A1→C2 full mapping.

def band_to_cefr(band: float) -> str:
    """
    Maps an IELTS overall band score to CEFR level.

    IELTS ↔ CEFR official mapping (British Council):
      9.0       → C2
      8.0–8.5   → C1
      7.0–7.5   → C1  (lower C1)
      5.5–6.5   → B2
      4.0–5.0   → B1
      3.0–3.5   → A2
      0.0–2.5   → A1
    """
    if band >= 9.0:
        return "C2"
    elif band >= 8.0:
        return "C1"
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
        "C2": (9.0, 9.0),
        "C1": (7.0, 8.5),
        "B2": (5.5, 6.5),
        "B1": (4.0, 5.0),
        "A2": (3.0, 3.5),
        "A1": (0.0, 2.5),
    }.get(cefr, (0.0, 9.0))
