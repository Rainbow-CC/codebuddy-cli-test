# -*- coding: utf-8 -*-
import requests
import json
import time
import sys

# Reconfigure stdout to UTF-8 to prevent UnicodeEncodeError on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def test_streaming():
    url = "http://127.0.0.1:5000/api/cards/industry_overview/analyze/stream"
    headers = {"Content-Type": "application/json"}
    
    # 1. Test real-time streaming generation (force refresh cache)
    data = {"force_refresh": True}
    print("[TEST] Testing streaming response generation (force_refresh=True)...")
    start_time = time.time()
    response = requests.post(url, headers=headers, json=data, stream=True)
    
    full_text = []
    has_chunks = False
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("data: "):
                has_chunks = True
                payload = json.loads(decoded_line[6:])
                if 'error' in payload:
                    print(f"\n[ERROR] Streaming generation failed: {payload['error']}")
                    break
                content = payload.get('content', '')
                full_text.append(content)
                print(content, end="", flush=True)
    print("\n")
    duration = time.time() - start_time
    print(f"[INFO] Streaming generation completed in {duration:.2f}s")
    assert has_chunks, "Error: No streaming data chunks received"
    
    # Wait a brief moment to ensure SQLite database write transaction commits successfully
    time.sleep(1)
    
    # 2. Test SQLite database cache hit
    print("[TEST] Testing SQLite database cache hit (force_refresh=False)...")
    start_time = time.time()
    response_cached = requests.post(url, headers=headers, json={}, stream=True)
    
    cached_text = []
    is_cached = False
    for line in response_cached.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("data: "):
                payload = json.loads(decoded_line[6:])
                is_cached = payload.get('cached', False)
                cached_text.append(payload.get('content', ''))
                
    duration_cached = time.time() - start_time
    print(f"[INFO] Cache read completed in {duration_cached:.4f}s")
    print(f"Cache hit state: {is_cached}")
    assert is_cached, "Error: Response should be served directly from SQLite database cache"
    assert "".join(cached_text) == "".join(full_text), "Error: Cache content does not match original generated content"
    print("[SUCCESS] SSE streaming response and SQLite database caching validation passed successfully.")

if __name__ == "__main__":
    test_streaming()
