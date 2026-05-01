"""Article Pipeline — FastAPI entry point.

Replaces n8n workflows:
  - WF1: Article Generation & Translation
  - WF2: Article Verification
  - WF3: Regeneration (called by WF2 internally)
  - Image Generation (Gemini)
  - Ideas Generation (Claude)
  - Publish Article
"""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from pipeline.generator import run_generation
from pipeline.verifier import run_verification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Article Pipeline", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track running pipelines so they don't get garbage collected
_running_tasks: set[asyncio.Task] = set()


# ── Request models ──────────────────────────────────────────────

class ApproveRequest(BaseModel):
    idea_id: str
    timestamp: str | None = None
    regenerate: bool = False
    theme: str | None = None
    article_id: str | None = None


class GenerateImageRequest(BaseModel):
    topic: str
    description: str = ""


class GenerateIdeasRequest(BaseModel):
    count: int = 10
    timestamp: str | None = None


class PublishArticleRequest(BaseModel):
    idea_id: str
    wordpress_urls: list[str] = []
    timestamp: str | None = None


# ── Pipeline (WF1 → WF2 → WF3) ────────────────────────────────

async def _run_full_pipeline(idea_id: str):
    """Run the full pipeline: generate -> verify (with auto-regen)."""
    try:
        logger.info(f"=== Pipeline started for idea: {idea_id} ===")

        # WF1: Generate articles in 6 languages
        article_data = await run_generation(idea_id)

        # WF2: Verify (runs WF3 internally if needed)
        result = await run_verification(article_data)

        status = result.get("verification_status", "unknown")
        logger.info(f"=== Pipeline finished for {idea_id}: {status} ===")

    except Exception as e:
        logger.exception(f"Pipeline failed for {idea_id}: {e}")
        from services.progress import notify_progress
        await notify_progress(idea_id, "error", 0, f"Помилка: {str(e)[:200]}")


@app.post("/approve-idea")
async def approve_idea(req: ApproveRequest):
    """Webhook endpoint — called when frontend approves an article idea."""
    task = asyncio.create_task(_run_full_pipeline(req.idea_id))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return {"status": "accepted", "idea_id": req.idea_id}


# ── Image Generation ────────────────────────────────────────────

@app.post("/generate-image")
async def generate_image_endpoint(req: GenerateImageRequest):
    """Synchronous image generation — Claude scene + Gemini image.
    Called by Express.js triggerImageGeneration (waits for response).
    """
    from services.image_gen.generator import generate_image

    result = await generate_image(req.topic, req.description)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Image generation failed"))

    return result


# ── Ideas Generation ────────────────────────────────────────────

@app.post("/generate-ideas")
async def generate_ideas_endpoint(req: GenerateIdeasRequest):
    """Generate article ideas using Claude AI."""
    from services.ideas_gen import generate_ideas

    ideas = await generate_ideas(req.count)

    if not ideas:
        raise HTTPException(status_code=500, detail="Failed to generate ideas")

    # Save to Supabase
    from services.supabase_client import get_client as get_supabase
    try:
        client = get_supabase()
        result = client.table("ideas").insert(ideas).execute()
        saved = result.data or ideas
        logger.info(f"[Ideas] Saved {len(saved)} ideas to DB")
    except Exception as e:
        logger.warning(f"[Ideas] DB save failed, returning unsaved: {e}")
        saved = ideas

    return {
        "success": True,
        "count": len(saved),
        "ideas": saved,
        "ids": [i.get("id", "") for i in saved],
        "message": f"Згенеровано {len(saved)} ідей статей",
    }


# ── Publish Article ─────────────────────────────────────────────

@app.post("/publish-article")
async def publish_article_endpoint(req: PublishArticleRequest):
    """Publish article to WordPress as draft and update DB."""
    from services.wp_publisher import publish_to_wordpress

    result = await publish_to_wordpress(req.idea_id)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Publishing failed"))

    return result


# ── Health ──────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "running_tasks": len(_running_tasks),
        "version": "2.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
