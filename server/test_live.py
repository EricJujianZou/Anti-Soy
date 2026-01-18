import httpx
import sys
import json

def test_live(username="Skullheadx"):
    # Ensure this matches your running uvicorn port
    url = f"http://127.0.0.1:8000/analyze/{username}"
    print(f"🚀 Sending Live POST request to {url}...")
    print("This will fetch REAL data from GitHub (make sure .env has your token)...")
    
    try:
        # increased timeout because fetching from GitHub can take a few seconds
        response = httpx.post(url, timeout=30.0) 
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Success! Response Body:")
            print(json.dumps(response.json(), indent=2))
        else:
            print("❌ Error Response:")
            print(response.text)
            
    except httpx.RequestError as exc:
        print(f"⚠️ Connection error: {exc}")
        print("Is the server running? (try: uvicorn server.main:app --reload)")

if __name__ == "__main__":
    # Allow passing username via command line: python test_live.py torvalds
    target_user = sys.argv[1] if len(sys.argv) > 1 else "EricJujianZou"
    test_live(target_user)
