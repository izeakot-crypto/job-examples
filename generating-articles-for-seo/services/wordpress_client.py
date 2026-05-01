"""WordPress REST API client using httpx."""
import base64
import logging

import httpx

logger = logging.getLogger(__name__)


class WordPressClient:
    def __init__(self, base_url: str, username: str, app_password: str):
        creds = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        self.api_base = f"{base_url.rstrip('/')}/wp-json/wp/v2"
        self.headers = {
            "Authorization": f"Basic {creds}",
        }
        self.timeout = 120.0

    async def upload_media(self, image_bytes: bytes, filename: str, mime_type: str = "image/png") -> int:
        """Upload image to WP Media Library. Returns media_id."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.api_base}/media",
                headers={
                    **self.headers,
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Type": mime_type,
                },
                content=image_bytes,
            )
            resp.raise_for_status()
            data = resp.json()
            media_id = data["id"]
            logger.info(f"[WP] Uploaded media: id={media_id}, file={filename}")
            return media_id

    async def create_post(self, post_data: dict) -> dict:
        """Create a WP post. Returns {id, link}."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.api_base}/posts",
                headers={**self.headers, "Content-Type": "application/json"},
                json=post_data,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"[WP] Created post: id={data['id']}, link={data.get('link')}")
            return {"id": data["id"], "link": data.get("link", "")}

    async def update_post(self, post_id: int, post_data: dict) -> dict:
        """Update an existing WP post. Returns {id, link}."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.api_base}/posts/{post_id}",
                headers={**self.headers, "Content-Type": "application/json"},
                json=post_data,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"[WP] Updated post: id={data['id']}")
            return {"id": data["id"], "link": data.get("link", "")}

    async def get_category_id(self, slug: str = "blog") -> int | None:
        """Find category ID by slug."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.api_base}/categories",
                headers=self.headers,
                params={"slug": slug},
            )
            resp.raise_for_status()
            categories = resp.json()
            if categories:
                return categories[0]["id"]
            return None
