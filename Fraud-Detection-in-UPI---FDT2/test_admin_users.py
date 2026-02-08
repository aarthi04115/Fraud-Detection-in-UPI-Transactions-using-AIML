"""
Test script to verify all 4 admin users can authenticate successfully
"""
import requests

BASE_URL = "http://localhost:8000"

ADMIN_USERS = [
    {"username": "admin", "password": "StrongAdmin123!", "role": "Super Admin"},
    {"username": "admin2", "password": "SecurePass2!", "role": "Admin"},
    {"username": "admin3", "password": "SecurePass3!", "role": "Admin"},
    {"username": "admin4", "password": "SecurePass4!", "role": "Admin"}
]

def test_admin_login(username, password, role):
    """Test admin login for a specific user"""
    try:
        # Create a session to handle cookies
        session = requests.Session()
        
        # Attempt login
        response = session.post(
            f"{BASE_URL}/admin/login",
            data={
                "username": username,
                "password": password
            },
            allow_redirects=False
        )
        
        # Check if login was successful (should redirect to /admin)
        if response.status_code == 303 and response.headers.get('location') == '/admin':
            print(f"✅ SUCCESS: {username:12} ({role:12}) - Authentication successful")
            return True
        else:
            print(f"❌ FAILED:  {username:12} ({role:12}) - Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR:   {username:12} ({role:12}) - {str(e)}")
        return False

def main():
    print("=" * 70)
    print("Testing Multi-Admin User Authentication")
    print("=" * 70)
    print()
    
    results = []
    for admin in ADMIN_USERS:
        result = test_admin_login(admin["username"], admin["password"], admin["role"])
        results.append(result)
    
    print()
    print("=" * 70)
    print(f"Results: {sum(results)}/{len(results)} admin users authenticated successfully")
    print("=" * 70)
    
    if all(results):
        print("\n✅ All admin users are working correctly!")
    else:
        print("\n⚠️  Some admin users failed authentication. Check the configuration.")

if __name__ == "__main__":
    main()
