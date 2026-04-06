import numpy as np
import logging
from openai import OpenAI
from config import Config

logger = logging.getLogger(__name__)

client = OpenAI(api_key=Config.OPENAI_API_KEY)


def understand_and_check_query(query: str) -> dict:
    """
    Combined AI call: checks if query is product-related AND translates it.
    Returns {"related": bool, "translated": str}
    Single API call instead of 2 separate ones = ~1-2s saved per search.
    """
    prompt = f"""Είσαι βοηθός αναζήτησης προϊόντων συστημάτων ασφαλείας (κάμερες, συναγερμοί, πυρανίχνευση, access control, καταγραφικά, τροφοδοτικά, καλώδια, NVR, DVR κ.λπ.).

Ο χρήστης έγραψε: "{query}"

1. Αν η αναζήτηση ΔΕΝ σχετίζεται καθόλου με προϊόντα/εξοπλισμό ασφαλείας, απάντησε:
RELATED: NO

2. Αν σχετίζεται, μετέτρεψέ την σε τεχνικές λέξεις-κλειδιά στα αγγλικά και απάντησε:
RELATED: YES
KEYWORDS: [keywords here]

Παραδείγματα:
- "καμερα εξωτερικη 4mp" → RELATED: YES / KEYWORDS: ip camera 4mp outdoor
- "καλημέρα πώς είσαι" → RELATED: NO
- "πυρανιχνευση inim" → RELATED: YES / KEYWORDS: inim fire alarm detector
- "τι ώρα είναι" → RELATED: NO
- "τροφοδοτικο 12v" → RELATED: YES / KEYWORDS: power supply 12v
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.1,
        )

        answer = response.choices[0].message.content.strip()
        logger.info(f"AI response for '{query}': {answer}")

        if "RELATED: NO" in answer.upper():
            return {"related": False, "translated": query}

        # Extract keywords
        for line in answer.split("\n"):
            if "KEYWORDS:" in line.upper():
                keywords = line.split(":", 1)[1].strip().lower()
                if len(keywords) > 2:
                    return {"related": True, "translated": keywords}

        return {"related": True, "translated": query.lower()}

    except Exception as e:
        logger.error(f"AI understand_and_check error: {e}")
        return {"related": True, "translated": query.lower()}


def get_embedding(text: str) -> np.ndarray | None:
    """Generate embedding for a text string."""
    for attempt in range(3):
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return np.array(response.data[0].embedding, dtype=np.float64)
        except Exception as e:
            logger.warning(f"Embedding attempt {attempt + 1}/3 failed: {e}")

    return None


def ai_product_advisor(query: str, products: list) -> str | None:
    """AI advisor gives recommendation on top products."""
    if not products:
        return None

    product_list = "\n".join(
        [f"{p['factory_code']} - {p['description']}" for p in products[:5]]
    )

    prompt = f"""Είσαι τεχνικός σύμβουλος συστημάτων ασφαλείας.

Ο χρήστης αναζητά: {query}

Διαθέσιμα προϊόντα:
{product_list}

Δώσε σύντομη συμβουλή ποιο προϊόν είναι πιο κατάλληλο και γιατί.
Απάντησε σε 1-2 προτάσεις."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"AI advisor error: {e}")
        return None
