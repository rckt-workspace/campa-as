"""Audit service for comparing posts across accounts"""
from datetime import datetime
from app.domain.models import AuditResult, PostAuditStatus, InstagramPost, MatchStatus
from app.domain.matcher import ContentMatcher, ExactContentMatcher, PerceptualContentMatcher
from app.domain.matcher_config import MatcherConfig


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
        review_count_by_account = {account: 0 for account in compared_accounts}
        found_in_all_count = 0
        with_missing_count = 0
        with_review_count = 0

        for master_post in master_posts:
            account_status = {}
            missing_in = []
            review_in = []

            for account, posts in account_posts.items():
                # Find best match for this post in this account
                best_result = None

                for candidate in posts:
                    # Get match result (always MatchResult)
                    result = self.matcher.match(master_post, candidate)

                    # Keep track of best match by score
                    if best_result is None or result.score > best_result.score:
                        best_result = result

                # Determine status for this account
                if best_result is None:
                    status = "missing"
                else:
                    # MatchResult object
                    status = best_result.status.value

                account_status[account] = status

                if status == "missing":
                    missing_in.append(account)
                    missing_count_by_account[account] += 1
                elif status == "review":
                    review_in.append(account)
                    review_count_by_account[account] += 1

            post_status = PostAuditStatus(
                master_post=master_post,
                account_status=account_status,
                missing_in=missing_in,
                review_in=review_in,
            )
            posts_status.append(post_status)

            # Count posts with issues
            if missing_in or review_in:
                if missing_in and not review_in:
                    with_missing_count += 1
                elif review_in and not missing_in:
                    with_review_count += 1
                elif missing_in and review_in:
                    # Post has both - count in missing for now
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
            with_review=with_review_count,
            missing_count_by_account=missing_count_by_account,
            review_count_by_account=review_count_by_account,
            timestamp=datetime.now(),
        )
