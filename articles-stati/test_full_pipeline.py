"""
Full pipeline test: generate -> verify -> publish as draft.

Usage:
    python test_full_pipeline.py                   # picks first pending idea
    python test_full_pipeline.py <idea_id>         # use specific idea
    python test_full_pipeline.py --publish-only <idea_id>  # skip gen/verify, just publish
"""
import asyncio
import logging
import sys
import time

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

API_BASE = "http://127.0.0.1:8000"
POLL_INTERVAL = 5   # seconds between status checks
POLL_TIMEOUT = 600  # max seconds to wait for pipeline


def get_pending_idea():
    """Fetch first idea with status 'pending' or 'approved' from Supabase."""
    from services.supabase_client import get_client
    client = get_client()
    # Try to find an idea that hasn't been fully generated yet
    for status in ("pending", "approved", "new"):
        result = client.table("ideas").select("id,theme,status").eq("status", status).limit(1).execute()
        if result.data:
            return result.data[0]
    # Fallback: get the most recently created idea
    result = client.table("ideas").select("id,theme,status").order("created_at", desc=True).limit(1).execute()
    if result.data:
        return result.data[0]
    return None


def get_verified_idea():
    """Fetch first idea that has been verified but not published."""
    from services.supabase_client import get_client
    client = get_client()
    result = (
        client.table("articles_audit")
        .select("id,verification_status,wordpress_post_id")
        .eq("verification_status", "passed")
        .is_("wordpress_post_id", "null")
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]
    # Also accept "partial_pass"
    result = (
        client.table("articles_audit")
        .select("id,verification_status,wordpress_post_id")
        .eq("verification_status", "partial_pass")
        .is_("wordpress_post_id", "null")
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_article_status(idea_id: str):
    """Check current article status in DB."""
    from services.supabase_client import get_client
    client = get_client()
    result = client.table("articles_audit").select(
        "id,verification_status,wordpress_post_id,wordpress_url"
    ).eq("id", idea_id).execute()
    return result.data[0] if result.data else None


async def run_generate_and_verify(idea_id: str):
    """Call /approve-idea and poll until pipeline finishes."""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        logger.info(f"▶  Calling /approve-idea for {idea_id}")
        resp = await client.post("/approve-idea", json={"idea_id": idea_id})
        resp.raise_for_status()
        logger.info(f"   Accepted: {resp.json()}")

    logger.info("⏳ Waiting for pipeline to finish (generate → verify)...")
    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        await asyncio.sleep(POLL_INTERVAL)
        status = get_article_status(idea_id)
        if status:
            vs = status.get("verification_status", "—")
            logger.info(f"   Status: {vs}")
            if vs in ("passed", "partial_pass", "failed", "pass"):
                return vs
        else:
            logger.info("   Article row not yet in DB...")

    raise TimeoutError(f"Pipeline did not finish within {POLL_TIMEOUT}s")


async def run_publish(idea_id: str):
    """Call /publish-article and return result."""
    async with httpx.AsyncClient(base_url=API_BASE, timeout=300) as client:
        logger.info(f"📤 Calling /publish-article for {idea_id}")
        resp = await client.post("/publish-article", json={"idea_id": idea_id})
        if resp.status_code != 200:
            logger.error(f"   HTTP {resp.status_code}: {resp.text[:500]}")
            return None
        return resp.json()


async def main():
    publish_only = False
    idea_id = None

    args = sys.argv[1:]
    if args and args[0] == "--publish-only":
        publish_only = True
        args = args[1:]
    if args:
        idea_id = args[0]

    # ── Step 0: Pick idea ──────────────────────────────────────────
    if not idea_id:
        if publish_only:
            row = get_verified_idea()
            if not row:
                logger.error("No verified+unpublished articles found in DB.")
                return
            idea_id = row["id"]
            logger.info(f"Found verified article: {idea_id} (status={row['verification_status']})")
        else:
            row = get_pending_idea()
            if not row:
                logger.error("No pending ideas found in DB.")
                return
            idea_id = row["id"]
            logger.info(f"Found idea: {idea_id} | theme={row.get('theme', '?')} | status={row.get('status', '?')}")
    else:
        logger.info(f"Using provided idea_id: {idea_id}")

    # ── Step 1: Generate + Verify ──────────────────────────────────
    if not publish_only:
        try:
            vs = await run_generate_and_verify(idea_id)
            if vs == "failed":
                logger.warning("⚠  Verification FAILED — article may have quality issues. Proceeding anyway...")
            else:
                logger.info(f"✅ Verification complete: {vs}")
        except TimeoutError as e:
            logger.error(f"⏰ {e}")
            return

    # ── Step 2: Publish to WP ──────────────────────────────────────
    result = await run_publish(idea_id)
    if not result:
        logger.error("❌ Publishing failed")
        return

    if result.get("success"):
        logger.info("✅ Published successfully!")
        logger.info(f"   WP Post ID  : {result.get('wordpress_post_id')}")
        logger.info(f"   WP Draft URL: {result.get('wordpress_url')}")
        logger.info(f"   Admin URL   : {result.get('admin_url', 'N/A')}")
    else:
        logger.error(f"❌ Publish error: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
