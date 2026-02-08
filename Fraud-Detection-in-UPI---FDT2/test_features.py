"""Test chatbot new features"""
import requests

def test():
    print("=" * 60)
    print("TESTING CHATBOT FEATURES")
    print("=" * 60)
    
    tests = [
        ("Transaction ID", "ff661dee-c323-4a7e-b82d-6af62c8c34d0"),
        ("Last 5 tx", "analyse last 5 transactions"),
        ("Blocked", "show blocked transactions"),
        ("Fraud rate", "what is the fraud rate"),
    ]
    
    for name, msg in tests:
        print(f"\n[{name}] Query: {msg[:40]}...")
        try:
            r = requests.post("http://localhost:8000/api/chatbot", json={"message": msg}, timeout=10)
            data = r.json()
            resp = data.get("response", "NO RESPONSE")
            print(f"Response ({len(resp)} chars):")
            print(resp[:300])
            if len(resp) > 300:
                print("...")
        except Exception as e:
            print(f"ERROR: {e}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test()
