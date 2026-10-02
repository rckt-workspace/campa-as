"""Run audit using fixture data"""
import json
from datetime import datetime
from pathlib import Path
from app.domain.models import InstagramPost, PostType
from app.services.audit_service import AuditService
from app.exporters.excel_exporter import ExcelExporter


def load_fixture(fixture_path: str) -> list[InstagramPost]:
    """Load fixture JSON and convert to InstagramPost objects"""
    with open(fixture_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    posts = []
    for post_data in data['posts']:
        # Convert published_at string to datetime
        published_at = post_data['published_at']
        if isinstance(published_at, str):
            published_at = datetime.fromisoformat(published_at)

        # Convert post_type string to PostType enum
        post_type = post_data['post_type']
        if isinstance(post_type, str):
            post_type = PostType(post_type)

        post = InstagramPost(
            shortcode=post_data['shortcode'],
            username=post_data['username'],
            caption=post_data['caption'],
            post_type=post_type,
            published_at=published_at,
            permalink=post_data['permalink'],
            thumbnail_url=post_data['thumbnail_url'],
            is_video=post_data['is_video'],
            media_count=post_data['media_count'],
        )
        posts.append(post)

    return posts


def main():
    """Run fixture audit"""
    print("\n" + "="*80)
    print("NEWBODY CONTENT AUDIT - FIXTURE TEST")
    print("="*80 + "\n")

    # Load fixtures
    fixture_dir = Path(__file__).parent.parent.parent / "tests" / "fixtures"

    print("Loading fixtures...")
    master_posts = load_fixture(fixture_dir / "newbodycol.json")

    account_posts = {
        "newbodyclubmedellin": load_fixture(fixture_dir / "newbodyclubmedellin.json"),
        "newbodyclubantienvejecimientoc": load_fixture(fixture_dir / "newbodyclubantienvejecimientoc.json"),
        "newbodybaq": load_fixture(fixture_dir / "newbodybaq.json"),
    }
    print(f"✓ Loaded {len(master_posts)} master posts")
    print(f"✓ Loaded posts for {len(account_posts)} regional accounts\n")

    # Run audit
    print("Running audit service...")
    service = AuditService()
    result = service.audit_accounts(
        master_posts=master_posts,
        account_posts=account_posts,
        master_account="newbodycol",
    )
    print("✓ Audit completed\n")

    # Print metrics
    print("METRICS:")
    print(f"  Master posts: {result.total_master_posts}")
    print(f"  Found everywhere: {result.found_in_all}")
    print(f"  With missing accounts: {result.with_missing}")
    print()

    print("MISSING BY ACCOUNT:")
    for account, count in result.missing_count_by_account.items():
        print(f"  {account}: {count}")
    print()

    # Export to Excel
    print("Generating Excel...")
    exporter = ExcelExporter()
    excel_path = exporter.export(result)
    print(f"✓ Excel generated: {excel_path}\n")

    # Print summary of missing posts
    print("POSTS WITH MISSING ACCOUNTS:")
    for i, post_status in enumerate(result.posts_status, 1):
        if post_status.missing_in:
            print(f"  {i}. {post_status.master_post.shortcode} - Missing in: {', '.join(post_status.missing_in)}")

    print("\n" + "="*80)
    print(f"Audit complete. Results saved to: {excel_path}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
