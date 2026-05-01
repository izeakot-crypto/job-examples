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

    Returns list of idea dicts with: title, description, keywords, priority_score, outline
    """
    client = get_client()

    user_prompt = (
        f"Згенеруй {count} унікальних ідей для SEO-статей блогу Oki-Toki.\n\n"
        "Для кожної ідеї верни JSON об'єкт з полями:\n"
        '- "title": заголовок статті (до 80 символів, природний, без кліше)\n'
        '- "description": короткий опис (1-2 речення — про що стаття)\n'
        '- "keywords": масив з 4-6 РЕАЛЬНИХ пошукових запитів українською, які б людина вводила у Google. '
        'Не загальні слова ("crm", "колл-центр"), а конкретні фрази: "як налаштувати crm для колл-центру", '
        '"порівняння ip-телефонії для бізнесу", "як знизити abandonment rate"\n'
        '- "outline": план статті — 2-4 речення що розкривають: про що стаття, навіщо вона читачеві, '
        'які головні розділи/пункти будуть в ній. НЕ список заголовків, а зв\'язний текст-анотація '
        '(приклад: "Покроковий гайд по інтеграції CRM з Oki-Toki. Читач дізнається як налаштувати '
        'webhook, які поля синхронізувати між системами, і як уникнути дублікатів контактів. '
        'Включено приклади для amoCRM і Bitrix24.")\n'
        '- "priority_score": число від 60 до 100 (оцінка пріоритетності за пошуковим попитом)\n\n'
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
                "outline": item.get("outline", ""),
                "priority_score": item.get("priority_score", 75),
            })

        logger.info(f"[Ideas Gen] Generated {len(ideas)} ideas")
        return ideas

    except Exception as e:
        logger.error(f"[Ideas Gen] Error: {e}")
        return []
