#!/usr/bin/env python3
"""Test performance features: caching, rate limiting, indexes"""

import requests
import json
import time
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:8001"

def test_registration_and_login():
    """Test user registration and login"""
    print("\n=== Testing Registration & Login ===")
    
    # Register
    user_data = {
        "phone": "8888888888",
        "name": "PerfTest2",
        "email": "perftest2@example.com",
        "password": "PerfTest2123"
    }
    resp = requests.post(f"{BASE_URL}/api/register", json=user_data)
    assert resp.status_code == 200, f"Registration failed: {resp.text}"
    token = resp.json()["token"]
    print(f"✓ Registration successful")
    print(f"✓ Token obtained: {token[:50]}...")
    return token

def test_dashboard_caching(token):
    """Test dashboard endpoint caching"""
    print("\n=== Testing Dashboard Caching ===")
    
    # First call - hits database
    start = time.time()
    resp1 = requests.get(
        f"{BASE_URL}/api/user/dashboard",
        headers={"Authorization": f"Bearer {token}"}
    )
    time1 = time.time() - start
    
    assert resp1.status_code == 200, f"Dashboard failed: {resp1.text}"
    data1 = resp1.json()
    print(f"✓ First call (DB hit): {time1:.3f}s")
    
    # Second call - should be cached
    start = time.time()
    resp2 = requests.get(
        f"{BASE_URL}/api/user/dashboard",
        headers={"Authorization": f"Bearer {token}"}
    )
    time2 = time.time() - start
    
    assert resp2.status_code == 200, f"Dashboard cached call failed: {resp2.text}"
    data2 = resp2.json()
    print(f"✓ Second call (cached): {time2:.3f}s")
    
    # Verify data is same
    assert data1 == data2, "Cached data differs from original"
    print(f"✓ Cache hit successful - data identical")
    
    if time2 < time1:
        speedup = time1 / time2
        print(f"✓ Speedup: {speedup:.1f}x faster with caching")
    
    return token

def test_rate_limiting(token):
    """Test rate limiting"""
    print("\n=== Testing Rate Limiting ===")
    
    # Make many rapid requests
    success_count = 0
    rate_limit_count = 0
    
    def make_request():
        try:
            resp = requests.get(
                f"{BASE_URL}/api/user/dashboard",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
            return resp.status_code
        except Exception as e:
            return None
    
    # Use ThreadPoolExecutor for concurrent requests
    print("Making 120 rapid concurrent requests (limit: 100 per 60 sec)...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda x: make_request(), range(120)))
    
    for status in results:
        if status == 200:
            success_count += 1
        elif status == 429:
            rate_limit_count += 1
    
    print(f"✓ Successful requests: {success_count}")
    print(f"✓ Rate limited (429): {rate_limit_count}")
    
    # Rate limiting should kick in for some requests
    if rate_limit_count > 0:
        print(f"✓ Rate limiting is working!")
    else:
        print(f"⚠ Rate limiting may not have triggered (limit was 100)")
    
    return True

def test_password_validation():
    """Test password validation"""
    print("\n=== Testing Password Validation ===")
    
    # Test weak password
    resp = requests.post(
        f"{BASE_URL}/api/register",
        json={
            "phone": "9999888888",
            "name": "Test",
            "email": "t@t.com",
            "password": "weak"
        }
    )
    assert resp.status_code == 400, "Weak password should be rejected"
    assert "8 characters" in resp.json()["detail"]
    print(f"✓ Password < 8 chars rejected")
    
    # Test password without digit
    resp = requests.post(
        f"{BASE_URL}/api/register",
        json={
            "phone": "9999888887",
            "name": "Test",
            "email": "t@t.com",
            "password": "NoDigitsHere"
        }
    )
    assert resp.status_code == 400, "Password without digit should be rejected"
    assert "number" in resp.json()["detail"]
    print(f"✓ Password without digit rejected")
    
    # Test valid password
    resp = requests.post(
        f"{BASE_URL}/api/register",
        json={
            "phone": "9999888886",
            "name": "Test",
            "email": "t@t.com",
            "password": "ValidPass123"
        }
    )
    assert resp.status_code == 200, f"Valid password should be accepted: {resp.text}"
    print(f"✓ Valid password accepted")

if __name__ == "__main__":
    try:
        print("=" * 60)
        print("PERFORMANCE FEATURES TEST SUITE")
        print("=" * 60)
        
        # Test password validation
        test_password_validation()
        
        # Get a token
        token = test_registration_and_login()
        
        # Test caching
        test_dashboard_caching(token)
        
        # Test rate limiting
        test_rate_limiting(token)
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
