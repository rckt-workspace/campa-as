"""Script to fetch Instagram posts and persist them locally"""
import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime

from app.providers.instagram import InstaloaderInstagramProvider
from app.repositories.json_repo import JsonRepository
from app.domain.exceptions import InstagramProviderException


def print_post_summary(posts):
    """Print a readable summary of fetched posts"""
    print(f"\n{'='*80}")
    print(f"Successfully fetched {len(posts)} posts from @{posts[0].username if posts else 'unknown'}")
    print(f"{'='*80}\n")

    for i, post in enumerate(posts, 1):
        caption_preview = post.caption[:100].replace("\n", " ") if post.caption else "(no caption)"
        print(f"#{i}")
        print(f"  Shortcode:    {post.shortcode}")
        print(f"  Published:    {post.published_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Type:         {post.post_type.value}")
        print(f"  Is Video:     {post.is_video}")
        print(f"  Permalink:    {post.permalink}")
        print(f"  Caption:      {caption_preview}...")
        print()


def serialize_post(post):
    """Serialize InstagramPost to JSON-compatible dict"""
    return {
        "shortcode": post.shortcode,
        "username": post.username,
        "caption": post.caption,
        "post_type": post.post_type.value,
        "published_at": post.published_at.isoformat(),
        "permalink": post.permalink,
        "thumbnail_url": post.thumbnail_url,
        "is_video": post.is_video,
        "media_count": post.media_count,
    }


async def fetch_and_save_posts(
    username: str,
    limit: int = 5,
    session_username: str | None = None,
    session_file: str | None = None,
):
    """Fetch posts from Instagram and save to JSON"""
    try:
        print(f"Initializing InstaloaderInstagramProvider...")
        session_file_path = Path(session_file) if session_file else None

        provider = InstaloaderInstagramProvider(
            session_username=session_username,
            session_file=session_file_path,
        )

        auth_status = " (authenticated)" if session_username else " (anonymous)"
        print(f"Fetching {limit} posts from @{username}{auth_status}...")
        posts = await provider.get_posts(username, limit=limit)

        if not posts:
            print(f"ERROR: No posts retrieved from @{username}")
            print("Possible causes:")
            print("  - Account doesn't exist")
            print("  - Account is private and requires authentication")
            print("  - Instagram rate limiting or blocking")
            return

        print_post_summary(posts)

        # Persist to JSON
        repo = JsonRepository(data_dir="data")
        data_to_save = {
            "username": username,
            "fetched_at": datetime.now().isoformat(),
            "authenticated": bool(session_username),
            "posts": [serialize_post(p) for p in posts],
        }

        repo.save(f"{username}_posts", data_to_save)
        print(f"✓ Saved to: data/{username}_posts.json")

    except InstagramProviderException as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Fetch Instagram posts and persist locally")
    parser.add_argument("--username", required=True, help="Instagram username to fetch (e.g., newbodycol)")
    parser.add_argument("--limit", type=int, default=5, help="Number of posts to fetch (default: 5)")
    parser.add_argument(
        "--session-username",
        help="Instagram username for authentication session",
    )
    parser.add_argument(
        "--session-file",
        help="Path to Instaloader session file (e.g., data/sessions/instagram.session)",
    )

    args = parser.parse_args()

    # Validate session arguments
    if bool(args.session_username) != bool(args.session_file):
        parser.error("Both --session-username and --session-file must be provided together")

    asyncio.run(
        fetch_and_save_posts(
            args.username,
            args.limit,
            args.session_username,
            args.session_file,
        )
    )


if __name__ == "__main__":
    main()
