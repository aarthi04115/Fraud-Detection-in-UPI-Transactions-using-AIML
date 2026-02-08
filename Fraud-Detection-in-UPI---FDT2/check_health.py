"""
API Health Check - Test all endpoints and services
"""
import requests
import psycopg2
import os
from datetime import datetime

def check_service(name, url, timeout=5):
    """Check if a service is responding"""
    try:
        response = requests.get(url, timeout=timeout)
        status = "✅ UP" if response.status_code in [200, 404] else f"⚠️  {response.status_code}"
        return status, response.elapsed.total_seconds()
    except requests.exceptions.ConnectionError:
        return "❌ DOWN", 0
    except requests.exceptions.Timeout:
        return "⏱️  TIMEOUT", timeout
    except Exception as e:
        return f"❌ ERROR: {str(e)[:30]}", 0

def check_database():
    """Check PostgreSQL connection"""
    try:
        db_url = os.getenv("DB_URL", "postgresql://fdt:fdtpass@localhost:5432/fdt_db")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users;")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return f"✅ UP ({count} users)", 0
    except Exception as e:
        return f"❌ DOWN: {str(e)[:40]}", 0

def check_redis():
    """Check Redis connection"""
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
        r.ping()
        return "✅ UP", 0
    except Exception as e:
        return f"⚠️  UNAVAILABLE", 0

print("="*70)
print(f"API HEALTH CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*70)

# Check services
services = [
    ("Backend User API", "http://localhost:8001/"),
    ("Admin Dashboard API", "http://localhost:8000/"),
    ("Frontend React App", "http://localhost:3000/"),
]

print("\n📡 Service Status:")
print(f"{'Service':<25} {'Status':<20} {'Response Time':<15}")
print("-"*70)

for name, url in services:
    status, time = check_service(name, url)
    time_str = f"{time*1000:.0f}ms" if time > 0 else "-"
    print(f"{name:<25} {status:<20} {time_str:<15}")

# Check database
print(f"\n💾 Database:")
status, _ = check_database()
print(f"  PostgreSQL: {status}")

# Check Redis
print(f"\n🗄️  Cache:")
status, _ = check_redis()
print(f"  Redis: {status}")

# Test key endpoints
print(f"\n🔍 API Endpoints:")
print(f"{'Endpoint':<35} {'Status':<20}")
print("-"*70)

endpoints = [
    ("POST /api/register", "http://localhost:8001/api/register"),
    ("POST /api/login", "http://localhost:8001/api/login"),
    ("GET /api/user/dashboard", "http://localhost:8001/api/user/dashboard"),
    ("POST /api/transactions", "http://localhost:8001/api/transactions"),
    ("GET /admin (check)", "http://localhost:8000/admin"),
]

for name, url in endpoints:
    # Just check if endpoint exists (will fail auth but should respond)
    status, time = check_service(name, url, timeout=3)
    print(f"{name:<35} {status:<20}")

print("\n" + "="*70)
print("Health check complete!")
print("="*70)
