from datetime import datetime
from app.domain.models import AuditResult, PostAuditStatus, InstagramPost
from app.domain.matcher import ContentMatcher, ExactContentMatcher


class AuditService:
    """Orchestrates audit logic for comparing posts across accounts"""

    def __init__(self, matcher: ContentMatcher = None):
        self.matcher = matcher or ExactContentMatcher()

    def audit_accounts(
        self,
        master_posts: list[InstagramPost],
        account_posts: dict[str, list[InstagramPost]],
        master_account: str = "newbodycol",
    ) -> AuditResult:
        """Compare master posts with regional account posts"""
        compared_accounts = list(account_posts.keys())
        posts_status = []
        missing_count_by_account = {account: 0 for account in compared_accounts}
        found_in_all_count = 0
        with_missing_count = 0

        for master_post in master_posts:
            account_status = {}
            missing_in = []

            for account, posts in account_posts.items():
                # Check if this master post is found in this account
                found = any(
                    self.matcher.is_same_content(master_post, candidate)
                    for candidate in posts
                )

                status = "found" if found else "missing"
                account_status[account] = status

                if not found:
                    missing_in.append(account)
                    missing_count_by_account[account] += 1

            post_status = PostAuditStatus(
                master_post=master_post,
                account_status=account_status,
                missing_in=missing_in,
            )
            posts_status.append(post_status)

            # Count posts with at least one missing account
            if missing_in:
                with_missing_count += 1
            else:
                found_in_all_count += 1

        return AuditResult(
            master_account=master_account,
            compared_accounts=compared_accounts,
            posts_status=posts_status,
            total_master_posts=len(master_posts),
            found_in_all=found_in_all_count,
            with_missing=with_missing_count,
            missing_count_by_account=missing_count_by_account,
            timestamp=datetime.now(),
        )
