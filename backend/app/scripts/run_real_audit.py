"""Run real audit against Instagram accounts"""
import asyncio
import argparse
import logging
from pathlib import Path

from app.config import AccountConfig, ScanConfig
from app.providers.instagram import InstaloaderInstagramProvider
from app.providers.browser_instagram import BrowserInstagramProvider
from app.services.scan_service import ScanService
from app.domain.exceptions import (
    InstagramProviderException,
    TooManyRequestsException,
    LoginRequiredException,
    ProfileNotFoundException,
    PrivateProfileException,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Run real Instagram audit"""
    parser = argparse.ArgumentParser(description="Run real Instagram content audit")
    parser.add_argument(
        "--master",
        type=str,
        default="newbodycol",
        help="Master Instagram account (default: newbodycol)",
    )
    parser.add_argument(
        "--compare",
        type=str,
        action="append",
        dest="comparison_accounts",
        help="Regional account to compare (can use multiple times)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Master account post limit (default: 5)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="browser",
        choices=["browser", "instaloader"],
        help="Provider to use: browser (Playwright, default) or instaloader",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Playwright in headed mode (visible browser) for debugging",
    )
    parser.add_argument(
        "--session-username",
        type=str,
        default=None,
        help="Instagram username for authenticated session (Instaloader only)",
    )
    parser.add_argument(
        "--session-file",
        type=str,
        default=None,
        help="Path to Instaloader session file",
    )

    args = parser.parse_args()

    print("\n" + "="*80)
    print("NEWBODY CONTENT AUDIT - REAL INSTAGRAM")
    print("="*80 + "\n")

    provider = None
    try:
        # Initialize provider
        logger.info(f"Initializing {args.provider} provider")

        if args.provider == "browser":
            provider = BrowserInstagramProvider(headless=not args.headed)
            logger.info("Using public Instagram browsing via Playwright")
        elif args.provider == "instaloader":
            if args.session_file:
                logger.info(f"Using authenticated session: {args.session_username}")
                provider = InstaloaderInstagramProvider(
                    session_username=args.session_username,
                    session_file=Path(args.session_file),
                )
            else:
                logger.info("Using anonymous Instaloader access")
                provider = InstaloaderInstagramProvider()
        else:
            raise ValueError(f"Unknown provider: {args.provider}")

        # Configure scan with CLI arguments
        if args.comparison_accounts is None:
            # Use defaults if not specified
            comparison_accounts = None
        else:
            comparison_accounts = args.comparison_accounts

        account_config = AccountConfig(
            master_account=args.master,
            comparison_accounts=comparison_accounts,
        )
        scan_config = ScanConfig(master_limit=args.limit)

        print(f"Configuration:")
        print(f"  Provider: {args.provider}")
        print(f"  Master account: {account_config.master_account}")
        print(f"  Regional accounts: {', '.join(account_config.comparison_accounts)}")
        print(f"  Master limit: {args.limit}")
        print(f"  Regional limit: {scan_config.regional_limit}")
        print()

        # Run scan
        service = ScanService(
            provider=provider,
            account_config=account_config,
            scan_config=scan_config,
        )

        logger.info("Starting audit scan")
        result = await service.scan()

        # Print results
        print(result.summary())
        print()

        print("="*80)
        print("Audit completed successfully")
        print("="*80 + "\n")

    except TooManyRequestsException as e:
        print(f"\n❌ ERROR: {e}")
        print("Instagram rate limit reached. Please try again later.\n")
        return 1
    except LoginRequiredException as e:
        print(f"\n❌ ERROR: {e}")
        print("Authentication required. Use --session-username and --session-file\n")
        return 1
    except (ProfileNotFoundException, PrivateProfileException) as e:
        print(f"\n❌ ERROR: {e}\n")
        return 1
    except InstagramProviderException as e:
        print(f"\n❌ ERROR: {e}\n")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}: {e}", exc_info=True)
        print(f"\n❌ Unexpected error: {e}\n")
        return 1
    finally:
        # Close browser if using Playwright
        if provider and isinstance(provider, BrowserInstagramProvider):
            try:
                await provider.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
