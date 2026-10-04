#!/usr/bin/env python3
"""
Test the MINIMAL query that was verified in Graph API Explorer.

Does NOT use expanded visual fields.
Goal: Determine if the issue is the expanded query or configuration.
"""
import asyncio
import os
import sys
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_minimal():
    """Test the known-working minimal query directly"""
    print("\n" + "=" * 70)
    print("MINIMAL QUERY TEST")
    print("=" * 70)

    # Check credentials
    ig_user_id = os.getenv("META_IG_USER_ID")
    access_token = os.getenv("META_ACCESS_TOKEN")
    api_version = os.getenv("META_GRAPH_API_VERSION", "v26.0")

    if not (ig_user_id and access_token):
        print("\n❌ Missing credentials")
        return

    print(f"\nAPI Version: {api_version}")
    print(f"IG User ID: ***configured***")
    print(f"Access Token: ***configured***")

    # This is the MINIMAL query verified in Graph API Explorer
    minimal_fields = (
        "business_discovery.username(newbodycol)"
        "{"
        "  id,"
        "  username,"
        "  media.limit(10)"
        "  {"
        "    id,"
        "    caption,"
        "    media_type,"
        "    permalink,"
        "    timestamp"
        "  }"
        "}"
    )

    print(f"\nQuery: business_discovery.username(newbodycol) + media.limit(10)")
    print(f"Fields: id, caption, media_type, permalink, timestamp (NO thumbnails, media_url, children)")

    base_url = f"https://graph.facebook.com/{api_version}"

    try:
        print(f"\nFetching...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{base_url}/{ig_user_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"fields": minimal_fields},
            )

            print(f"HTTP Status: {response.status_code}")

            data = response.json()

            # Check for error
            if "error" in data:
                error = data["error"]
                print(f"\n❌ API ERROR:")
                print(f"   Code: {error.get('code')}")
                print(f"   Type: {error.get('type')}")
                print(f"   Message: {error.get('message')}")
                if "error_subcode" in error:
                    print(f"   Subcode: {error.get('error_subcode')}")
                return

            # Check for Business Discovery
            bd = data.get("business_discovery", {})
            if not bd:
                print(f"\n❌ No business_discovery in response")
                print(f"Response keys: {list(data.keys())}")
                return

            # Count media
            media = bd.get("media", {})
            media_list = media.get("data", [])
            posts = len(media_list)

            print(f"\n✅ SUCCESS!")
            print(f"   Target username: {bd.get('username')}")
            print(f"   Target ID: {bd.get('id')}")
            print(f"   Posts retrieved: {posts}")

            if posts > 0:
                print(f"\n   Sample posts:")
                for i, p in enumerate(media_list[:3], 1):
                    print(f"      {i}. {p.get('media_type')}: {p.get('caption', '')[:50]}...")
                    print(f"         {p.get('permalink')}")

            print(f"\n   🎯 MINIMAL QUERY WORKS!")
            print(f"\n   Conclusion: Field expansion might be the issue.")

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(test_minimal())
