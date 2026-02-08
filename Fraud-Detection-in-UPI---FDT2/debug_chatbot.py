"""Debug chatbot API response"""
import requests
import json

def test_chatbot():
    print("=" * 60)
    print("CHATBOT DEBUG TEST")
    print("=" * 60)
    
    # Test 1: Simple hello
    print("\n[Test 1: 'hello']")
    try:
        r = requests.post('http://localhost:8000/api/chatbot', 
                         json={'message': 'hello'}, timeout=10)
        print(f"  Status Code: {r.status_code}")
        print(f"  Content-Type: {r.headers.get('content-type')}")
        
        try:
            data = r.json()
            print(f"  JSON Keys: {list(data.keys()) if isinstance(data, dict) else 'NOT A DICT'}")
            if 'response' in data:
                print(f"  Response length: {len(data['response'])} chars")
                print(f"  First 200 chars: {data['response'][:200]}")
            elif 'error' in data:
                print(f"  ERROR: {data['error']}")
            else:
                print(f"  Full data: {data}")
        except Exception as e:
            print(f"  JSON parse error: {e}")
            print(f"  Raw text: {r.text[:500]}")
    except Exception as e:
        print(f"  REQUEST FAILED: {e}")

    # Test 2: Total transactions
    print("\n[Test 2: 'how many transactions']")
    try:
        r = requests.post('http://localhost:8000/api/chatbot', 
                         json={'message': 'how many transactions'}, timeout=10)
        print(f"  Status Code: {r.status_code}")
        data = r.json()
        if 'response' in data:
            print(f"  Response: {data['response'][:300]}")
        elif 'error' in data:
            print(f"  ERROR: {data['error']}")
    except Exception as e:
        print(f"  REQUEST FAILED: {e}")

    # Test 3: What if message format is wrong
    print("\n[Test 3: Empty message]")
    try:
        r = requests.post('http://localhost:8000/api/chatbot', 
                         json={'message': ''}, timeout=10)
        print(f"  Status Code: {r.status_code}")
        print(f"  Response: {r.json()}")
    except Exception as e:
        print(f"  REQUEST FAILED: {e}")

    # Test 4: Check what browser might be seeing
    print("\n[Test 4: Simulate browser request]")
    try:
        r = requests.post('http://localhost:8000/api/chatbot',
                         headers={'Content-Type': 'application/json'},
                         json={
                             'message': 'hello',
                             'time_range': '24h',
                             'history': []
                         }, timeout=10)
        print(f"  Status Code: {r.status_code}")
        data = r.json()
        print(f"  Has 'response': {'response' in data}")
        print(f"  Has 'error': {'error' in data}")
        if 'response' in data:
            print(f"  Response OK: {len(data['response'])} chars")
        if 'error' in data:
            print(f"  Error: {data['error']}")
    except Exception as e:
        print(f"  REQUEST FAILED: {e}")

if __name__ == "__main__":
    test_chatbot()
