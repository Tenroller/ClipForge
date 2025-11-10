#!/usr/bin/env python3
"""Utility script to update yt-dlp to the latest version.

Usage:
    python backend/update_yt_dlp.py

Or integrate into startup by importing in app.py:
    from backend.update_yt_dlp import auto_update_on_startup
    auto_update_on_startup()
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.utils.youtube import update_yt_dlp, check_yt_dlp_version

try:
    from logging_config import get_logger
except ImportError:
    from backend.logging_config import get_logger

logger = get_logger("update_yt_dlp")


def auto_update_on_startup(check_interval_days: int = 7):
    """Optional: Call this in app.py to auto-update yt-dlp on startup.

    Args:
        check_interval_days: Only update if last check was more than N days ago
    """
    from datetime import datetime, timedelta
    import os

    last_check_file = Path(__file__).parent / ".yt_dlp_last_check"

    try:
        # Check if we updated recently
        if last_check_file.exists():
            last_check = datetime.fromtimestamp(last_check_file.stat().st_mtime)
            if datetime.now() - last_check < timedelta(days=check_interval_days):
                logger.debug(f"yt-dlp update check skipped (last check: {last_check.strftime('%Y-%m-%d')})")
                return

        current_version = check_yt_dlp_version()
        logger.info(f"Current yt-dlp version: {current_version}")
        logger.info("Updating yt-dlp to latest version...")

        success = update_yt_dlp()

        if success:
            # Touch the file to record last check time
            last_check_file.touch()
            new_version = check_yt_dlp_version()
            if new_version and new_version != current_version:
                logger.info(f"yt-dlp updated: {current_version} -> {new_version}")
            else:
                logger.info("yt-dlp is already up to date")
        else:
            logger.warning("yt-dlp update failed, continuing with current version")

    except Exception as e:
        logger.error(f"Error during yt-dlp auto-update: {e}")
        # Don't fail startup if update fails


if __name__ == "__main__":
    """Run this script to manually update yt-dlp"""
    print("=" * 60)
    print("yt-dlp Update Utility")
    print("=" * 60)

    current_version = check_yt_dlp_version()
    if current_version:
        print(f"Current version: {current_version}")
    else:
        print("Current version: Not installed or could not detect")

    print("\nUpdating yt-dlp to latest version from GitHub...")
    print("This may take a minute...")

    success = update_yt_dlp()

    if success:
        new_version = check_yt_dlp_version()
        print("\n✓ Update successful!")
        if new_version:
            print(f"New version: {new_version}")
            if current_version and new_version != current_version:
                print(f"Upgraded from {current_version} to {new_version}")
    else:
        print("\n✗ Update failed. Check logs above for details.")
        sys.exit(1)

    print("=" * 60)
