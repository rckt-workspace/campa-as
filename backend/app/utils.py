"""Utility functions"""
import re


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
