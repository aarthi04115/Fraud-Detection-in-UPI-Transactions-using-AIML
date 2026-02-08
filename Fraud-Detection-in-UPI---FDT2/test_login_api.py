"""
Test login API endpoint directly
"""
import requests
import json

API_URL = "http://localhost:8001"

def test_login(phone, password):
    """Test login endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing Login API: {phone}")
    print(f"{'='*60}")
    
    payload = {
        "phone": phone,
        "password": password
    }
    
    try:
        response = requests.post(f"{API_URL}/api/login", json=payload, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                print(f"\n✅ LOGIN SUCCESSFUL!")
                print(f"   User: {data['user']['name']}")
                print(f"   Token: {data['token'][:50]}...")
                return True
        else:
            print(f"\n❌ LOGIN FAILED!")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    # Test known users
    test_cases = [
        ("+919876543211", "password123"),  # Priya Sharma
        ("+919876543212", "password123"),  # Amit Patel
        ("9876543211", "wrong_password"),  # Wrong password test
    ]
    
    for phone, password in test_cases:
        test_login(phone, password)
