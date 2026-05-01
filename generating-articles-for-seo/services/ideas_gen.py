"""Ideas generation service: uses Claude to generate article ideas for Oki-Toki blog."""
import json
import logging
import uuid

from services.anthropic_client import get_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ти SEO-спеціаліст для блогу компанії Oki-Toki — хмарного сервісу для колл-центрів. "
    "Генеруй ідеї статей українською мовою. "
    "Кожна ідея повинна бути релевантною для цільової аудиторії: керівники колл-центрів, "
    "менеджери з продажів, IT-директори.\n\n"
    "Теми: CRM, IP-телефонія, автоматизація колл-центру, KPI операторів, "
    "скрипти продажів, IVR, SIP, VoIP, інтеграції, аналітика дзвінків, "
    "якість обслуговування, навчання операторів, workforce management.\n\n"
    "Відповідай ТІЛЬКИ валідним JSON масивом."
)


async def generate_ideas(count: int = 10) -> list[dict]:
    """Generate article ideas using Claude.

    Returns list of idea dicts with: title, description, keywords, outline, priority_score
    """
    client = get_client()

    user_prompt = (
        f"Згенеруй {count} унікальних ідей для SEO-статей блогу Oki-Toki.\n\n"
        "Для кожної ідеї верни JSON об'єкт з полями:\n"
        '- "title": заголовок статті (до 80 символів)\n'
        '- "description": короткий опис теми (1-2 речення)\n'
        '- "keywords": масив з 5-7 ключових слів, СТРОГО релевантних темі статті.\n'
        '  Ключові слова мають бути конкретними пошуковими запитами (не загальні слова).\n'
        '  Наприклад для теми про IVR: ["IVR меню для колл-центру", "налаштування голосового меню", '
        '"автовідповідач для бізнесу", "IVR система Oki-Toki", "інтерактивне голосове меню"]\n'
        '- "outline": масив з 5-7 рядків — заголовки розділів майбутньої статті (план)\n'
        '  Кожен розділ — конкретна підтема, яка буде розкрита в статті.\n'
        '  Наприклад: ["Що таке IVR і як воно працює", "Переваги IVR для бізнесу", '
        '"Кроки налаштування IVR в Oki-Toki", "Типові помилки при налаштуванні IVR"]\n'
        '- "priority_score": число від 60 до 100 (оцінка SEO-пріоритетності теми)\n\n'
        "Відповідь — ТІЛЬКИ JSON масив без markdown."
    )

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=6000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

        ideas_raw = json.loads(raw)

        ideas = []
        for item in ideas_raw[:count]:
            ideas.append({
                "id": str(uuid.uuid4()),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "type": "article",
                "status": "pending",
                "source": "ai_generator",
                "keywords": item.get("keywords", []),
                "outline": item.get("outline", []),
                "priority_score": item.get("priority_score", 75),
            })

        logger.info(f"[Ideas Gen] Generated {len(ideas)} ideas")
        return ideas

    except Exception as e:
        logger.error(f"[Ideas Gen] Error: {e}")
        return []
