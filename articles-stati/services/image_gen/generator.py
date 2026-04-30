"""Image generation service: Claude scene description + Gemini image generation."""
import logging
from pathlib import Path

import httpx

from config import settings
from services.anthropic_client import get_client as get_anthropic_client

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent"

# Load reference images (base64) at module level
_REF_IMAGES: list[str] = []
_REF_DIR = Path(__file__).parent


def _load_ref_images() -> list[str]:
    global _REF_IMAGES
    if _REF_IMAGES:
        return _REF_IMAGES
    for i in range(3):
        b64_path = _REF_DIR / f"ref_image_{i}.b64"
        if b64_path.exists():
            _REF_IMAGES.append(b64_path.read_text().strip())
        else:
            logger.warning(f"Reference image not found: {b64_path}")
    return _REF_IMAGES


SCENE_SYSTEM_PROMPT = (
    "You create UNIQUE scene descriptions for flat vector blog illustrations. "
    "Each scene must visually represent the SPECIFIC topic through metaphorical objects and character actions.\n\n"
    "STYLE RULES:\n"
    "- 1-2 FULL-BODY characters (legs visible, wearing black or dark pants, blue/indigo shirt, dark blue hair)\n"
    "- Characters DO things: sit at desk with laptop, stand pointing at giant screen, hold documents, gesture at floating objects\n"
    "- Characters can sit at desks/tables or stand freely (NO visible ground line or floor surface)\n"
    "- TOPIC-SPECIFIC large objects that visually represent the blog topic (giant browser window showing relevant UI, "
    "oversized phone with specific interface, robot for AI topics, shield for security, folders for data management, "
    "headphones for call center)\n"
    "- 5-10 small floating decorative elements: gears, arrows, question marks, chat bubbles, envelopes, phone icons, "
    "charts, checkmarks, dashed lines, brackets, sound waves\n"
    "- METAPHORICAL representation: the objects should TELL what the article is about without words\n"
    "- Complex but clean composition with multiple layers of detail\n\n"
    "UNIQUENESS RULES:\n"
    "- Each illustration must look DIFFERENT from others - unique character pose, unique main object, unique arrangement\n"
    "- The main large object should be SPECIFIC to the topic (NOT just a generic phone)\n"
    "- Include 2-3 medium objects that add context to the topic\n"
    "- Vary character actions: typing on laptop, pointing at screen, holding phone to ear, gesturing, examining documents\n\n"
    "BANNED: headset on head, visible ground/floor line, shadow under feet, 3D effects, gradients, photorealism.\n\n"
    "OUTPUT: 4-6 sentences describing the scene. Be specific about objects and their relevance to the topic. "
    "Last sentence MUST be: The scene is set on a white background with ONE large solid organic lavender-blue blob shape "
    "behind the entire composition."
)

GEMINI_SYSTEM_INSTRUCTION = (
    "You generate professional flat vector illustrations. RULES: "
    "1) ALWAYS use PURE WHITE (#FFFFFF) canvas background. "
    "2) Place ONE soft lavender blob (#C5CAE9) inside the white canvas. "
    "3) Make each illustration UNIQUE with topic-specific objects and detailed compositions. "
    "4) Include many small decorative elements for visual richness. "
    "5) Characters are full-body with visible legs in dark pants."
)

IMAGE_PROMPT_LINES = [
    "BACKGROUND: The IMAGE CANVAS is PURE WHITE (#FFFFFF). All edges are white. "
    "Inside the white canvas is ONE large soft organic lavender blob (#C5CAE9, no outline). "
    "Characters and objects are ON TOP of the blob. White is visible around blob edges.",
    "",
    "Generate a NEW flat vector illustration matching the reference images style. "
    "Make it UNIQUE and SPECIFIC to the described scene.",
    "",
    "SCENE: {scene_description}",
    "",
    "STYLE (match references):",
    "1. FULL-BODY characters with visible legs in BLACK/DARK PANTS. Blue/indigo shirt (#4361EE) with collar. "
    "Dark blue hair (#1A1A2E). Minimal face (dot eyes, tiny nose). Warm peach skin.",
    "2. Characters DO things: sit at desk, type on laptop, point at screens, hold documents, gesture. Natural active poses.",
    "3. NO visible ground line or floor surface. Characters either float or sit at objects that float.",
    "4. LARGE TOPIC-SPECIFIC OBJECTS: giant browser windows with UI mockups, oversized phones with app screens, "
    "robots with speech bubbles, laptops, documents, folders, shields. These objects must clearly represent the blog topic.",
    "5. MEDIUM floating objects: open folders, clipboards, browser tabs, CRM cards, phone receivers, data charts.",
    "6. SMALL scattered decorative elements (many!): gears, arrows (curved and straight), question marks, chat bubbles, "
    "envelopes, checkmarks, dots, plus signs, dashed orbit lines, sound waves, brackets, phone icons, location pins.",
    "7. ABSOLUTELY FLAT 2D. No perspective, no 3D, no gradients, no shadows. THICK DARK NAVY OUTLINES (#1A1A2E) "
    "on every element 3-4px.",
    "8. Square 1:1. NO text/words/letters in the image.",
    "9. COLORS: White canvas, lavender blob (#C5CAE9), blue shirts (#4361EE), navy outlines+hair (#1A1A2E), "
    "peach skin, teal accents (#26A69A), black/dark pants.",
    "10. COMPLEX rich COMPOSITION: multiple layers, many elements, but clean and readable. "
    "Like a professional SaaS illustration pack. Each illustration looks UNIQUE.",
    "",
    "CANVAS MUST BE WHITE. Not dark, not black, not gray.",
]


async def _generate_scene_description(topic: str, description: str) -> str:
    """Use Claude to generate a scene description for the illustration."""
    client = get_anthropic_client()

    user_prompt = (
        f"{SCENE_SYSTEM_PROMPT}\n\n"
        "---\n\n"
        "Create a UNIQUE illustration scene for this blog topic. "
        "The scene must visually represent the topic through specific objects and character actions.\n\n"
        f"Blog topic: {topic}\n\n"
        f"Article summary: {description or 'No description provided.'}\n\n"
        "Describe a scene with 1-2 full-body characters interacting with topic-specific large objects. "
        "Include 5-10 small floating decorative elements. "
        "Make the main objects clearly represent what the article is about.\n\n"
        "IMPORTANT: Output ONLY the scene description (4-6 sentences), nothing else. "
        "No introductions, no explanations, no headers."
    )

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return response.content[0].text


async def _generate_image_gemini(scene_description: str) -> dict:
    """Use Gemini to generate the image from scene description + reference images."""
    ref_images = _load_ref_images()

    image_parts = [
        {"inlineData": {"mimeType": "image/png", "data": img}}
        for img in ref_images
    ]

    prompt = "\n".join(IMAGE_PROMPT_LINES).format(scene_description=scene_description)

    request_body = {
        "systemInstruction": {
            "parts": [{"text": GEMINI_SYSTEM_INSTRUCTION}]
        },
        "contents": [{
            "parts": [*image_parts, {"text": prompt}]
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "temperature": 0.6,
        },
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            GEMINI_URL,
            params={"key": settings.gemini_api_key},
            json=request_body,
        )
        resp.raise_for_status()
        data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        return {"success": False, "error": "No candidates in Gemini response"}

    parts = candidates[0].get("content", {}).get("parts", [])
    image_data = None
    text_description = ""

    for part in parts:
        if "inlineData" in part:
            image_data = part["inlineData"]
        if "text" in part:
            text_description = part["text"]

    if not image_data:
        return {"success": False, "error": "No image data in response", "textOnly": text_description}

    return {
        "success": True,
        "description": text_description,
        "sceneDescription": scene_description,
        "mimeType": image_data.get("mimeType", "image/png"),
        "imageBase64": image_data.get("data", ""),
    }


async def generate_image(topic: str, description: str = "") -> dict:
    """Full image generation pipeline: Claude scene -> Gemini image.

    Returns:
        {"success": True, "mimeType": str, "imageBase64": str, ...} on success
        {"success": False, "error": str} on failure
    """
    try:
        logger.info(f"[Image Gen] Generating scene description for: {topic}")
        scene = await _generate_scene_description(topic, description)
        logger.info(f"[Image Gen] Scene: {scene[:100]}...")

        logger.info("[Image Gen] Calling Gemini for image generation...")
        result = await _generate_image_gemini(scene)

        if result.get("success"):
            logger.info("[Image Gen] Image generated successfully")
        else:
            logger.warning(f"[Image Gen] Failed: {result.get('error')}")

        return result

    except Exception as e:
        logger.error(f"[Image Gen] Error: {e}")
        return {"success": False, "error": str(e)}
