"""Central configuration for Instagram accounts and scanning"""
from dataclasses import dataclass, field
from app.utils import normalize_instagram_username


@dataclass
class AccountConfig:
    """Configuration for Instagram accounts to scan"""
    master_account: str = "newbodycol"
    comparison_accounts: list[str] = field(default_factory=lambda: [
        "newbodyclubmedellin",
        "newbodyclubantienvejecimientoc",
        "newbodybaq",
    ])

    def __post_init__(self):
        # Normalize all usernames
        self.master_account = normalize_instagram_username(self.master_account)
        self.comparison_accounts = [
            normalize_instagram_username(acc) for acc in self.comparison_accounts
        ]

    def all_accounts(self) -> list[str]:
        """Return all accounts including master"""
        return [self.master_account] + self.comparison_accounts


@dataclass
class ScanConfig:
    """Configuration for scanning behavior"""
    master_limit: int = 20
    regional_multiplier: float = 2.0

    @property
    def regional_limit(self) -> int:
        """Calculate regional limit based on master limit"""
        return int(self.master_limit * self.regional_multiplier)

    # Media cache settings
    media_cache_dir: str = "data/cache"
    media_timeout: float = 10.0

    # Instagram settings
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    max_retries: int = 1


# Default instances
DEFAULT_ACCOUNT_CONFIG = AccountConfig()
DEFAULT_SCAN_CONFIG = ScanConfig()
