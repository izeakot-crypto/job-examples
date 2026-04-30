import logging
from dataclasses import dataclass

import anthropic
import httpx

from config import settings, CLAUDE_MODELS, CLAUDE_MAX_TOKENS

logger = logging.getLogger(__name__)

_client = None


# --- Ollama-compatible wrapper that mimics Anthropic SDK interface ---

@dataclass
class _TextBlock:
    type: str
    text: str


@dataclass
class _OllamaResponse:
    content: list


class _OllamaMessages:
    """Mimics anthropic.AsyncAnthropic().messages interface."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def create(self, *, model: str = "", max_tokens: int = 4096,
                     messages: list, system: str = None, **kwargs) -> _OllamaResponse:
        ollama_messages = []
        if system:
            ollama_messages.append({"role": "system", "content": system})
        for msg in messages:
            ollama_messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=600.0) as http:
            resp = await http.post(
                f"{self.base_url}/api/chat",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        text = data.get("message", {}).get("content", "")
        logger.info(f"[Ollama] model={self.model}, prompt_tokens={data.get('prompt_eval_count', '?')}, "
                     f"eval_tokens={data.get('eval_count', '?')}")
        return _OllamaResponse(content=[_TextBlock(type="text", text=text)])


class _OllamaClient:
    """Drop-in replacement for anthropic.AsyncAnthropic."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.messages = _OllamaMessages(base_url, api_key, model)


def get_client():
    global _client
    if _client is None:
        if settings.ollama_base_url:
            logger.info(f"[LLM] Using Ollama API: {settings.ollama_base_url}, model={settings.ollama_model}")
            _client = _OllamaClient(settings.ollama_base_url, settings.ollama_api_key, settings.ollama_model)
        else:
            kwargs = {
                "api_key": settings.anthropic_api_key,
                "timeout": 300.0,
            }
            if settings.anthropic_base_url:
                kwargs["base_url"] = settings.anthropic_base_url
            _client = anthropic.AsyncAnthropic(**kwargs)
    return _client


SYSTEM_MESSAGES = {
    "en": (
        "You are an expert SEO copywriter for Oki-Toki cloud contact center. "
        "You MUST respond with valid JSON only containing SEO_HEADING and ARTICLE_HTML keys. "
        "NEVER output plain text — ONLY JSON. Minimum 12,000 characters in ARTICLE_HTML."
    ),
    "ru": "Ты SEO копирайтер. Пиши только JSON. Минимум 12000 символов.",
    "pl": (
        "Jesteś copywriterem SEO. MUSISZ: "
        "1. ZAWSZE odpowiadać poprawnym JSON z SEO_HEADING i ARTICLE_HTML "
        "2. ZAWSZE pisać minimum 12,000 znaków w ARTICLE_HTML "
        "3. ZAWSZE używać prawidłowych tagów HTML (h1, h2, h3, p, ul, li, strong) "
        "4. NIGDY nie wyświetlać zwykłego tekstu - TYLKO JSON"
    ),
    "es": (
        "Eres un redactor SEO experto para Oki-Toki, un centro de contacto en la nube. "
        "DEBES responder SOLO con JSON válido que contenga las claves SEO_HEADING y ARTICLE_HTML. "
        "NUNCA escribas texto plano — SOLO JSON. Mínimo 12.000 caracteres en ARTICLE_HTML."
    ),
    "tr": (
        "Oki-Toki bulut iletişim merkezi için uzman bir SEO metin yazarısınız. "
        "YALNIZCA SEO_HEADING ve ARTICLE_HTML anahtarlarını içeren geçerli JSON ile yanıt vermelisiniz. "
        "ASLA düz metin yazmayın — YALNIZCA JSON. ARTICLE_HTML en az 12.000 karakter olmalıdır."
    ),
    "uk": (
        "Ти досвідчений SEO-копірайтер, який пише статті для Oki-Toti — хмарного контакт-центру. "
        "Твоя задача — писати розгорнуті, корисні статті, які допомагають читачам зрозуміти тему "
        "та вирішити їхні проблеми. Пиши так, ніби пояснюєш колезі — просто, зрозуміло, але професійно."
    ),
}

PROMPTS = {
    "en": """You are an SEO copywriter. You MUST write LONG articles.

CRITICAL: Your article MUST be 12,000-18,000 characters.
If you write less than 12,000 characters, you have FAILED.

Write detailed paragraphs with examples, explanations, and practical advice.
Never write short responses. Always expand and elaborate.
Write a LONG SEO article in English (minimum 12,000 characters).

Topic (translate from Ukrainian): {title}
Keywords (translate from Ukrainian): {keywords}

YOUR ARTICLE MUST HAVE:
- EXACTLY 1x <h1> title (ONLY ONE h1, never more!)
- 10-12x <h2> sections
- Under each <h2>: 4-5 paragraphs of 50-80 words EACH
- MANDATORY: at least 3 bullet lists using <ul><li>...</li></ul>
- MANDATORY: use <strong> for key terms (at least 10 times)
- Mention Oki-Toki platform 5-6 times naturally
- MANDATORY: mention the main keyword from Keywords at least 6 times naturally throughout the text
- MANDATORY: use transition words (however, therefore, moreover, furthermore, in addition, as a result, for example, in contrast, consequently, finally) — at least 15 times total
- MANDATORY: include 2-3 outbound links to real authoritative sources (Wikipedia, industry sites) using <a href="URL" target="_blank">anchor text</a>
- Total: 12,000-18,000 characters

REMEMBER:
- Translate the topic to English
- Write MINIMUM 12,000 characters
- If shorter - you FAILED
- ONLY ONE <h1> tag allowed!

HTML tags: <h1>, <h2>, <h3>, <p>, <ul>, <li>, <strong>
NO: <div>, <span>, <br>

JSON response only:
{{
  "SEO_HEADING": "English title",
  "ARTICLE_HTML": "<h1>...</h1>..."
}}

NOW WRITE A VERY LONG DETAILED ARTICLE!""",

    "ru": """ТЫ ДОЛЖЕН СОБЛЮДАТЬ ЭТИ ПРАВИЛА ТОЧНО:

ПРАВИЛО 1 - ФОРМАТ ВЫВОДА:
Твой ответ ДОЛЖЕН быть ТОЛЬКО этой JSON структурой:
{{
  "result": true,
  "SEO_HEADING": "Твой SEO заголовок здесь",
  "ARTICLE_HTML": "<h1>Заголовок</h1><h2>Секция 1</h2><p>Контент...</p>..."
}}

ПРАВИЛО 2 - МИНИМАЛЬНАЯ ДЛИНА (КРИТИЧНО!):
- Поле ARTICLE_HTML ДОЛЖНО содержать МИНИМУМ 12,000 символов
- Если твоя статья короче 12,000 символов = ТЫ ПРОВАЛИЛСЯ
- Пиши ДЛИННЫЕ детальные абзацы с примерами

ПРАВИЛО 3 - ТРЕБОВАНИЯ К КОНТЕНТУ:
Тема (переведи на русский): {title}
Ключевые слова: {keywords}

Нужная структура:
- РОВНО 1x <h1> (ТОЛЬКО ОДИН h1, никогда больше!)
- 10-12x <h2> секций
- Под каждым <h2>: 4-5 абзацев <p>
- Каждый <p>: минимум 50-80 слов
- Упомяни Oki-Toki 5-6 раз
- ОБЯЗАТЕЛЬНО: упоминай главное ключевое слово из Keywords минимум 6 раз естественно по всему тексту
- ОБЯЗАТЕЛЬНО: используй слова-связки (однако, поэтому, более того, кроме того, в результате, например, следовательно, наконец, таким образом, в то время как) — минимум 15 раз
- ОБЯЗАТЕЛЬНО: добавь 2-3 ссылки на реальные авторитетные источники (Wikipedia, отраслевые сайты) в формате <a href="URL" target="_blank">текст ссылки</a>

⚠️ КРИТИЧЕСКОЕ ПРАВИЛО - HTML СПИСКИ (НЕ ОБСУЖДАЕТСЯ):
Твоя статья ДОЛЖНА содержать МИНИМУМ 3 маркированных списка с тегами <ul> и <li>.
Если в статье НЕТ хотя бы 3 блоков <ul><li>...</li></ul>, ответ будет ОТКЛОНЁН.

Пример обязательного списка:
<ul><li>Первый пункт списка</li><li>Второй пункт</li><li>Третий пункт</li></ul>

Каждый список должен содержать 3-6 элементов <li>. Распредели списки по разным секциям <h2>.
ТАКЖЕ ОБЯЗАТЕЛЬНО: используй <strong> для ключевых терминов (минимум 10 раз).

ПРАВИЛО 4 - ТОЛЬКО HTML ТЕГИ:
Используй ТОЛЬКО: <h1>, <h2>, <h3>, <p>, <ul>, <li>, <strong>
НЕТ: <div>, <span>, <br>, <article>, <section>
ТОЛЬКО ОДИН тег <h1>!

ТЕПЕРЬ НАПИШИ СТАТЬЮ НА РУССКОМ. ПОМНИ: МИНИМУМ 12,000 СИМВОЛОВ!""",

    "pl": """MUSISZ PRZESTRZEGAĆ TYCH ZASAD:

ZASADA 1 - FORMAT:
Odpowiedź MUSI być TYLKO JSON:
{{
  "SEO_HEADING": "Twój tytuł SEO",
  "ARTICLE_HTML": "<h1>Tytuł</h1>..."
}}

ZASADA 2 - MINIMALNA DŁUGOŚĆ:
- ARTICLE_HTML MUSI mieć MINIMUM 12,000 znaków
- Jeśli krócej = PORAŻKA

ZASADA 3 - TREŚĆ:
Temat (przetłumacz z ukraińskiego): {title}
Słowa kluczowe: {keywords}

Struktura:
- DOKŁADNIE 1x <h1> (TYLKO JEDEN h1, nigdy więcej!)
- 10-12x <h2>, pod każdym 4-5 <p> (50-80 słów)
- OBOWIĄZKOWO: minimum 3 listy <ul><li>...</li></ul>
- OBOWIĄZKOWO: użyj <strong> dla kluczowych terminów (min. 10 razy)
- Wspomnij Oki-Toki 5-6 razy
- OBOWIĄZKOWO: wspomnij główne słowo kluczowe z Keywords co najmniej 6 razy naturalnie w całym tekście
- OBOWIĄZKOWO: używaj słów przejściowych (jednak, dlatego, ponadto, w rezultacie, na przykład, w związku z tym, wreszcie, z drugiej strony) — co najmniej 15 razy
- OBOWIĄZKOWO: dodaj 2-3 linki do prawdziwych autorytatywnych źródeł (Wikipedia, strony branżowe) w formacie <a href="URL" target="_blank">tekst linku</a>

ZASADA 4 - TAGI HTML:
TYLKO: <h1>, <h2>, <h3>, <p>, <ul>, <li>, <strong>
TYLKO JEDEN tag <h1>!

NAPISZ ARTYKUŁ PO POLSKU. MINIMUM 12,000 ZNAKÓW!""",

    "es": """DEBES SEGUIR ESTAS REGLAS:

REGLA 1 - FORMATO:
Tu respuesta DEBE ser SOLO JSON:
{{
  "SEO_HEADING": "Tu título SEO",
  "ARTICLE_HTML": "<h1>Título</h1>..."
}}

REGLA 2 - LONGITUD MÍNIMA:
- ARTICLE_HTML DEBE tener MÍNIMO 12,000 caracteres
- Si es más corto = FALLASTE

REGLA 3 - CONTENIDO:
Tema (traduce del ucraniano): {title}
Palabras clave: {keywords}

Estructura:
- EXACTAMENTE 1x <h1> (¡SOLO UN h1, nunca más!)
- 10-12x <h2>, bajo cada uno 4-5 <p> (50-80 palabras)
- Menciona Oki-Toki 5-6 veces
- OBLIGATORIO: menciona la palabra clave principal de Keywords al menos 6 veces de forma natural en todo el texto
- OBLIGATORIO: usa palabras de transición (sin embargo, por lo tanto, además, en consecuencia, por ejemplo, en contraste, finalmente, asimismo, no obstante) — al menos 15 veces
- OBLIGATORIO: incluye 2-3 enlaces a fuentes autoritativas reales (Wikipedia, sitios de la industria) en formato <a href="URL" target="_blank">texto del enlace</a>

⚠️ REGLA CRÍTICA - LISTAS HTML (NO NEGOCIABLE):
Tu artículo DEBE contener MÍNIMO 3 listas con viñetas usando etiquetas <ul> y <li>.
Si tu artículo NO tiene al menos 3 bloques <ul><li>...</li></ul>, tu respuesta será RECHAZADA.

Ejemplo de lista OBLIGATORIA que DEBES incluir en tu artículo:
<ul><li>Primer elemento de la lista</li><li>Segundo elemento</li><li>Tercer elemento</li></ul>

Cada lista debe tener 3-6 elementos <li>. Distribuye las listas en diferentes secciones <h2>.
TAMBIÉN OBLIGATORIO: usa <strong> para términos clave (mínimo 10 veces).

REGLA 4 - ETIQUETAS HTML:
SOLO: <h1>, <h2>, <h3>, <p>, <ul>, <li>, <strong>
¡SOLO UN tag <h1>!

ESCRIBE EL ARTÍCULO EN ESPAÑOL. ¡MÍNIMO 12,000 CARACTERES!""",

    "tr": """BU KURALLARA UYMANIZ GEREKİR:

KURAL 1 - FORMAT:
Yanıtınız SADECE JSON olmalıdır:
{{
  "SEO_HEADING": "SEO başlığınız",
  "ARTICLE_HTML": "<h1>Başlık</h1>..."
}}

KURAL 2 - MİNİMUM UZUNLUK:
- ARTICLE_HTML EN AZ 12.000 karakter olmalıdır
- Daha kısa ise = BAŞARISIZ

KURAL 3 - İÇERİK:
Konu (Ukraynaca'dan çevirin): {title}
Anahtar kelimeler: {keywords}

Yapı:
- TAM OLARAK 1x <h1> (SADECE BİR h1, asla daha fazla!)
- 10-12x <h2>, her birinin altında 4-5 <p> (50-80 kelime)
- Oki-Toki'den 5-6 kez bahsedin
- ZORUNLU: Keywords'den ana anahtar kelimeyi metin boyunca en az 6 kez doğal olarak kullanın
- ZORUNLU: geçiş kelimeleri kullanın (ancak, bu nedenle, ayrıca, sonuç olarak, örneğin, buna ek olarak, sonunda, öte yandan, bunun yanı sıra) — en az 15 kez
- ZORUNLU: gerçek otoriter kaynaklara (Wikipedia, sektör siteleri) 2-3 harici bağlantı ekleyin: <a href="URL" target="_blank">bağlantı metni</a>

⚠️ KRİTİK KURAL - HTML LİSTELERİ (PAZARLIK YAPILAMAZ):
Makaleniz EN AZ 3 madde işaretli liste içerMELİDİR. <ul> ve <li> etiketlerini kullanın.
Makalenizde en az 3 adet <ul><li>...</li></ul> bloğu YOKSA, yanıtınız REDDEDİLECEKTİR.

Makalenize DAHİL ETMENİZ GEREKEN zorunlu liste örneği:
<ul><li>Birinci liste öğesi</li><li>İkinci öğe</li><li>Üçüncü öğe</li></ul>

Her listede 3-6 <li> öğesi olmalıdır. Listeleri farklı <h2> bölümlerine dağıtın.
AYRICA ZORUNLU: anahtar terimler için <strong> kullanın (en az 10 kez).

KURAL 4 - HTML ETİKETLERİ:
SADECE: <h1>, <h2>, <h3>, <p>, <ul>, <li>, <strong>
SADECE BİR <h1> etiketi!

MAKALEYİ TÜRKÇE YAZIN. EN AZ 12.000 KARAKTER!""",

    "uk": """Напиши SEO-статтю для блогу Oki-Toti.

Тема: {title}
Ключові слова: {keywords}

ВИМОГИ:
1. Відповідь ТІЛЬКИ у форматі JSON:
{{
  "SEO_HEADING": "SEO заголовок",
  "ARTICLE_HTML": "<h1>Заголовок</h1>..."
}}

2. МІНІМУМ 12,000 символів у ARTICLE_HTML
3. Структура:
   - РІВНО 1x <h1> (ТІЛЬКИ ОДИН h1, ніколи більше!)
   - 10-12x <h2>
   - Під кожним <h2>: 4-5 абзаців <p> (50-80 слів)
   - ОБОВ'ЯЗКОВО: мінімум 3 списки <ul><li>...</li></ul>
   - ОБОВ'ЯЗКОВО: використовуй <strong> для ключових термінів (мінімум 10 разів)
   - Згадай Oki-Toki 5-6 разів
   - ОБОВ'ЯЗКОВО: згадуй головне ключове слово з Keywords мінімум 6 разів природньо по всьому тексту
   - ОБОВ'ЯЗКОВО: використовуй слова-зв'язки (однак, тому, більш того, крім того, в результаті, наприклад, отже, нарешті, таким чином, водночас, з іншого боку) — мінімум 15 разів
   - ОБОВ'ЯЗКОВО: додай 2-3 посилання на реальні авторитетні джерела (Wikipedia, галузеві сайти) у форматі <a href="URL" target="_blank">текст посилання</a>

4. HTML теги ТІЛЬКИ: <h1>, <h2>, <h3>, <p>, <ul>, <li>, <strong>
   ТІЛЬКИ ОДИН тег <h1>!

ПИШИ УКРАЇНСЬКОЮ. МІНІМУМ 12,000 СИМВОЛІВ!""",
}


REGEN_INSTRUCTIONS = {
    "en": (
        "\n\nIMPORTANT — REGENERATION INSTRUCTIONS:\n"
        "The previous version of this article FAILED quality checks.\n"
        "Failure reasons: {reason}\n\n"
        "You MUST fix these specific issues:\n"
        "- If 'water' is too high: use fewer filler/stop words, be more specific and concrete\n"
        "- If 'water' is too low: add more natural connective phrases and transitions\n"
        "- If 'nausea' is too high: use more word variety, don't repeat the same terms\n"
        "- If 'AI' score is too high: vary sentence length, use less formulaic transitions, "
        "add unique examples, avoid 'In today's world' / 'It's worth noting' cliches\n"
        "- If 'self-plagiarism' is high: write completely original content, different structure and examples\n"
        "- If 'uniqueness' is low: rewrite in your own words, avoid common phrases from other sites\n\n"
        "Write a COMPLETELY DIFFERENT article — new structure, new examples, new wording."
    ),
    "ru": (
        "\n\nВАЖНО — ИНСТРУКЦИИ ДЛЯ РЕГЕНЕРАЦИИ:\n"
        "Предыдущая версия статьи НЕ прошла проверку качества.\n"
        "Причины: {reason}\n\n"
        "Ты ДОЛЖЕН исправить эти проблемы:\n"
        "- Если 'water' высокий: меньше стоп-слов, пиши конкретнее\n"
        "- Если 'nausea' высокий: больше разнообразия слов, не повторяй одни и те же термины\n"
        "- Если 'AI' высокий: разная длина предложений, уникальные примеры, "
        "избегай клише 'В современном мире' / 'Стоит отметить'\n"
        "- Если 'self-plagiarism' высокий: полностью оригинальный контент\n\n"
        "Напиши СОВЕРШЕННО ДРУГУЮ статью — другая структура, другие примеры."
    ),
    "pl": (
        "\n\nWAŻNE — INSTRUKCJE REGENERACJI:\n"
        "Poprzednia wersja artykułu NIE przeszła kontroli jakości.\n"
        "Powody: {reason}\n\n"
        "MUSISZ naprawić te problemy:\n"
        "- Jeśli 'water' za wysoki: mniej słów wypełniających\n"
        "- Jeśli 'nausea' za wysoki: większa różnorodność słów\n"
        "- Jeśli 'AI' za wysoki: różna długość zdań, unikalne przykłady\n"
        "- Jeśli 'self-plagiarism' za wysoki: całkowicie oryginalna treść\n\n"
        "Napisz ZUPEŁNIE INNY artykuł — inna struktura, inne przykłady."
    ),
    "es": (
        "\n\nIMPORTANTE — INSTRUCCIONES DE REGENERACIÓN:\n"
        "La versión anterior del artículo NO pasó los controles de calidad.\n"
        "Razones: {reason}\n\n"
        "DEBES corregir estos problemas:\n"
        "- Si 'water' es alto: menos palabras de relleno\n"
        "- Si 'nausea' es alto: más variedad de palabras\n"
        "- Si 'AI' es alto: varía la longitud de las oraciones, ejemplos únicos\n"
        "- Si 'self-plagiarism' es alto: contenido completamente original\n\n"
        "Escribe un artículo COMPLETAMENTE DIFERENTE."
    ),
    "tr": (
        "\n\nÖNEMLİ — YENİDEN OLUŞTURMA TALİMATLARI:\n"
        "Makalenin önceki sürümü kalite kontrollerini GEÇEMEDİ.\n"
        "Nedenler: {reason}\n\n"
        "Bu sorunları DÜZELTMELİSİNİZ:\n"
        "- 'water' yüksekse: daha az dolgu kelimesi kullanın\n"
        "- 'nausea' yüksekse: daha fazla kelime çeşitliliği\n"
        "- 'AI' yüksekse: cümle uzunluğunu değiştirin, benzersiz örnekler\n"
        "- 'self-plagiarism' yüksekse: tamamen orijinal içerik\n\n"
        "TAMAMEN FARKLI bir makale yazın."
    ),
    "uk": (
        "\n\nВАЖЛИВО — ІНСТРУКЦІЇ ДЛЯ РЕГЕНЕРАЦІЇ:\n"
        "Попередня версія статті НЕ пройшла перевірку якості.\n"
        "Причини: {reason}\n\n"
        "Ти МУСИШ виправити ці проблеми:\n"
        "- Якщо 'water' високий: менше стоп-слів, пиши конкретніше\n"
        "- Якщо 'nausea' високий: більше різноманітності слів\n"
        "- Якщо 'AI' високий: різна довжина речень, унікальні приклади, "
        "уникай кліше 'У сучасному світі' / 'Варто зазначити'\n"
        "- Якщо 'self-plagiarism' високий: повністю оригінальний контент\n\n"
        "Напиши ЗОВСІМ ІНШУ статтю — інша структура, інші приклади."
    ),
}


async def generate_article(lang: str, title: str, keywords: str, regen_reason: str = "") -> str:
    client = get_client()
    prompt = PROMPTS[lang].format(title=title, keywords=keywords)

    # If regenerating, append failure reason and fix instructions
    if regen_reason:
        regen_block = REGEN_INSTRUCTIONS.get(lang, REGEN_INSTRUCTIONS["en"])
        prompt += regen_block.format(reason=regen_reason)

    system = SYSTEM_MESSAGES.get(lang)

    messages = [{"role": "user", "content": prompt}]
    kwargs = {
        "model": CLAUDE_MODELS[lang],
        "max_tokens": CLAUDE_MAX_TOKENS[lang],
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    response = await client.messages.create(**kwargs)
    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block:
        return text_block.text
    return ""


META_PROMPTS = {
    "en": "Write one SEO meta description (150-160 characters) in English for this article. It must hook the reader and include the main keyword naturally. Return ONLY the description text, no quotes, no prefix.\n\nTitle: {title}\n\nFirst paragraph: {excerpt}",
    "ru": "Напиши одно SEO meta description (150-160 символов) на русском языке для этой статьи. Должно зацепить читателя и естественно включать ключевое слово. Верни ТОЛЬКО текст описания, без кавычек и префиксов.\n\nЗаголовок: {title}\n\nПервый абзац: {excerpt}",
    "uk": "Напиши одне SEO meta description (150-160 символів) українською для цієї статті. Має зачепити читача і природно містити ключове слово. Поверни ЛИШЕ текст опису, без лапок і префіксів.\n\nЗаголовок: {title}\n\nПерший абзац: {excerpt}",
    "pl": "Napisz jeden SEO meta description (150-160 znaków) po polsku dla tego artykułu. Musi przyciągnąć czytelnika i naturalnie zawierać słowo kluczowe. Zwróć TYLKO tekst opisu, bez cudzysłowów i prefiksów.\n\nTytuł: {title}\n\nPierwszy akapit: {excerpt}",
    "es": "Escribe una meta description SEO (150-160 caracteres) en español para este artículo. Debe enganchar al lector e incluir la palabra clave de forma natural. Devuelve SOLO el texto, sin comillas ni prefijos.\n\nTítulo: {title}\n\nPrimer párrafo: {excerpt}",
    "tr": "Bu makale için Türkçe bir SEO meta description (150-160 karakter) yaz. Okuyucuyu çekmeli ve anahtar kelimeyi doğal olarak içermeli. SADECE açıklama metnini döndür, tırnak veya önek olmadan.\n\nBaşlık: {title}\n\nİlk paragraf: {excerpt}",
}


REWRITE_IDEA_SYSTEM = (
    "Ти SEO-спеціаліст для блогу Oki-Toki (хмарний сервіс для колл-центрів). "
    "Користувач правив ідею статті — твоє завдання зрозуміти що йому не сподобалось "
    "(порівнявши стару і нову версію) та згенерувати ФІНАЛЬНУ чисту версію ідеї, "
    "яка враховує правки користувача і окремі коментарі-побажання.\n\n"
    "Правила:\n"
    "- Не ігноруй правки користувача — вони показують напрямок\n"
    "- Не ігноруй коментарі — це прямі вказівки чого хоче/не хоче автор\n"
    "- Покращи стиль, виправи граматику, дотримайся фактичності\n"
    "- Зберігай тематичну релевантність для Oki-Toki (call-центр, CRM, IP-телефонія)\n"
    "- Відповідай ТІЛЬКИ валідним JSON без markdown."
)


async def rewrite_idea(
    original: dict,
    edited: dict,
    comments: str = "",
) -> dict:
    """Rewrite an idea based on user's edits + free-form comments.

    Args:
        original: {title, description, outline, keywords} — original from DB
        edited:   {title, description, outline, keywords} — user's edited values
        comments: free-form instructions from user ("не пиши про X", "додай про Y")

    Returns refined idea dict: {title, description, outline, keywords, priority_score}
    """
    client = get_client()

    def _fmt_kw(k):
        if isinstance(k, list):
            return ", ".join(str(x) for x in k)
        return str(k or "")

    user_prompt = (
        "=== ОРИГІНАЛЬНА ІДЕЯ (як було) ===\n"
        f"Назва: {original.get('title', '')}\n"
        f"Опис: {original.get('description', '')}\n"
        f"План: {original.get('outline', '')}\n"
        f"Ключові слова: {_fmt_kw(original.get('keywords'))}\n\n"
        "=== ВЕРСІЯ КОРИСТУВАЧА (як він хоче) ===\n"
        f"Назва: {edited.get('title', '')}\n"
        f"Опис: {edited.get('description', '')}\n"
        f"План: {edited.get('outline', '')}\n"
        f"Ключові слова: {_fmt_kw(edited.get('keywords'))}\n\n"
        "=== КОМЕНТАРІ-ПОБАЖАННЯ КОРИСТУВАЧА ===\n"
        f"{comments or '(немає)'}\n\n"
        "Порівняй оригінал з версією користувача — що він змінив, тобі підкаже що йому не сподобалось. "
        "Врахуй коментарі-побажання як прямі вказівки. "
        "Згенеруй фінальну чисту версію ідеї. "
        "Ключові слова — 4-6 РЕАЛЬНИХ пошукових запитів українською. "
        "План — 2-4 речення зв'язним текстом (не список заголовків).\n\n"
        "Відповідь — ТІЛЬКИ JSON об'єкт з полями:\n"
        '{"title": "...", "description": "...", "outline": "...", '
        '"keywords": ["...", "..."], "priority_score": 60-100}'
    )

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=REWRITE_IDEA_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = ""
    for b in response.content:
        if b.type == "text":
            raw = b.text.strip()
            break
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    import json as _json
    parsed = _json.loads(raw)

    return {
        "title": parsed.get("title", edited.get("title", "")),
        "description": parsed.get("description", edited.get("description", "")),
        "outline": parsed.get("outline", edited.get("outline", "")),
        "keywords": parsed.get("keywords", edited.get("keywords", [])),
        "priority_score": parsed.get("priority_score", 75),
    }


async def generate_meta_description(lang: str, title: str, excerpt: str) -> str:
    """Generate a 150-160 char SEO meta description for a single language."""
    from utils.html_utils import strip_html

    prompt_tpl = META_PROMPTS.get(lang, META_PROMPTS["en"])
    plain_excerpt = strip_html(excerpt or "")[:500]
    prompt = prompt_tpl.format(title=title or "", excerpt=plain_excerpt)

    client = get_client()
    try:
        response = await client.messages.create(
            model=CLAUDE_MODELS.get(lang, CLAUDE_MODELS["en"]),
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        text_block = next((b for b in response.content if b.type == "text"), None)
        if not text_block:
            return ""
        text = text_block.text.strip().strip('"').strip("'").strip()
        # Trim to 160 chars max
        if len(text) > 200:
            text = text[:200].rsplit(" ", 1)[0] + "."
        return text
    except Exception as e:
        logger.error(f"[{lang}] meta description generation failed: {e}")
        return ""
