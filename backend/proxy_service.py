import requests
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import asyncio
import threading
from fastapi import HTTPException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
PROXY_SCRAPE_API_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get"
API_PARAMS = {
    "request": "get_proxies",
    "skip": 0,
    "proxy_format": "protocolipport",
    "format": "json",
    "limit": 15
}
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://proxyscrape.com",
    "Referer": "https://proxyscrape.com/",
    "Accept": "application/json, text/plain, */*"
}
REQUEST_TIMEOUT = 10  # seconds

# In-memory cache for proxies
proxy_cache = {
    "proxies": [],
    "last_updated": None,
    "lock": threading.Lock()
}

def fetch_proxies_from_api() -> List[str]:
    """
    Fetch proxies from ProxyScrape API with proper headers and timeout handling.

    Returns:
        List[str]: List of proxy strings in protocolipport format

    Raises:
        HTTPException: If API request fails
    """
    try:
        logger.info("Fetching proxies from ProxyScrape API")

        response = requests.get(
            PROXY_SCRAPE_API_URL,
            params=API_PARAMS,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        # Parse JSON response
        data = response.json()
        if not isinstance(data, dict) or "proxies" not in data:
            logger.error("Unexpected API response format")
            raise HTTPException(
                status_code=500,
                detail="Unexpected API response format"
            )

        proxies_data = data.get("proxies", [])
        if not isinstance(proxies_data, list):
            logger.error("Proxies data is not a list")
            raise HTTPException(
                status_code=500,
                detail="Proxies data is not a list"
            )

        # Extract proxy strings from the proxy objects
        proxies = []
        for proxy_obj in proxies_data:
            if isinstance(proxy_obj, dict) and "proxy" in proxy_obj:
                proxy_str = proxy_obj["proxy"]
                if isinstance(proxy_str, str) and proxy_str.strip():
                    proxies.append(proxy_str)

        logger.info(f"Successfully fetched {len(proxies)} proxies from API")
        return proxies

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"API request failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching proxies: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

def sanitize_proxies(proxies: List[str]) -> List[str]:
    """
    Sanitize proxy strings to ensure they are in protocolipport format.

    Args:
        proxies (List[str]): List of proxy strings

    Returns:
        List[str]: List of sanitized proxy strings
    """
    if not proxies:
        return []

    sanitized = []
    for proxy in proxies:
        if not proxy or not isinstance(proxy, str):
            continue

        # Remove any whitespace and ensure proper format
        proxy = proxy.strip()
        if not proxy:
            continue

        # Basic validation - should contain protocol, IP, and port
        if ":" in proxy and "." in proxy:
            sanitized.append(proxy)

    logger.info(f"Sanitized {len(sanitized)} proxies from {len(proxies)} raw entries")
    return sanitized

def get_cached_proxies() -> List[str]:
    """
    Get cached proxies with thread-safe access.

    Returns:
        List[str]: List of cached proxy strings
    """
    with proxy_cache["lock"]:
        return proxy_cache["proxies"].copy()

def update_cache(proxies: List[str]):
    """
    Update the proxy cache with new data.

    Args:
        proxies (List[str]): List of proxy strings to cache
    """
    with proxy_cache["lock"]:
        proxy_cache["proxies"] = sanitize_proxies(proxies)
        proxy_cache["last_updated"] = datetime.utcnow()
        logger.info(f"Cache updated with {len(proxy_cache['proxies'])} proxies")

def is_cache_valid() -> bool:
    """
    Check if the current cache is valid (less than 24 hours old).

    Returns:
        bool: True if cache is valid, False otherwise
    """
    with proxy_cache["lock"]:
        if not proxy_cache["last_updated"]:
            return False

        time_since_update = datetime.utcnow() - proxy_cache["last_updated"]
        return time_since_update < timedelta(hours=24)

def initialize_cache():
    """
    Initialize the proxy cache at system boot.
    If cache is null or >24h old, trigger a fresh fetch from ProxyScrape.
    """
    logger.info("Initializing proxy cache")

    if is_cache_valid():
        logger.info("Valid cache found, no need to refresh")
        return

    logger.info("Cache is invalid or empty, fetching fresh proxies")
    try:
        proxies = fetch_proxies_from_api()
        update_cache(proxies)
    except Exception as e:
        logger.error(f"Failed to initialize cache: {str(e)}")
        # If initialization fails, we'll have an empty cache
        # This is acceptable as the background task will retry

def refresh_cache_background():
    """
    Background task to refresh the proxy cache.
    """
    logger.info("Starting background cache refresh")

    try:
        proxies = fetch_proxies_from_api()
        update_cache(proxies)
        logger.info("Background cache refresh completed successfully")
    except Exception as e:
        logger.error(f"Background cache refresh failed: {str(e)}")

def start_background_task():
    """
    Start the 24-hour background refresh task.

    Returns:
        threading.Timer: The timer object for the background task
    """
    # Calculate time until next refresh (24 hours from now)
    next_refresh_time = 24 * 60 * 60  # 24 hours in seconds

    logger.info(f"Scheduling background refresh in {next_refresh_time} seconds")

    # Create and start the timer
    refresh_timer = threading.Timer(next_refresh_time, refresh_cache_background)
    refresh_timer.daemon = True  # Daemon thread will exit when main program exits
    refresh_timer.start()

    return refresh_timer

def manual_refresh():
    """
    Manually trigger a cache refresh.

    Returns:
        Dict[str, Any]: Result of the refresh operation
    """
    try:
        proxies = fetch_proxies_from_api()
        update_cache(proxies)

        return {
            "success": True,
            "message": "Cache refreshed successfully",
            "proxy_count": len(proxies),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Manual refresh failed: {str(e)}")
        return {
            "success": False,
            "message": f"Refresh failed: {str(e)}",
            "proxy_count": 0,
            "timestamp": datetime.utcnow().isoformat()
        }