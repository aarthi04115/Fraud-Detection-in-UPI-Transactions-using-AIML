"""Create test users for the web app"""
import requests
import time

def create_test_users():
    """Register test users via the API"""
    base_url = "http://localhost:8001"
    
    # Wait for server to be ready
    print("Waiting for backend server to be ready...")
    for i in range(10):
        try:
            requests.get(f"{base_url}/api/health", timeout=2)
            print("✓ Server is ready")
            break
        except:
            if i < 9:
                print(f"  Retry {i+1}/9...")
                time.sleep(2)
            else:
                print("✗ Server not responding")
                return
    
    test_users = [
        {
            "name": "Test User",
            "phone": "9876543210",
            "password": "TestPass123",
            "email": "test@example.com"
        },
        {
            "name": "John Doe",
            "phone": "9876543211",
            "password": "JohnPass123",
            "email": "john@example.com"
        },
        {
            "name": "Jane Smith",
            "phone": "9876543212",
            "password": "JanePass123",
            "email": "jane@example.com"
        }
    ]
    
    print("\n" + "="*60)
    print("CREATING TEST USERS")
    print("="*60)
    
    for user in test_users:
        try:
            print(f"\nRegistering: {user['name']} ({user['phone']})")
            response = requests.post(
                f"{base_url}/api/register",
                json=user,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Success - Token: {data.get('token', 'N/A')[:20]}...")
            elif response.status_code == 400:
                print(f"⚠ {response.json().get('detail', 'Bad request')}")
            else:
                print(f"✗ Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"✗ Failed: {e}")
    
    print("\n" + "="*60)
    print("TEST USER CREDENTIALS")
    print("="*60)
    for user in test_users:
        print(f"\nPhone: {user['phone']}")
        print(f"Password: {user['password']}")
    print("\n" + "="*60)

if __name__ == "__main__":
    create_test_users()
