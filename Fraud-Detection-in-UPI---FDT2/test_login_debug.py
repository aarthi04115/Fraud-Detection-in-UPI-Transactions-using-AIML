"""
Debug script to test login functionality
"""
import psycopg2
import os
from dotenv import load_dotenv
from argon2 import PasswordHasher
import bcrypt

load_dotenv()

DB_URL = os.getenv('DB_URL', 'postgresql://fdt:fdtpass@localhost:5432/fdt_db')
pwd_hasher = PasswordHasher()

def verify_password(password_hash: str, password: str) -> bool:
    """
    Verify password against hash, supporting both bcrypt and Argon2
    """
    try:
        # Detect hash type by prefix
        if password_hash.startswith('$2b$') or password_hash.startswith('$2a$') or password_hash.startswith('$2y$'):
            # bcrypt hash
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        elif password_hash.startswith('$argon2'):
            # Argon2 hash
            pwd_hasher.verify(password_hash, password)
            return True
        else:
            print(f"[WARNING] Unknown password hash format: {password_hash[:20]}...")
            return False
    except Exception as e:
        print(f"[WARNING] Password verification failed: {e}")
        return False

def test_user_login(phone, password):
    """Test login for a specific user"""
    print(f"\n{'='*60}")
    print(f"Testing login for: {phone}")
    print(f"{'='*60}")
    
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Get user
    cur.execute(
        "SELECT user_id, name, phone, email, password_hash, is_active FROM users WHERE phone = %s",
        (phone,)
    )
    user = cur.fetchone()
    
    if not user:
        print(f"❌ User not found with phone: {phone}")
        conn.close()
        return False
    
    user_id, name, phone_val, email, password_hash, is_active = user
    
    print(f"✓ User found:")
    print(f"  - User ID: {user_id}")
    print(f"  - Name: {name}")
    print(f"  - Phone: {phone_val}")
    print(f"  - Email: {email}")
    print(f"  - Is Active: {is_active}")
    print(f"  - Password hash: {password_hash[:50]}...")
    print(f"  - Hash prefix: {password_hash[:10]}")
    
    if not is_active:
        print(f"❌ User account is not active")
        conn.close()
        return False
    
    # Test password verification
    print(f"\n📝 Testing password: '{password}'")
    if verify_password(password_hash, password):
        print(f"✅ Password verification SUCCESSFUL!")
        conn.close()
        return True
    else:
        print(f"❌ Password verification FAILED!")
        conn.close()
        return False

def list_all_users():
    """List all users in database"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    cur.execute("SELECT user_id, name, phone, email, is_active FROM users LIMIT 10")
    users = cur.fetchall()
    
    print(f"\n{'='*60}")
    print(f"Users in Database:")
    print(f"{'='*60}")
    for user in users:
        print(f"  - {user[2]} | {user[1]} | Active: {user[4]}")
    
    conn.close()

if __name__ == "__main__":
    # List all users
    list_all_users()
    
    # Test known users (common test credentials)
    test_phones = [
        ("+919876543211", "password123"),  # Priya Sharma
        ("+919876543212", "password123"),  # Amit Patel
        ("9876543211", "password123"),     # Without +91
    ]
    
    for phone, password in test_phones:
        test_user_login(phone, password)
