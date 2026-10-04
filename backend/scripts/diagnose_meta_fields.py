#!/usr/bin/env python3
"""
Progressive field diagnosis for Meta Graph API Business Discovery.

Tests which fields are supported by progressively adding fields to the query.
"""
import asyncio
import os
import sys
import httpx
import logging

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_query(
    query_name: str,
    fields: str,
    ig_user_id: str,
    access_token: str,
    api_version: str = "v26.0",
) -> tuple[bool, int, dict]:
    """
    Test a specific field configuration.

    Returns:
        (works: bool, posts: int, response_dict)
    """
    print(f"\nTesting: {query_name}")
    print(f"  Fields: {fields[:60]}...")

    base_url = f"https://graph.facebook.com/{api_version}"
    full_fields = f"business_discovery.username(newbodycol){{{fields}}}"

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{base_url}/{ig_user_id}",
                headers=headers,
                params={
                    "fields": full_fields,
                },
            )

            data = response.json()

            # Check for API error
            if "error" in data:
                error = data["error"]
                code = error.get("code")
                msg = error.get("message", "")
                print(f"  ❌ HTTP {response.status_code}: code={code}, msg={msg[:80]}")
                return False, 0, data

            # Check for Business Discovery response
            bd = data.get("business_discovery", {})
            if not bd:
                print(f"  ❌ No business_discovery in response")
                return False, 0, data

            # Count media
            media = bd.get("media", {})
            media_list = media.get("data", [])
            posts = len(media_list)

            print(f"  ✅ HTTP {response.status_code}: {posts} posts")
            return True, posts, data

    except Exception as e:
        print(f"  ❌ Exception: {type(e).__name__}: {str(e)[:80]}")
        return False, 0, {}


async def main():
    """Run progressive field test"""
    print("\n" + "=" * 70)
    print("META GRAPH API FIELD DIAGNOSIS")
    print("=" * 70)

    # Check credentials
    ig_user_id = os.getenv("META_IG_USER_ID")
    access_token = os.getenv("META_ACCESS_TOKEN")
    api_version = os.getenv("META_GRAPH_API_VERSION", "v26.0")

    if not (ig_user_id and access_token):
        print("\n❌ Missing META_IG_USER_ID or META_ACCESS_TOKEN")
        return

    print(f"\nConfiguration:")
    print(f"  API Version: {api_version}")
    print(f"  IG User ID: ***configured***")
    print(f"  Access Token: ***configured***")

    # Define progressive field sets
    tests = [
        (
            "MINIMAL (baseline - known working)",
            "id,username,media.limit(3){id,caption,media_type,permalink,timestamp}",
        ),
        (
            "A: Add media_url",
            "id,username,media.limit(3){id,caption,media_type,media_url,permalink,timestamp}",
        ),
        (
            "B: Add thumbnail_url",
            "id,username,media.limit(3){id,caption,media_type,media_url,thumbnail_url,permalink,timestamp}",
        ),
        (
            "C: Add media_product_type",
            "id,username,media.limit(3){id,caption,media_type,media_product_type,media_url,thumbnail_url,permalink,timestamp}",
        ),
        (
            "D: Add children (minimal)",
            "id,username,media.limit(3){id,caption,media_type,media_product_type,media_url,thumbnail_url,permalink,timestamp,children{id,media_type,media_url}}",
        ),
        (
            "E: Add children with thumbnail",
            "id,username,media.limit(3){id,caption,media_type,media_product_type,media_url,thumbnail_url,permalink,timestamp,children{id,media_type,media_url,thumbnail_url}}",
        ),
    ]

    # Run tests
    results = []
    for query_name, fields in tests:
        works, posts, response = await test_query(
            query_name,
            fields,
            ig_user_id,
            access_token,
            api_version,
        )
        results.append((query_name, works, posts, response))

    # Summary
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    print("\n{:<50} | HTTP | Posts".format("Field Set"))
    print("-" * 70)

    working_set = None
    for name, works, posts, response in results:
        status = "✅" if works else "❌"
        print(f"{status} {name:<47} | {posts:>4} posts")
        if works and posts > 0 and not working_set:
            working_set = name

    print("\n" + "=" * 70)

    if working_set:
        print(f"\n🎯 DIAGNOSIS: {working_set} works!")
        print("\nRecommendation:")
        if "MINIMAL" in working_set:
            print("  Use MINIMAL field set for production.")
            print("  Visual fields may need alternative approach.")
        elif "A:" in working_set:
            print("  Use field set A (media_url) for production.")
        elif "B:" in working_set:
            print("  Use field set B (thumbnail_url) for production.")
        elif "C:" in working_set:
            print("  Use field set C (media_product_type) for production.")
        else:
            print("  Use working field set for production.")
    else:
        print("\n❌ DIAGNOSIS: No field set returned posts!")
        print("\nThis indicates:")
        print("  - Business Discovery may not be accessible for this account")
        print("  - Or the source IG User ID doesn't have permission")
        print("  - Or there's an API-level configuration issue")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
