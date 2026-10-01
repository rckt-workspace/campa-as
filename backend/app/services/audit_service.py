from app.providers.instagram import InstagramProvider
from app.repositories.base import Repository


class AuditService:
    """Orchestrates audit logic"""

    def __init__(self, instagram_provider: InstagramProvider, repository: Repository):
        self.instagram = instagram_provider
        self.repository = repository

    async def audit_accounts(self, master_account: str, comparison_accounts: list[str]) -> dict:
        """Compare master account posts with comparison accounts"""
        return {
            "status": "ok",
            "message": "Audit service initialized",
        }
