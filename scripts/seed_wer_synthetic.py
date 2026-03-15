"""
Generates synthetic audio samples for WER validation pipeline testing.

Uses Google Text-to-Speech (gTTS) to convert known reference texts
to speech, then stores both the audio and reference transcripts in
the database. This validates the full WER pipeline without requiring
real recorded audio samples.

IMPORTANT: Synthetic TTS audio will produce artificially low WER
(typically 1-3%) because TTS produces clean, accent-free speech.
This is intentional for pipeline testing — it validates mechanics,
not real-world ASR performance. Real accent-specific audio must be
collected before the Go/No-Go decision.

Run with:
  python scripts/seed_wer_synthetic.py

Requires: pip install gtts asyncpg python-dotenv
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

# Monorepo root on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# IELTS-style reference texts — realistic language exam content.
# These sentences cover the vocabulary range and complexity typical
# of IELTS Speaking Part 2 and Part 3 responses.
REFERENCE_SAMPLES = {
    "en-US": [
        "The development of renewable energy sources is essential for addressing climate change and reducing our dependence on fossil fuels.",
        "University education provides students with critical thinking skills and analytical abilities that are valuable throughout their careers.",
        "Many people believe that international travel broadens the mind by exposing individuals to different cultures and perspectives.",
        "The rapid advancement of artificial intelligence is transforming industries and creating both opportunities and challenges for society.",
        "Regular physical exercise has been shown to improve both physical health and mental wellbeing according to numerous scientific studies.",
        "The preservation of cultural heritage sites is important for maintaining a connection to our historical roots and national identity.",
        "Governments should invest more heavily in public transportation infrastructure to reduce traffic congestion in urban areas.",
        "The internet has fundamentally changed how people communicate access information and conduct business on a global scale.",
        "Environmental pollution poses serious threats to biodiversity and ecosystems that have taken millions of years to develop.",
        "Education systems should be adapted to prepare students for the rapidly changing demands of the modern workforce.",
    ],
    "en-GB": [
        "The National Health Service has provided universal healthcare to British citizens since its establishment in nineteen forty eight.",
        "British universities are renowned worldwide for their academic excellence and contribution to scientific research and innovation.",
        "The relationship between economic growth and environmental sustainability is one of the most pressing issues of our time.",
        "Public libraries play a crucial role in providing equal access to information and educational resources for all members of society.",
        "The influence of social media on young people's mental health and self-image is a matter of considerable public concern.",
        "Effective communication skills are increasingly valued by employers across all sectors of the modern economy.",
        "The conservation of natural habitats is vital for maintaining the biodiversity that underpins healthy ecosystems globally.",
        "Many researchers argue that early childhood education has a profound and lasting impact on cognitive development.",
        "The globalisation of trade has brought significant economic benefits but has also contributed to growing inequality.",
        "Urban planning decisions made today will have lasting consequences for the quality of life in our cities for generations.",
    ],
    "fr-FR": [
        "Le développement durable est devenu une priorité absolue pour les gouvernements et les entreprises du monde entier.",
        "L'éducation est le fondement sur lequel repose le progrès social et économique de toute société moderne.",
        "La protection de l'environnement nécessite une coopération internationale et des politiques ambitieuses à long terme.",
        "Les nouvelles technologies transforment profondément notre façon de travailler de communiquer et de nous divertir.",
        "La diversité culturelle est une richesse qui contribue à l'enrichissement mutuel des sociétés et des individus.",
        "Le système de santé français est considéré comme l'un des meilleurs au monde grâce à son accessibilité universelle.",
        "L'apprentissage des langues étrangères ouvre des portes professionnelles et favorise la compréhension interculturelle.",
        "Les inégalités sociales et économiques constituent un obstacle majeur au développement d'une société juste et équitable.",
        "La lecture régulière contribue au développement du vocabulaire et des capacités de réflexion analytique.",
        "Le changement climatique représente l'un des défis les plus importants auxquels l'humanité doit faire face aujourd'hui.",
    ],
    "fr-CA": [
        "Le Québec possède une culture et une identité distinctes qui enrichissent le tissu multiculturel du Canada.",
        "L'économie canadienne bénéficie d'une main-d'œuvre diversifiée et hautement qualifiée grâce à ses politiques d'immigration.",
        "La préservation de la langue française en Amérique du Nord est une priorité culturelle et politique importante.",
        "Les universités québécoises offrent une formation de qualité à des coûts relativement abordables pour les étudiants.",
        "Le système de garderies subventionnées au Québec a permis à davantage de parents de participer au marché du travail.",
        "La nature sauvage et les grands espaces canadiens attirent des touristes du monde entier chaque année.",
        "Les relations entre les communautés francophones et anglophones au Canada ont évolué considérablement au fil des décennies.",
        "L'innovation technologique et la recherche scientifique sont des moteurs essentiels de la compétitivité économique.",
        "Le bénévolat et l'engagement communautaire jouent un rôle fondamental dans le tissu social des villes canadiennes.",
        "La santé mentale est un enjeu de plus en plus reconnu dans les politiques de santé publique au Canada.",
    ],
}

# gTTS language codes and TLD for accent targeting
# gTTS uses TLD to select regional accent variants
GTTS_CONFIG = {
    "en-US": {"lang": "en", "tld": "com"},      # American English
    "en-GB": {"lang": "en", "tld": "co.uk"},    # British English
    "fr-FR": {"lang": "fr", "tld": "fr"},        # Metropolitan French
    "fr-CA": {"lang": "fr", "tld": "ca"},        # Canadian French
}


async def seed_synthetic_samples():
    """Generates TTS audio and seeds the database with samples."""
    import asyncpg
    from gtts import gTTS

    # Create audio output directory
    audio_dir = Path(__file__).parent.parent / "data" / "wer_samples"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Connect to database
    conn = await asyncpg.connect(
        host=os.getenv("LM_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("LM_DB_PORT", "5432")),
        database=os.getenv("LM_DB_NAME", "linguamentor"),
        user=os.getenv("LM_DB_USER", "lm_user"),
        password=os.getenv("LM_DB_PASSWORD", "lm_dev_password"),
    )

    try:
        # Clear existing synthetic samples
        await conn.execute(
            "DELETE FROM linguamentor.wer_audio_samples WHERE source = 'synthetic-tts'"
        )

        total_inserted = 0

        for accent, texts in REFERENCE_SAMPLES.items():
            accent_dir = audio_dir / accent
            accent_dir.mkdir(exist_ok=True)
            config = GTTS_CONFIG[accent]

            print(f"\nGenerating {len(texts)} clips for {accent}...")

            for i, text in enumerate(texts, 1):
                # Generate audio file
                filename = f"synthetic_{i:03d}.mp3"
                filepath = accent_dir / filename
                relative_path = f"{accent}/{filename}"

                print(f"  [{i}/{len(texts)}] Generating: {text[:60]}...")

                tts = gTTS(
                    text=text,
                    lang=config["lang"],
                    tld=config["tld"],
                    slow=False,
                )
                tts.save(str(filepath))

                # Estimate word count from reference text
                word_count = len(text.split())

                # Insert into database
                sample_id = str(uuid.uuid4())
                await conn.execute(
                    """
                    INSERT INTO linguamentor.wer_audio_samples (
                        id, accent_target, audio_path, reference_text,
                        source, word_count
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    uuid.UUID(sample_id),
                    accent,
                    relative_path,
                    text,
                    "synthetic-tts",
                    word_count,
                )
                total_inserted += 1

        print(f"\n✅ Seeded {total_inserted} synthetic audio samples")
        print(f"   Audio files: {audio_dir}")
        print(f"\n⚠️  These are synthetic TTS samples for pipeline testing.")
        print(f"   WER will be artificially low (~2-5%).")
        print(f"   Replace with real accent audio before Go/No-Go sign-off.")

        # Verify
        counts = await conn.fetch(
            """
            SELECT accent_target, COUNT(*) as count
            FROM linguamentor.wer_audio_samples
            WHERE source = 'synthetic-tts'
            GROUP BY accent_target
            ORDER BY accent_target
            """
        )
        print("\n   Database verification:")
        for row in counts:
            print(f"   {row['accent_target']}: {row['count']} clips")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_synthetic_samples())
