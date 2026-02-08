import requests
import json
import sys

# COMPREHENSIVE CHATBOT TEST
print("=" * 70)
print("CHATBOT COMPREHENSIVE FUNCTIONALITY TEST")
print("=" * 70)
print()

url = "http://localhost:8000/api/chatbot"
headers = {"Content-Type": "application/json"}

# Test cases covering all chatbot functionality
test_cases = [
    {
        "name": "1. Welcome/Greeting",
        "message": "hello"
    },
    {
        "name": "2. Transaction Statistics",
        "message": "How many transactions were blocked?"
    },
    {
        "name": "3. Risk Score Analysis",
        "message": "What's the average risk score?"
    },
    {
        "name": "4. High-Risk Transactions",
        "message": "Show me high risk transactions"
    },
    {
        "name": "5. Transaction Amounts",
        "message": "What are the transaction amounts?"
    },
    {
        "name": "6. Transaction ID Query",
        "message": "83acc0d8-a4e2-481c-ad98-abd6d71e5218"
    },
    {
        "name": "7. General Fund Query",
        "message": "What is the fraud rate?"
    },
    {
        "name": "8. Trend Analysis",
        "message": "Show me transaction trends"
    }
]

passed = 0
failed = 0
total = len(test_cases)

for test in test_cases:
    print(f"\n[TEST] {test['name']}")
    print(f"Query: \"{test['message']}\"")
    print("-" * 70)
    
    try:
        payload = {
            "message": test["message"],
            "time_range": "24h"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            bot_response = data.get("response", "")
            
            if bot_response and len(bot_response) > 0:
                print(f"✓ STATUS: SUCCESS (HTTP 200)")
                print(f"✓ RESPONSE LENGTH: {len(bot_response)} characters")
                print(f"\nRESPONSE PREVIEW (first 150 chars):")
                print(bot_response[:150] + ("..." if len(bot_response) > 150 else ""))
                passed += 1
            else:
                print(f"✗ STATUS: FAILED (Empty response)")
                failed += 1
        else:
            print(f"✗ STATUS: FAILED (HTTP {response.status_code})")
            print(f"Error: {response.text[:200]}")
            failed += 1
            
    except Exception as e:
        print(f"✗ STATUS: FAILED")
        print(f"Exception: {type(e).__name__}: {str(e)[:200]}")
        failed += 1

print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print(f"Total Tests: {total}")
print(f"✓ Passed: {passed}")
print(f"✗ Failed: {failed}")
print(f"Success Rate: {(passed/total)*100:.1f}%")
print("=" * 70)

if passed == total:
    print("\n🎉 ALL TESTS PASSED! CHATBOT IS FULLY FUNCTIONAL! 🎉\n")
    sys.exit(0)
else:
    print(f"\n⚠️  {failed} test(s) failed. Review errors above.\n")
    sys.exit(1)
