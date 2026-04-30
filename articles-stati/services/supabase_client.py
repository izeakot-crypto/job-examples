import threading

from supabase import create_client

from config import settings

_client = None
_lock = threading.Lock()


def get_client():
    global _client
    if _client is None:
        with _lock:
            if _client is None:
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
    # Ideas table may not have this id (e.g. manually created articles)
    idea_result = client.table("ideas").select("*").eq("id", idea_id).execute()
    idea_data = idea_result.data[0] if idea_result.data else {}
    return {**article.data, "idea": idea_data}


def update_article_audit(idea_id: str, data: dict):
    client = get_client()
    # Use upsert so the row is created if it doesn't exist yet
    data["id"] = idea_id
    client.table("articles_audit").upsert(data, on_conflict="id").execute()
