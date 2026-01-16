import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

# ===================== CONFIG =====================
TIMEOUT = 12
TEST_URL = "http://httpbin.org/ip"
MAX_WORKERS = 40
SHOW_ERRORS = False       # change to True to see detailed error messages

GOOD_PROXIES = []
BAD_PROXIES = []
# ==================================================

def clean_and_extract_proxies(text: str):
    """
    Extract proxy addresses from Python list-like string
    Handles: "ip:port", commas, quotes, line breaks, etc.
    """
    # Remove everything outside the list brackets
    text = re.sub(r'^.*?[\[\(]', '[', text, flags=re.DOTALL)
    text = re.sub(r'[\]\)].*?$', ']', text, flags=re.DOTALL)

    # Find all patterns that look like IP:PORT (with or without quotes)
    pattern = r'(?:"|\')?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})(?:"|\')?'
    matches = re.findall(pattern, text)

    proxies = [p.strip() for p in matches if p.strip()]
    return proxies


def test_proxy(proxy: str) -> tuple:
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}$', proxy):
        return proxy, False, "Invalid format"

    proxies_dict = {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}",
    }

    try:
        start = time.time()
        r = requests.get(
            TEST_URL,
            proxies=proxies_dict,
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 Proxy-Checker"}
        )
        elapsed = round(time.time() - start, 2)

        if r.status_code == 200:
            try:
                ip = r.json().get("origin", "unknown")
            except:
                ip = r.text.strip()[:15]
            return proxy, True, f"OK  {elapsed}s  →  {ip}"
        else:
            return proxy, False, f"Bad status: {r.status_code}"

    except Exception as e:
        err_name = type(e).__name__
        if SHOW_ERRORS:
            return proxy, False, f"FAIL - {err_name}: {str(e)}"
        else:
            return proxy, False, f"FAIL - {err_name}"


def load_proxies_from_file(filename="proxy.txt"):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        proxies = clean_and_extract_proxies(content)
        
        if not proxies:
            print("Warning: No proxies found in the file!")
        else:
            print(f"Found {len(proxies)} proxies")
            
        return proxies
        
    except FileNotFoundError:
        print(f"File '{filename}' not found!")
        return []
    except Exception as e:
        print(f"Error reading file: {e}")
        return []


def main():
    proxies = load_proxies_from_file("proxy.txt")
    
    if not proxies:
        print("Nothing to test. Exiting.")
        return

    print(f"\nTesting {len(proxies)} proxies...")
    print("-" * 65)

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_proxy = {
            executor.submit(test_proxy, proxy): proxy 
            for proxy in proxies
        }

        for future in as_completed(future_to_proxy):
            proxy, success, msg = future.result()
            
            color = "\033[92m" if success else "\033[91m"
            status = "GOOD" if success else "BAD "
            
            print(f"{color}{status}\033[0m  {proxy:22} → {msg}")

            if success:
                GOOD_PROXIES.append(proxy)
            else:
                BAD_PROXIES.append(proxy)

    total_time = round(time.time() - start_time, 2)
    print("-" * 65)
    print(f"\nFinished in {total_time} seconds")
    print(f"Good: {len(GOOD_PROXIES):3d}  |  Bad: {len(BAD_PROXIES):3d}")

    if GOOD_PROXIES:
        print("\nWorking proxies:")
        for p in GOOD_PROXIES:
            print(p)


if __name__ == "__main__":
    main()
