"""Utility functions"""
import re
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


def normalize_instagram_username(value: str) -> str:
    """
    Normalize Instagram username to clean format.

    Accepts:
        @newbodycol
        newbodycol
        https://instagram.com/newbodycol/
        https://www.instagram.com/newbodycol/

    Returns:
        newbodycol

    Raises:
        ValueError: If username is invalid
    """
    if not value:
        raise ValueError("Username cannot be empty")

    # Remove leading @
    username = value.lstrip("@").strip()

    # Extract from URL
    url_match = re.search(r"instagram\.com/([a-zA-Z0-9._-]+)", username)
    if url_match:
        username = url_match.group(1)

    # Remove trailing slash/path
    username = username.rstrip("/").split("/")[0].strip()

    # Validate: only alphanumeric, dot, underscore, hyphen
    if not re.match(r"^[a-zA-Z0-9._-]+$", username):
        raise ValueError(
            f"Invalid Instagram username: {value}. "
            "Only alphanumeric, dot, underscore, and hyphen allowed."
        )

    # Must be at least 1 character
    if len(username) < 1 or len(username) > 30:
        raise ValueError(
            f"Invalid username length: {len(username)}. "
            "Instagram usernames must be 1-30 characters."
        )

    return username


def clean_caption(caption: str) -> str:
    """
    Clean caption for presentation: remove Instagram metadata, unescape HTML.

    Args:
        caption: Raw caption from Instagram

    Returns:
        Clean caption suitable for display
    """
    if not caption:
        return ""

    from html import unescape

    caption = unescape(caption)

    # Remove Instagram metadata pattern: "N likes/comments - username el/on DATE:"
    pattern = r"^\d+\s+likes?,\s+\d+\s+comments?\s*-\s*\w+\s+(?:on|el)\s+\w+\s+\d+,\s+\d+:\s*"
    caption = re.sub(pattern, "", caption, flags=re.IGNORECASE)

    return caption.strip()


def to_bogota_time(dt: datetime) -> datetime:
    """
    Convert datetime to Bogota timezone (UTC-5).

    If datetime is timezone-naive, assumes UTC.
    Preserves the actual moment in time, just changes the display timezone.

    Args:
        dt: datetime object (naive or aware)

    Returns:
        datetime in Bogota timezone (America/Bogota, UTC-5)
    """
    if dt is None:
        return None

    # If naive, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Convert to Bogota timezone using ZoneInfo
    bogota_tz = ZoneInfo("America/Bogota")
    return dt.astimezone(bogota_tz)
