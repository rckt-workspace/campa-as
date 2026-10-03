"""Central configuration for Instagram accounts and scanning"""
from dataclasses import dataclass, field
from datetime import date
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
    account_labels: dict[str, str] = field(default_factory=lambda: {
        "newbodycol": "Colombia",
        "newbodyclubmedellin": "Medellín",
        "newbodyclubantienvejecimientoc": "Antienvejecimiento",
        "newbodybaq": "Barranquilla",
    })

    def __post_init__(self):
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
    master_limit: int | None = 20
    from_date: date | None = None
    to_date: date | None = None
    regional_multiplier: float = 2.0

    @property
    def regional_limit(self) -> int:
        """Calculate regional limit based on master limit"""
        if self.master_limit is None:
            # Date mode: no artificial limit, will be filtered by actual date range
            # Safety limit is handled in provider (MAX_DATE_SCROLLS)
            return 1000  # High safety limit, not a filter
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
