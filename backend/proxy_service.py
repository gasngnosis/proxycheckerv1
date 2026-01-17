import requests
import logging
import time
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import HTTPException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
PROXY_SCRAPE_API_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get"
GITHUB_PROXY_LIST_URL = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
SPEEDX_PROXY_LIST_URL = "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt"
API_PARAMS = {
    "request": "get_proxies",
    "skip": 0,
    "proxy_format": "protocolipport",
    "format": "json",
    "limit": 500
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

# Constants for proxy testing
TEST_URL = "http://httpbin.org/ip"
TEST_TIMEOUT = 12  # seconds
MAX_CONCURRENT_TESTS = 40  # Limit concurrent tests to avoid server overload

def fetch_proxies_from_github() -> List[str]:
    """
    Fetch proxies from GitHub raw proxy list.

    Returns:
        List[str]: List of proxy strings in ip:port format

    Raises:
        HTTPException: If GitHub request fails
    """
    try:
        logger.info("Fetching proxies from GitHub proxy list")

        response = requests.get(
            GITHUB_PROXY_LIST_URL,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        # Get text content and split by lines
        proxy_text = response.text
        proxies = []

        for line in proxy_text.split('\n'):
            line = line.strip()
            if line and ':' in line and '.' in line:
                # Add http:// prefix to make it consistent with ProxyScrape format
                proxies.append(f"http://{line}")

        logger.info(f"Successfully fetched {len(proxies)} proxies from GitHub")
        return proxies

    except requests.exceptions.RequestException as e:
        logger.error(f"GitHub request failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"GitHub request failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching GitHub proxies: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

def fetch_proxies_from_speedx() -> List[str]:
    """
    Fetch proxies from TheSpeedX SOCKS List on GitHub.

    Returns:
        List[str]: List of proxy strings in ip:port format

    Raises:
        HTTPException: If SpeedX request fails
    """
    try:
        logger.info("Fetching proxies from TheSpeedX SOCKS List")

        response = requests.get(
            SPEEDX_PROXY_LIST_URL,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        # Get text content and split by lines
        proxy_text = response.text
        proxies = []

        for line in proxy_text.split('\n'):
            line = line.strip()
            if line and ':' in line and '.' in line:
                # Add http:// prefix to make it consistent with other sources
                proxies.append(f"http://{line}")

        logger.info(f"Successfully fetched {len(proxies)} proxies from TheSpeedX")
        return proxies

    except requests.exceptions.RequestException as e:
        logger.error(f"TheSpeedX request failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"TheSpeedX request failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching TheSpeedX proxies: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

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

def test_proxy(proxy: str) -> bool:
    """
    Test a single proxy to check if it's working.

    Args:
        proxy (str): Proxy string in format ip:port or protocol://ip:port

    Returns:
        bool: True if proxy is working, False otherwise
    """
    try:
        # Extract just the ip:port part for testing
        proxy_parts = proxy.replace("http://", "").replace("https://", "")
        if ":" not in proxy_parts:
            return False

        proxies_dict = {
            "http": f"http://{proxy_parts}",
            "https": f"http://{proxy_parts}",
        }

        start_time = time.time()
        response = requests.get(
            TEST_URL,
            proxies=proxies_dict,
            timeout=TEST_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 AzureCheck"}
        )

        # Check if request was successful and reasonably fast
        elapsed = time.time() - start_time
        return response.status_code == 200 and elapsed < TEST_TIMEOUT

    except Exception as e:
        logger.debug(f"Proxy {proxy} failed: {str(e)}")
        return False

def test_proxies_in_batches(proxies: List[str], batch_size: int = 100) -> List[str]:
    """
    Test proxies in batches to avoid overwhelming the server.

    Args:
        proxies (List[str]): List of proxy strings to test
        batch_size (int): Number of proxies to test in each batch

    Returns:
        List[str]: List of working proxy strings
    """
    working_proxies = []
    total_proxies = len(proxies)
    logger.info(f"Starting to test {total_proxies} proxies in batches of {batch_size}")

    for i in range(0, total_proxies, batch_size):
        batch = proxies[i:i + batch_size]
        logger.info(f"Testing batch {i//batch_size + 1}/{math.ceil(total_proxies/batch_size)} with {len(batch)} proxies")

        batch_working = []
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TESTS) as executor:
            # Submit all proxies in this batch for testing
            future_to_proxy = {
                executor.submit(test_proxy, proxy): proxy
                for proxy in batch
            }

            # Collect results as they complete
            for future in as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    is_working = future.result()
                    if is_working:
                        batch_working.append(proxy)
                except Exception as e:
                    logger.error(f"Error testing proxy {proxy}: {str(e)}")

        working_proxies.extend(batch_working)
        logger.info(f"Batch completed: {len(batch_working)}/{len(batch)} proxies working")

    logger.info(f"Proxy testing complete: {len(working_proxies)}/{total_proxies} proxies are working")
    return working_proxies

def update_cache(proxies: List[str]):
    """
    Update the proxy cache with new data.
    Now includes automatic testing of proxies before caching.

    Args:
        proxies (List[str]): List of proxy strings to cache
    """
    with proxy_cache["lock"]:
        # First sanitize the proxies
        sanitized_proxies = sanitize_proxies(proxies)
        logger.info(f"Sanitized {len(sanitized_proxies)} proxies, starting testing...")

        # Test all proxies and only keep working ones
        working_proxies = test_proxies_in_batches(sanitized_proxies)

        # Update cache with only working proxies
        proxy_cache["proxies"] = working_proxies
        proxy_cache["last_updated"] = datetime.utcnow()
        logger.info(f"Cache updated with {len(working_proxies)} working proxies")

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
        proxies = fetch_combined_proxies()
        update_cache(proxies)
    except Exception as e:
        logger.error(f"Failed to initialize cache: {str(e)}")
        # If initialization fails, we'll have an empty cache
        # This is acceptable as the background task will retry

def fetch_combined_proxies() -> List[str]:
    """
    Fetch proxies from both ProxyScrape API and GitHub proxy list,
    then combine and deduplicate them.

    Returns:
        List[str]: Combined list of unique proxy strings
    """
    combined_proxies = []
    errors = []

    # Try to fetch from ProxyScrape API
    try:
        api_proxies = fetch_proxies_from_api()
        combined_proxies.extend(api_proxies)
        logger.info(f"Added {len(api_proxies)} proxies from ProxyScrape API")
    except Exception as e:
        errors.append(f"ProxyScrape API failed: {str(e)}")
        logger.error(f"ProxyScrape API failed: {str(e)}")

    # Try to fetch from GitHub proxy list
    try:
        github_proxies = fetch_proxies_from_github()
        combined_proxies.extend(github_proxies)
        logger.info(f"Added {len(github_proxies)} proxies from GitHub")
    except Exception as e:
        errors.append(f"GitHub proxy list failed: {str(e)}")
        logger.error(f"GitHub proxy list failed: {str(e)}")

    # Try to fetch from TheSpeedX SOCKS List
    try:
        speedx_proxies = fetch_proxies_from_speedx()
        combined_proxies.extend(speedx_proxies)
        logger.info(f"Added {len(speedx_proxies)} proxies from TheSpeedX")
    except Exception as e:
        errors.append(f"TheSpeedX proxy list failed: {str(e)}")
        logger.error(f"TheSpeedX proxy list failed: {str(e)}")

    # Deduplicate proxies while preserving order
    seen = set()
    unique_proxies = []
    for proxy in combined_proxies:
        if proxy not in seen:
            seen.add(proxy)
            unique_proxies.append(proxy)

    logger.info(f"Combined {len(unique_proxies)} unique proxies from {len(combined_proxies)} total proxies")

    if errors:
        logger.warning(f"Some proxy sources failed: {', '.join(errors)}")

    return unique_proxies

def refresh_cache_background():
    """
    Background task to refresh the proxy cache.
    """
    logger.info("Starting background cache refresh")

    try:
        proxies = fetch_combined_proxies()
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
        proxies = fetch_combined_proxies()
        update_cache(proxies)

        return {
            "success": True,
            "message": "Cache refreshed successfully with combined sources",
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