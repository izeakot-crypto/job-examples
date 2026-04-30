"""Supabase-compatible client: routes to local PostgreSQL when USE_LOCAL_PG=true.

Keeps the existing API surface (get_client, get_idea, update_article_audit, etc.)
so downstream imports don't change.
"""
import os
import threading

from config import settings

_client = None
_lock = threading.Lock()


def _use_local_pg() -> bool:
    return str(os.environ.get("USE_LOCAL_PG", "")).lower() == "true"


def get_client():
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                if _use_local_pg():
                    from services.supabase_client_pg import get_pg_client
                    _client = get_pg_client()
                else:
                    from supabase import create_client
                    _client = create_client(settings.supabase_url, settings.supabase_key)
    return _client


def get_idea(idea_id: str) -> dict:
    client = get_client()
    result = client.table("ideas").select("*").eq("id", idea_id).single().execute()
    return result.data


def get_article_for_publish(idea_id: str) -> dict:
    """Fetch article + idea data for publishing."""
    client = get_client()
    article = client.table("articles_audit").select("*").eq("id", idea_id).single().execute()
    idea_result = client.table("ideas").select("*").eq("id", idea_id).execute()
    idea_data = idea_result.data[0] if idea_result.data else {}
    return {**article.data, "idea": idea_data}


def update_article_audit(idea_id: str, data: dict):
    client = get_client()
    data["id"] = idea_id
    client.table("articles_audit").upsert(data, on_conflict="id").execute()


def patch_article_audit(idea_id: str, data: dict):
    """UPDATE only — safe for partial updates (won't fail on NOT NULL columns)."""
    client = get_client()
    client.table("articles_audit").update(data).eq("id", idea_id).execute()
