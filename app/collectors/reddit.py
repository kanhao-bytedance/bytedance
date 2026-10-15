from datetime import datetime, timezone
import httpx
from ..schemas import RawFeedback
from ..settings import settings

API = "https://oauth.reddit.com"

def _headers():
    if not settings.reddit_bearer_token:
        raise RuntimeError("Set REDDIT_BEARER_TOKEN before using the Reddit collector.")
    return {"Authorization": f"bearer {settings.reddit_bearer_token}", "User-Agent": settings.reddit_user_agent}

async def search_posts(query: str, subreddit: str | None = None, limit: int = 25) -> list[RawFeedback]:
    path = f"/r/{subreddit}/search" if subreddit else "/search"
    params = {"q": query, "limit": min(limit, 100), "sort": "new", "restrict_sr": bool(subreddit), "raw_json": 1}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(API + path, headers=_headers(), params=params)
        r.raise_for_status()
    out = []
    for child in r.json()["data"]["children"]:
        d = child["data"]
        out.append(RawFeedback(
            source="reddit", external_id=d["name"], content_type="post",
            url="https://www.reddit.com" + d.get("permalink", ""), author=d.get("author"),
            title=d.get("title"), text=d.get("selftext") or d.get("title") or "",
            published_at=datetime.fromtimestamp(d["created_utc"], tz=timezone.utc),
            engagement=int(d.get("score", 0)) + int(d.get("num_comments", 0)),
        ))
    return out
