from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import json
import asyncio
import threading
from datetime import datetime

# Import proxy service
from proxy_service import (
    initialize_cache,
    start_background_task,
    get_cached_proxies,
    manual_refresh
)

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active WebSocket connections
active_connections = []

# Global variable to store background task timer
background_task_timer = None

# Initialize proxy cache on startup
@app.on_event("startup")
async def startup_event():
    """Initialize proxy cache and start background refresh task"""
    global background_task_timer

    # Initialize cache
    initialize_cache()

    # Start background refresh task (24-hour interval)
    background_task_timer = start_background_task()

# Configuration
TIMEOUT = 12
TEST_URL = "http://httpbin.org/ip"
MAX_WORKERS = 40

class ProxyRequest(BaseModel):
    text: str

class ProxyResult(BaseModel):
    proxy: str
    success: bool
    message: str
    latency: float
    exit_ip: str

def clean_and_extract_proxies(text: str) -> List[str]:
    """
    Extract proxy addresses from text
    Handles: "ip:port", commas, quotes, line breaks, etc.
    """
    # Find all patterns that look like IP:PORT (with or without quotes)
    pattern = r'(?:"|\')?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})(?:"|\')?'
    matches = re.findall(pattern, text)

    proxies = [p.strip() for p in matches if p.strip()]
    return proxies

def test_proxy(proxy: str) -> Dict[str, Any]:
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}$', proxy):
        return {
            "proxy": proxy,
            "success": False,
            "message": "Invalid format",
            "latency": 0.0,
            "exit_ip": ""
        }

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
            headers={"User-Agent": "Mozilla/5.0 AzureCheck"}
        )
        elapsed = round(time.time() - start, 2)

        if r.status_code == 200:
            try:
                ip = r.json().get("origin", "unknown")
            except:
                ip = r.text.strip()[:15]
            return {
                "proxy": proxy,
                "success": True,
                "message": "OK",
                "latency": elapsed,
                "exit_ip": ip
            }
        else:
            return {
                "proxy": proxy,
                "success": False,
                "message": f"Bad status: {r.status_code}",
                "latency": elapsed,
                "exit_ip": ""
            }

    except Exception as e:
        err_name = type(e).__name__
        return {
            "proxy": proxy,
            "success": False,
            "message": f"FAIL - {err_name}",
            "latency": 0.0,
            "exit_ip": ""
        }

@app.post("/api/verify")
async def verify_proxies(request: ProxyRequest):
    proxies = clean_and_extract_proxies(request.text)

    if not proxies:
        return {"error": "No valid proxies found in the input text"}

    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_proxy = {
            executor.submit(test_proxy, proxy): proxy
            for proxy in proxies
        }

        for future in as_completed(future_to_proxy):
            result = future.result()
            results.append(result)

    return {"results": results}

@app.websocket("/ws/verify")
async def websocket_verify(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            request_data = json.loads(data)
            text = request_data.get("text", "")

            proxies = clean_and_extract_proxies(text)

            if not proxies:
                await websocket.send_text(json.dumps({"error": "No valid proxies found"}))
                continue

            total_proxies = len(proxies)
            processed_count = 0

            # Send initial info
            await websocket.send_text(json.dumps({
                "type": "start",
                "total": total_proxies
            }))

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_proxy = {
                    executor.submit(test_proxy, proxy): proxy
                    for proxy in proxies
                }

                for future in as_completed(future_to_proxy):
                    result = future.result()
                    processed_count += 1
                    progress = round((processed_count / total_proxies) * 100, 2)

                    # Send individual result
                    await websocket.send_text(json.dumps({
                        "type": "result",
                        "result": result,
                        "progress": progress
                    }))

            # Send completion message
            await websocket.send_text(json.dumps({
                "type": "complete",
                "message": "All proxies tested"
            }))

    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        active_connections.remove(websocket)
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))

@app.get("/")
async def root():
    return {"message": "AzureCheck Proxy Verification API"}

@app.get("/api/fetch-proxies")
async def fetch_proxies():
    """
    Manual trigger endpoint to fetch fresh proxies from ProxyScrape API.

    Returns:
        Dict[str, Any]: Result of the fetch operation
    """
    try:
        result = manual_refresh()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch proxies: {str(e)}"
        )

@app.get("/api/get-cached-proxies")
async def get_cached_proxies_endpoint():
    """
    Retrieve pre-verified cached proxies from the in-memory cache.

    Returns:
        Dict[str, Any]: Pre-verified cached proxies and metadata
    """
    try:
        proxies = get_cached_proxies()
        return {
            "success": True,
            "proxies": proxies,
            "count": len(proxies),
            "timestamp": datetime.utcnow().isoformat(),
            "pre_verified": True,
            "message": "All proxies have been pre-tested and verified to be working"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve cached proxies: {str(e)}"
        )

@app.get("/api/get-preverified-proxies")
async def get_preverified_proxies_endpoint():
    """
    Retrieve pre-verified proxies with detailed information about the verification process.

    Returns:
        Dict[str, Any]: Pre-verified proxies with verification metadata
    """
    try:
        proxies = get_cached_proxies()
        return {
            "success": True,
            "proxies": proxies,
            "count": len(proxies),
            "timestamp": datetime.utcnow().isoformat(),
            "pre_verified": True,
            "verification_info": {
                "method": "backend_pre_checking",
                "test_url": "http://httpbin.org/ip",
                "timeout_seconds": 12,
                "max_concurrent_tests": 40,
                "description": "All proxies have been tested on the backend server and verified to be working before being returned to the client"
            },
            "message": "These proxies have been pre-tested on the server to ensure they are working, preventing browser freezing"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve pre-verified proxies: {str(e)}"
        )