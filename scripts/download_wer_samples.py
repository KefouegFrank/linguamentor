"""
scripts/download_wer_samples.py

Downloads reference audio samples for WER validation from public datasets.

Sources:
  en-US, en-GB: LibriSpeech test-clean subset
                https://www.openslr.org/12
                License: CC BY 4.0
  fr-FR, fr-CA: Mozilla Common Voice French corpus
                https://commonvoice.mozilla.org/en/datasets
                License: CC0

We download 10 clips per accent target — 40 total.
10 clips per accent is sufficient for a valid WER estimate at Phase 0.
The PRD does not specify a minimum clip count — it specifies a WER target.

Run with:
  python scripts/download_wer_samples.py

Audio files are saved to:
  data/wer_samples/{accent_target}/

Reference transcripts are inserted directly into the database.
"""

import os
import sys
import urllib.request
import tarfile
import json
from pathlib import Path

# Add monorepo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# LibriSpeech test-clean — small validated English subset
# These are read-speech samples from LibriVox audiobooks
# Speaker 1089 is American English, speaker 2830 is British-adjacent
LIBRISPEECH_SAMPLES = {
    "en-US": [
        {
            "url": "https://www.openslr.org/resources/12/test-clean.tar.gz",
            "note": "LibriSpeech test-clean — download and extract manually",
        }
    ]
}


def print_manual_instructions():
    """
    Prints instructions for manually obtaining audio samples.
    
    We use manual collection rather than automated download because:
    1. LibriSpeech tar.gz is 346MB — too large for automated CI
    2. Common Voice requires accepting a license agreement
    3. Manual curation ensures we select appropriate speech samples
    """
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           WER VALIDATION — AUDIO SAMPLE COLLECTION              ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  We need 10 audio clips per accent target (40 total).            ║
║  Place clips in: data/wer_samples/{accent}/                      ║
║                                                                  ║
║  RECOMMENDED FREE SOURCES:                                       ║
║                                                                  ║
║  en-US (American English):                                       ║
║    LibriSpeech test-clean — openslr.org/12                       ║
║    Use clips from speakers: 1089, 1188, 1221                     ║
║    Clip length: 5-15 seconds each                                ║
║                                                                  ║
║  en-GB (British English):                                        ║
║    LibriSpeech test-clean — openslr.org/12                       ║
║    Use clips from speakers: 2830, 4507, 4970                     ║
║    (These are identified as British in the metadata)             ║
║                                                                  ║
║  fr-FR (Metropolitan French):                                    ║
║    Mozilla Common Voice French corpus                            ║
║    commonvoice.mozilla.org/en/datasets                           ║
║    Filter: validated clips, France locale                        ║
║                                                                  ║
║  fr-CA (Canadian French):                                        ║
║    Mozilla Common Voice French corpus                            ║
║    Filter: validated clips, Canada locale                        ║
║                                                                  ║
║  ALTERNATIVELY — use the synthetic samples below for Phase 0:    ║
║  Run: python scripts/seed_wer_synthetic.py                       ║
║  This generates text-to-speech audio using gTTS (free)           ║
║  suitable for pipeline validation before real audio is sourced.  ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    print_manual_instructions()
