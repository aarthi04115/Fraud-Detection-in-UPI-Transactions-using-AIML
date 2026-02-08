"""
FDT Backend Server - Fraud Detection in UPI Transactions
FastAPI server with user authentication, transaction processing, and ML-based fraud detection
"""

import os
import uuid
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal

from fastapi import FastAPI, Request, HTTPException, status, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from argon2 import PasswordHasher
import bcrypt

# Use argon2 for new passwords, but support bcrypt for legacy passwords
pwd_hasher = PasswordHasher()
import jwt
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

import psycopg2
import psycopg2.extras
import redis
import secrets
import base64
import webauthn
from webauthn import generate_registration_options, verify_registration_response
from webauthn import generate_authentication_options, verify_authentication_response
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
    AuthenticatorTransport
)

# Import WebSocket manager
try:
    from backend.ws_manager import ws_manager
except ImportError:
    from ws_manager import ws_manager

# Load environment variables
from dotenv import load_dotenv
import yaml
from pathlib import Path
load_dotenv()

# Configuration
DEFAULT_DB_URL = "postgresql://fdt:fdtpass@host.docker.internal:5432/fdt_db"
CFG_PATH = Path(__file__).resolve().parent.parent / "config" / "config.yaml"

def _load_cfg_db_url() -> str:
    """Load DB URL from config/config.yaml, handling UTF-8 BOM."""
    if not CFG_PATH.exists():
        return ""
    try:
        raw = CFG_PATH.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8-sig")
        cfg = yaml.safe_load(text) or {}
        return str(cfg.get("db_url", "")).strip()
    except Exception as e:
        print(f"[WARNING] Failed to load config.yaml DB URL: {e}")
        return ""

env_db_url = os.getenv("DB_URL")
cfg_db_url = _load_cfg_db_url()
DB_URL = (env_db_url or cfg_db_url or DEFAULT_DB_URL).strip()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fdt_jwt_secret_key_change_in_production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# =========================================================================
# REDIS CACHE INITIALIZATION
# =========================================================================
redis_client = None

def init_redis():
    """Initialize Redis connection for caching"""
    global redis_client
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        print(f"[OK] Redis cache connected: {REDIS_URL}")
        return True
    except Exception as e:
        print(f"[WARNING] Redis unavailable ({e}). Caching disabled, using direct DB queries.")
        redis_client = None
        return False

# Cache TTL constants (in seconds)
CACHE_TTL_USER = 300  # 5 minutes
CACHE_TTL_HISTORY = 180  # 3 minutes
CACHE_TTL_STATS = 60  # 1 minute

# =========================================================================
# RATE LIMITING (In-memory implementation)
# =========================================================================
from collections import defaultdict
from time import time

class RateLimiter:
    """Simple in-memory rate limiter"""
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)  # user_id -> list of request timestamps
    
    def is_allowed(self, user_id: str) -> bool:
        """Check if request is allowed for user"""
        now = time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        self.requests[user_id] = [t for t in self.requests[user_id] if t > window_start]
        
        # Check limit
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[user_id].append(now)
        return True

rate_limiter = RateLimiter(max_requests=100, window_seconds=60)  # 100 requests per minute

# Initialize scheduler 
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events (startup and shutdown)"""
    # Startup: Initialize database schema and Redis cache
    init_redis()
    
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # Step 1: Add daily_limit column if it doesn't exist
        cur.execute(
            """
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS daily_limit DECIMAL(15, 2) DEFAULT 10000.00
            """
        )
        
        # Step 2: Add Send Money feature columns to transactions table
        new_columns = [
            ("receiver_user_id", "VARCHAR(100) REFERENCES users(user_id)"),
            ("status_history", "TEXT[] DEFAULT '{}'"),
            ("amount_deducted_at", "TIMESTAMP"),
            ("amount_credited_at", "TIMESTAMP")
        ]
        
        for column_name, column_def in new_columns:
            try:
                cur.execute(f"ALTER TABLE transactions ADD COLUMN IF NOT EXISTS {column_name} {column_def}")
            except Exception as e:
                print(f"Column {column_name} already exists or error: {e}")
        
        # Step 3: Create transaction_ledger table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transaction_ledger (
                ledger_id SERIAL PRIMARY KEY,
                tx_id VARCHAR(100) REFERENCES transactions(tx_id),
                operation VARCHAR(50) NOT NULL,
                user_id VARCHAR(100) REFERENCES users(user_id),
                amount DECIMAL(15, 2) NOT NULL,
                operation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Step 4: Create user_daily_transactions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_daily_transactions (
                record_id SERIAL PRIMARY KEY,
                user_id VARCHAR(100) REFERENCES users(user_id),
                transaction_date DATE NOT NULL,
                total_amount DECIMAL(15, 2) DEFAULT 0.00,
                transaction_count INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, transaction_date)
            )
        """)
        
        # Step 5: Create indexes for performance optimization
        indexes = [
            ("idx_users_phone", "users", "phone"),
            ("idx_users_user_id", "users", "user_id"),
            ("idx_transactions_user_id", "transactions", "user_id"),
            ("idx_transactions_tx_id", "transactions", "tx_id"),
            ("idx_transactions_created_at", "transactions", "created_at"),
            ("idx_transactions_receiver_user_id", "transactions", "receiver_user_id"),
            ("idx_transaction_ledger_tx_id", "transaction_ledger", "tx_id"),
            ("idx_transaction_ledger_user_id", "transaction_ledger", "user_id"),
            ("idx_user_daily_transactions_user_date", "user_daily_transactions", "user_id, transaction_date")
        ]
        
        for index_name, table_name, columns in indexes:
            try:
                cur.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})")
            except Exception as e:
                print(f"Index {index_name} already exists or error: {e}")
        
        # Step 6: Add new test users
        new_users = [
            ('user_004', 'Abishek Kumar', '+919876543219', 'abishek@example.com', 
             '$2b$12$sC4pqNPR0pxSK8.6E4aire4FCKHbWK988MYFODhurkjGs35TPj8i.', 20000.00, 10000.00),
            ('user_005', 'Jerold Smith', '+919876543218', 'jerold@example.com', 
             '$2b$12$sC4pqNPR0pxSK8.6E4aire4FCKHbWK988MYFODhurkjGs35TPj8i.', 18000.00, 10000.00),
            ('user_006', 'Gowtham Kumar', '+919876543217', 'gowtham@example.com', 
             '$2b$12$sC4pqNPR0pxSK8.6E4aire4FCKHbWK988MYFODhurkjGs35TPj8i.', 22000.00, 10000.00)
        ]
        
        for user_data in new_users:
            try:
                cur.execute("""
                    INSERT INTO users (user_id, name, phone, email, password_hash, balance, daily_limit)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                """, user_data)
            except Exception as e:
                print(f"User {user_data[1]} already exists or error: {e}")
        
        conn.commit()
        print("[OK] Database schema initialized successfully (including Send Money feature)")
    except Exception as e:
        print(f"[WARNING] Could not ensure database schema: {e}")
    finally:
        try:
            conn.close()
        except:
            pass
    
    # Start the scheduler
    try:
        scheduler.add_job(
            auto_refund_delayed_transactions,
            trigger=IntervalTrigger(minutes=1),
            id="auto_refund_job",
            name="Auto-refund delayed transactions",
            replace_existing=True
        )
        scheduler.start()
        print("[OK] Auto-refund scheduler started")
    except Exception as e:
        print(f"[WARNING] Could not start scheduler: {e}")
    
    yield  # Application runs
    
    # Shutdown: Clean up resources
    try:
        scheduler.shutdown()
        print("[OK] Scheduler shut down")
    except Exception as e:
        print(f"[WARNING] Warning during scheduler shutdown: {e}")

# Initialize FastAPI app with lifespan
app = FastAPI(title="FDT API", version="1.0.0", lifespan=lifespan)

# CORS Configuration - Allow localhost + devtunnel URLs for mobile testing
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:3001,http://localhost:8000,http://192.168.21.59:3001,http://192.168.21.59:8001").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"(https?://.*\.devtunnels\.ms|http://192\.168\..*|http://localhost.*)",  # Allow devtunnels, local IPs, localhost
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["*"],
)

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to authenticated endpoints"""
    # Skip rate limiting for public endpoints
    if request.url.path in ["/docs", "/openapi.json", "/api/register", "/api/login"]:
        return await call_next(request)
    
    # Try to get user_id from token
    try:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("user_id")
            
            if user_id and not rate_limiter.is_allowed(user_id):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Max 100 requests per minute."}
                )
    except Exception:
        pass  # If token parsing fails, allow request (handled by auth later)
    
    return await call_next(request)

# Lifespan event handler defined above (async context manager)
# Old @app.on_event("startup") replaced with modern lifespan approach

async def auto_refund_delayed_transactions():
    """Auto-refund transactions that have been delayed for more than 5 minutes"""
    def _auto_refund():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Find transactions older than 5 minutes with DELAY status
            five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
            cur.execute(
                """
                SELECT tx_id, user_id, amount, recipient_vpa, created_at, amount_deducted_at
                FROM transactions 
                WHERE action = 'DELAY' 
                AND db_status = 'pending'
                AND created_at < %s
                """,
                (five_minutes_ago,)
            )
            
            expired_transactions = cur.fetchall()
            
            for tx in expired_transactions:
                # Refund sender only if funds were previously deducted
                if tx["amount_deducted_at"] is not None:
                    cur.execute(
                        "UPDATE users SET balance = balance + %s WHERE user_id = %s",
                        (float(tx["amount"]), tx["user_id"])
                    )
                    
                    # Log refund in transaction_ledger
                    cur.execute(
                        """
                        INSERT INTO transaction_ledger (tx_id, operation, user_id, amount, remarks)
                        VALUES (%s, 'REFUND', %s, %s, %s)
                        """,
                        (tx["tx_id"], tx["user_id"], float(tx["amount"]), "Auto-refund after 5 minute timeout")
                    )
                
                # Update transaction status
                cur.execute(
                    """
                    UPDATE transactions 
                    SET db_status = 'auto-refunded', 
                        action = 'BLOCK',
                        updated_at = NOW()
                    WHERE tx_id = %s
                    """,
                    (tx["tx_id"],)
                )
                
                # Emit WebSocket event for auto-refund
                try:
                    asyncio.create_task(
                        ws_manager.send_to_user(tx["user_id"], {
                            "type": "transaction_auto_refunded",
                            "tx_id": tx["tx_id"],
                            "amount": float(tx["amount"]),
                            "reason": "Auto-refund after 5 minute timeout"
                        })
                    )
                except Exception as e:
                    print(f"WebSocket emit error for auto-refund: {e}")
                
                print(f"Auto-refunded transaction {tx['tx_id']} (₹{tx['amount']})")
            
            if expired_transactions:
                conn.commit()
                print(f"[OK] Auto-refunded {len(expired_transactions)} delayed transactions")
            
        except Exception as e:
            print(f"Auto-refund error: {e}")
            if conn:
                conn.rollback()
        finally:
            conn.close()
    
    return await run_in_threadpool(_auto_refund)

# ============================================================================
# DATABASE HELPERS
# ============================================================================

def get_db_conn():
    """Get PostgreSQL database connection"""
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)

# =========================================================================
# REDIS CACHING HELPERS
# =========================================================================

def cache_get(key: str):
    """Get value from Redis cache"""
    try:
        if redis_client:
            return redis_client.get(key)
    except Exception as e:
        print(f"[WARNING] Cache get error: {e}")
    return None

def cache_set(key: str, value: str, ttl: int = 300):
    """Set value in Redis cache with TTL"""
    try:
        if redis_client:
            redis_client.setex(key, ttl, value)
    except Exception as e:
        print(f"[WARNING] Cache set error: {e}")

def cache_delete(key: str):
    """Delete value from Redis cache"""
    try:
        if redis_client:
            redis_client.delete(key)
    except Exception as e:
        print(f"[WARNING] Cache delete error: {e}")

def dict_to_json_serializable(data):
    """Convert dict with Decimal to JSON serializable format"""
    if isinstance(data, dict):
        return {k: dict_to_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [dict_to_json_serializable(item) for item in data]
    elif isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, datetime):
        return data.isoformat()
    return data

def verify_password(password_hash: str, password: str) -> bool:
    """
    Verify password against hash, supporting both bcrypt and Argon2
    
    Args:
        password_hash: The stored password hash
        password: The plain text password to verify
    
    Returns:
        True if password matches, False otherwise
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

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class UserRegister(BaseModel):
    name: str
    phone: str
    password: str
    email: Optional[str] = None

class UserLogin(BaseModel):
    phone: str
    password: str

class TransactionCreate(BaseModel):
    recipient_vpa: str
    amount: float
    remarks: Optional[str] = None
    device_id: Optional[str] = None

class UserDecision(BaseModel):
    tx_id: str
    decision: str  # 'confirm' or 'cancel'

class PushToken(BaseModel):
    fcm_token: str
    device_id: Optional[str] = None

class TransactionLimitUpdate(BaseModel):
    daily_limit: float

class UserSearchResult(BaseModel):
    user_id: str
    name: str
    phone: str
    upi_id: str

class TransactionConfirm(BaseModel):
    tx_id: str

class TransactionCancel(BaseModel):
    tx_id: str

# ============================================================================
# AUTHENTICATION HELPERS
# ============================================================================

def create_access_token(user_id: str) -> str:
    """Create JWT access token with proper UTC timestamps"""
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    # PyJWT automatically converts datetime to Unix timestamp
    payload = {
        "user_id": user_id,
        "iat": now,  # Issued at
        "exp": expiry  # Expiry
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    
    return token

def verify_token(token: str) -> Dict:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(request: Request) -> str:
    """Get current user from Authorization header"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = auth_header.split(" ")[1]
    payload = verify_token(token)
    return payload["user_id"]

# ============================================================================
# API ENDPOINTS - AUTHENTICATION
# ============================================================================

@app.post("/api/register")
async def register_user(user_data: UserRegister):
    """Register a new user"""
    def _register():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Check if phone already exists
            cur.execute("SELECT user_id FROM users WHERE phone = %s", (user_data.phone,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Phone number already registered")
            
            # Validate password complexity
            if len(user_data.password) < 8:
                raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
            if not any(c.isdigit() for c in user_data.password):
                raise HTTPException(status_code=400, detail="Password must contain at least one number")
            
            # Generate user ID
            user_id = f"user_{uuid.uuid4().hex[:8]}"
            
            # Hash password
            password_hash = pwd_hasher.hash(user_data.password)
            
            # Insert user
            cur.execute(
                """
                INSERT INTO users (user_id, name, phone, email, password_hash, balance, created_at)
                VALUES (%s, %s, %s, %s, %s, 10000.00, NOW())
                RETURNING user_id, name, phone, email, balance, created_at
                """,
                (user_id, user_data.name, user_data.phone, user_data.email, password_hash)
            )
            
            user = cur.fetchone()
            conn.commit()
            
            # Create access token
            token = create_access_token(user_id)
            
            return {
                "status": "success",
                "message": "User registered successfully",
                "user": dict_to_json_serializable(dict(user)),
                "token": token
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_register)

@app.post("/api/login")
async def login_user(credentials: UserLogin):
    """Login user and return JWT token"""
    def _login():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Get user by phone
            cur.execute(
                "SELECT user_id, name, phone, email, password_hash, balance FROM users WHERE phone = %s AND is_active = TRUE",
                (credentials.phone,)
            )
            user = cur.fetchone()
            
            if not user:
                raise HTTPException(status_code=401, detail="Invalid phone or password")
            
            # Verify password (supports both bcrypt and Argon2)
            if not verify_password(user["password_hash"], credentials.password):
                raise HTTPException(status_code=401, detail="Invalid phone or password")
            
            # Create token
            token = create_access_token(user["user_id"])
            
            # Remove password hash from response
            user_data = dict(user)
            del user_data["password_hash"]
            
            return {
                "status": "success",
                "message": "Login successful",
                "user": dict_to_json_serializable(user_data),
                "token": token
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_login)

# ============================================================================
# API ENDPOINTS - WEBAUTHN BIOMETRIC AUTHENTICATION
# ============================================================================

# Pydantic models for WebAuthn
class WebAuthnRegisterRequest(BaseModel):
    credential_id: str
    public_key: str
    device_name: Optional[str] = None
    aaguid: Optional[str] = None
    transports: Optional[List[str]] = None

class WebAuthnAuthenticateRequest(BaseModel):
    credential_id: str
    authenticator_data: str
    client_data_json: str
    signature: str
    user_handle: Optional[str] = None

class WebAuthnChallengeResponse(BaseModel):
    challenge: str
    user_id: Optional[str] = None

# Temporary storage for challenges (in production, use Redis with expiration)
webauthn_challenges = {}

@app.post("/api/auth/register-challenge")
async def create_register_challenge(user_id: str = Depends(get_current_user)):
    """Generate a challenge for WebAuthn credential registration"""
    challenge = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    webauthn_challenges[user_id] = {
        'challenge': challenge,
        'timestamp': datetime.utcnow(),
        'type': 'register'
    }
    
    return {
        "status": "success",
        "challenge": challenge,
        "user_id": user_id
    }

@app.post("/api/auth/register-credential")
async def register_credential(
    cred_data: WebAuthnRegisterRequest,
    user_id: str = Depends(get_current_user)
):
    """Register a new WebAuthn credential (fingerprint/biometric)"""
    def _register_credential():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Check if credential already exists
            cur.execute(
                "SELECT credential_id FROM user_credentials WHERE credential_id = %s",
                (cred_data.credential_id,)
            )
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Credential already registered")
            
            # Generate device name if not provided
            device_name = cred_data.device_name or f"Device {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
            
            # Insert credential
            cur.execute(
                """
                INSERT INTO user_credentials 
                (credential_id, user_id, public_key, device_name, transports, created_at, last_used)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING credential_id, device_name, created_at
                """,
                (
                    cred_data.credential_id,
                    user_id,
                    cred_data.public_key,
                    device_name,
                    cred_data.transports
                )
            )
            
            credential = cur.fetchone()
            
            # Enable fingerprint for user
            cur.execute(
                "UPDATE users SET fingerprint_enabled = TRUE WHERE user_id = %s",
                (user_id,)
            )
            
            conn.commit()
            
            # Clear cache
            cache_delete(f"dashboard:{user_id}")
            
            return {
                "status": "success",
                "message": "Biometric authentication enabled successfully",
                "credential": dict_to_json_serializable(dict(credential))
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_register_credential)

@app.post("/api/auth/login-challenge")
async def create_login_challenge(request: Request):
    """Generate a challenge for WebAuthn authentication"""
    data = await request.json()
    phone = data.get('phone')
    
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number required")
    
    def _get_user():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT user_id, fingerprint_enabled FROM users WHERE phone = %s AND is_active = TRUE",
                (phone,)
            )
            user = cur.fetchone()
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            if not user['fingerprint_enabled']:
                raise HTTPException(status_code=400, detail="Biometric authentication not enabled")
            
            # Get user's credentials
            cur.execute(
                "SELECT credential_id FROM user_credentials WHERE user_id = %s AND is_active = TRUE",
                (user['user_id'],)
            )
            credentials = cur.fetchall()
            
            if not credentials:
                raise HTTPException(status_code=400, detail="No biometric credentials found")
            
            # Generate challenge
            challenge = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
            webauthn_challenges[user['user_id']] = {
                'challenge': challenge,
                'timestamp': datetime.utcnow(),
                'type': 'authenticate'
            }
            
            return {
                "status": "success",
                "challenge": challenge,
                "user_id": user['user_id'],
                "allowCredentials": [{"id": c['credential_id'], "type": "public-key"} for c in credentials]
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_get_user)

@app.post("/api/auth/authenticate-credential")
async def authenticate_credential(auth_data: WebAuthnAuthenticateRequest):
    """Authenticate user using WebAuthn credential"""
    def _authenticate():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Get credential and user
            cur.execute(
                """
                SELECT uc.user_id, uc.public_key, uc.counter, u.name, u.phone, u.email, u.balance
                FROM user_credentials uc
                JOIN users u ON uc.user_id = u.user_id
                WHERE uc.credential_id = %s AND uc.is_active = TRUE AND u.is_active = TRUE
                """,
                (auth_data.credential_id,)
            )
            result = cur.fetchone()
            
            if not result:
                raise HTTPException(status_code=401, detail="Invalid credential")
            
            user_id = result['user_id']
            
            # In production, verify signature with public key here
            # For now, we'll trust the client-side verification
            
            # Update last used timestamp and counter
            cur.execute(
                "UPDATE user_credentials SET last_used = NOW(), counter = counter + 1 WHERE credential_id = %s",
                (auth_data.credential_id,)
            )
            conn.commit()
            
            # Create JWT token
            token = create_access_token(user_id)
            
            user_data = {
                'user_id': result['user_id'],
                'name': result['name'],
                'phone': result['phone'],
                'email': result['email'],
                'balance': float(result['balance'])
            }
            
            return {
                "status": "success",
                "message": "Biometric authentication successful",
                "user": user_data,
                "token": token
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_authenticate)

@app.get("/api/auth/credentials")
async def list_credentials(user_id: str = Depends(get_current_user)):
    """List all registered credentials for user"""
    def _list_credentials():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT credential_id, device_name, transports, created_at, last_used
                FROM user_credentials
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,)
            )
            credentials = cur.fetchall()
            
            return {
                "status": "success",
                "credentials": [dict_to_json_serializable(dict(c)) for c in credentials]
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_list_credentials)

@app.delete("/api/auth/credentials/{credential_id}")
async def revoke_credential(credential_id: str, user_id: str = Depends(get_current_user)):
    """Revoke a WebAuthn credential"""
    def _revoke():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Check ownership
            cur.execute(
                "SELECT user_id FROM user_credentials WHERE credential_id = %s",
                (credential_id,)
            )
            result = cur.fetchone()
            
            if not result or result['user_id'] != user_id:
                raise HTTPException(status_code=404, detail="Credential not found")
            
            # Soft delete (mark as inactive)
            cur.execute(
                "UPDATE user_credentials SET is_active = FALSE WHERE credential_id = %s",
                (credential_id,)
            )
            
            # Check if user has any active credentials left
            cur.execute(
                "SELECT COUNT(*) as count FROM user_credentials WHERE user_id = %s AND is_active = TRUE",
                (user_id,)
            )
            count = cur.fetchone()['count']
            
            # If no active credentials, disable fingerprint
            if count == 0:
                cur.execute(
                    "UPDATE users SET fingerprint_enabled = FALSE WHERE user_id = %s",
                    (user_id,)
                )
            
            conn.commit()
            
            # Clear cache
            cache_delete(f"dashboard:{user_id}")
            
            return {
                "status": "success",
                "message": "Credential revoked successfully"
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_revoke)

# ============================================================================
# API ENDPOINTS - USER DASHBOARD
# ============================================================================

@app.get("/api/user/dashboard")
async def get_user_dashboard(user_id: str = Depends(get_current_user)):
    """Get user dashboard data (cached for 3 minutes)"""
    # Try to get from cache first
    cache_key = f"dashboard:{user_id}"
    cached_data = cache_get(cache_key)
    if cached_data:
        return json.loads(cached_data)
    
    def _get_dashboard():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Get user info
            cur.execute(
                "SELECT user_id, name, phone, email, balance, created_at FROM users WHERE user_id = %s",
                (user_id,)
            )
            user = cur.fetchone()
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Add UPI ID to user data
            user_dict = dict(user)
            user_dict["upi_id"] = f"{user_dict['phone'].replace('+91', '').replace('+', '')}@upi"
            
            # Get recent transactions (last 5)
            cur.execute(
                """
                SELECT tx_id, amount, recipient_vpa, tx_type, action, risk_score, created_at, db_status, remarks
                FROM transactions
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (user_id,)
            )
            recent_transactions = cur.fetchall()
            
            # Get transaction stats
            cur.execute(
                """
                SELECT 
                    COUNT(*) as total_transactions,
                    COUNT(*) FILTER (WHERE action = 'ALLOW') as successful,
                    COUNT(*) FILTER (WHERE action = 'BLOCK') as blocked,
                    COUNT(*) FILTER (WHERE action = 'DELAY') as pending,
                    COALESCE(SUM(amount) FILTER (WHERE action = 'ALLOW'), 0) as total_spent
                FROM transactions
                WHERE user_id = %s
                """,
                (user_id,)
            )
            stats = cur.fetchone()
            
            result = {
                "status": "success",
                "user": dict_to_json_serializable(user_dict),
                "recent_transactions": dict_to_json_serializable([dict(t) for t in recent_transactions]),
                "stats": dict_to_json_serializable(dict(stats))
            }
            
            # Cache the result for 3 minutes
            cache_set(cache_key, json.dumps(result), CACHE_TTL_HISTORY)
            
            return result
        finally:
            conn.close()
    
    return await run_in_threadpool(_get_dashboard)

# ============================================================================
# API ENDPOINTS - TRANSACTIONS
# ============================================================================

@app.post("/api/transaction")
async def create_transaction(tx_data: TransactionCreate, user_id: str = Depends(get_current_user)):
    """Create new transaction and perform fraud detection"""
    def _create_transaction():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Get user balance and daily limit
            cur.execute("SELECT balance, daily_limit FROM users WHERE user_id = %s", (user_id,))
            user = cur.fetchone()
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            if float(user["balance"]) < tx_data.amount:
                raise HTTPException(status_code=400, detail="Insufficient balance")
            
            # Check daily limit and get cumulative amount for today
            today = datetime.now(timezone.utc).date()
            cur.execute(
                """
                SELECT COALESCE(total_amount, 0) as total_amount, COALESCE(transaction_count, 0) as transaction_count
                FROM user_daily_transactions 
                WHERE user_id = %s AND transaction_date = %s
                """,
                (user_id, today)
            )
            daily_stats = cur.fetchone()
            
            total_today = float(daily_stats["total_amount"]) if daily_stats else 0.0
            
            # Generate transaction ID
            tx_id = f"tx_{uuid.uuid4().hex[:12]}"
            device_id = tx_data.device_id or f"device_{uuid.uuid4().hex[:8]}"
            
            # Find receiver user if it's a registered user
            receiver_user_id = None
            if "@upi" in tx_data.recipient_vpa.lower():
                # Extract phone number from UPI ID
                phone_from_vpa = tx_data.recipient_vpa.replace("@upi", "").replace("+91", "").replace("+", "")
                cur.execute(
                    "SELECT user_id FROM users WHERE phone LIKE %s AND is_active = TRUE",
                    (f"%{phone_from_vpa}",)
                )
                receiver = cur.fetchone()
                if receiver:
                    receiver_user_id = receiver["user_id"]
            
            # Build transaction object for ML scoring
            transaction = {
                "tx_id": tx_id,
                "user_id": user_id,
                "device_id": device_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "amount": tx_data.amount,
                "recipient_vpa": tx_data.recipient_vpa,
                "tx_type": "P2M" if "@merchant" in tx_data.recipient_vpa else "P2P",
                "channel": "app",
                "remarks": tx_data.remarks
            }
            
            # Perform fraud detection using ML models
            risk_score = 0.0
            try:
                # Import scoring module from parent app directory
                import sys
                import os
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                sys.path.insert(0, project_root)
                from app import scoring
                
                risk_score = scoring.score_transaction(transaction)
                print(f"ML Risk Score for {tx_id}: {risk_score}")
            except Exception as e:
                print(f"Scoring error: {e}")
                # Fallback to simple rule-based scoring
                if tx_data.amount > 10000:
                    risk_score = 0.7
                elif tx_data.amount > 5000:
                    risk_score = 0.4
                else:
                    risk_score = 0.1
            
            # Determine action based on thresholds and daily limit
            delay_threshold = float(os.getenv("DELAY_THRESHOLD", "0.30"))
            block_threshold = float(os.getenv("BLOCK_THRESHOLD", "0.60"))
            
            # Force DELAY if exceeding daily limit
            total_with_this_tx = total_today + tx_data.amount
            exceeds_daily_limit = total_with_this_tx > float(user["daily_limit"])
            
            if risk_score >= block_threshold:
                action = "BLOCK"
                db_status = "blocked"
            elif risk_score >= delay_threshold or exceeds_daily_limit:
                action = "DELAY"
                db_status = "pending"
            else:
                action = "ALLOW"
                db_status = "success"
            
            amount_deducted_at = datetime.now(timezone.utc) if action == "ALLOW" else None

            # Insert transaction with new fields
            cur.execute(
                """
                INSERT INTO transactions 
                (tx_id, user_id, device_id, ts, amount, recipient_vpa, tx_type, channel, 
                 risk_score, action, db_status, remarks, receiver_user_id, amount_deducted_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING tx_id, user_id, amount, recipient_vpa, risk_score, action, db_status, created_at
                """,
                (tx_id, user_id, device_id, transaction["ts"], tx_data.amount, 
                 tx_data.recipient_vpa, transaction["tx_type"], "app", 
                 risk_score, action, db_status, tx_data.remarks, receiver_user_id, amount_deducted_at)
            )
            
            result = cur.fetchone()
            
            # Handle different actions
            if action == "ALLOW":
                # Debit sender immediately for allowed transactions
                cur.execute(
                    "UPDATE users SET balance = balance - %s WHERE user_id = %s",
                    (tx_data.amount, user_id)
                )
                
                # Log debit in transaction_ledger
                cur.execute(
                    """
                    INSERT INTO transaction_ledger (tx_id, operation, user_id, amount, remarks)
                    VALUES (%s, 'DEBIT', %s, %s, %s)
                    """,
                    (tx_id, user_id, float(tx_data.amount), 
                     f"Send to {tx_data.recipient_vpa}" + (" (forced DELAY: exceeds daily limit)" if exceeds_daily_limit else ""))
                )

                # Credit receiver immediately
                if receiver_user_id:
                    cur.execute(
                        "UPDATE users SET balance = balance + %s WHERE user_id = %s",
                        (tx_data.amount, receiver_user_id)
                    )
                    
                    # Log credit in transaction_ledger
                    cur.execute(
                        """
                        INSERT INTO transaction_ledger (tx_id, operation, user_id, amount, remarks)
                        VALUES (%s, 'CREDIT', %s, %s, %s)
                        """,
                        (tx_id, receiver_user_id, float(tx_data.amount), f"Credit from {user_id}")
                    )
                    
                    # Mark as credited
                    cur.execute(
                        "UPDATE transactions SET amount_credited_at = NOW() WHERE tx_id = %s",
                        (tx_id,)
                    )
            
            # Create fraud alert if risky
            if action in ["DELAY", "BLOCK"]:
                reason = []
                if tx_data.amount > 10000:
                    reason.append("High transaction amount")
                if exceeds_daily_limit:
                    reason.append("Exceeds daily transaction limit")
                if risk_score >= block_threshold:
                    reason.append("ML model detected suspicious pattern")
                
                cur.execute(
                    """
                    INSERT INTO fraud_alerts (tx_id, user_id, alert_type, risk_score, reason, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    """,
                    (tx_id, user_id, action, risk_score, "; ".join(reason))
                )
            
            # Update daily transactions tracking
            cur.execute(
                """
                INSERT INTO user_daily_transactions (user_id, transaction_date, total_amount, transaction_count)
                VALUES (%s, %s, %s, 1)
                ON CONFLICT (user_id, transaction_date) 
                DO UPDATE SET 
                    total_amount = user_daily_transactions.total_amount + %s,
                    transaction_count = user_daily_transactions.transaction_count + 1,
                    updated_at = NOW()
                """,
                (user_id, today, float(tx_data.amount), float(tx_data.amount))
            )
            
            conn.commit()

            # Clear dashboard cache for sender and receiver
            cache_delete(f"dashboard:{user_id}")
            if receiver_user_id:
                cache_delete(f"dashboard:{receiver_user_id}")
            
            # Schedule WebSocket events (async but handled via create_task)
            try:
                asyncio.create_task(
                    ws_manager.send_to_user(user_id, {
                        "type": "transaction_created",
                        "transaction": dict_to_json_serializable(dict(result)),
                        "requires_confirmation": action in ["DELAY", "BLOCK"],
                        "risk_level": "high" if risk_score >= block_threshold else "medium" if risk_score >= delay_threshold else "low"
                    })
                )
                
                if action == "ALLOW":
                    asyncio.create_task(
                        ws_manager.send_to_user(user_id, {
                            "type": "balance_updated",
                            "amount": -float(tx_data.amount),
                            "operation": "debit",
                            "new_balance": float(user["balance"]) - float(tx_data.amount)
                        })
                    )
                
                # If ALLOW and receiver is registered user, notify receiver
                if action == "ALLOW" and receiver_user_id:
                    asyncio.create_task(
                        ws_manager.send_to_user(receiver_user_id, {
                            "type": "transaction_received",
                            "transaction": dict_to_json_serializable(dict(result)),
                            "amount": float(tx_data.amount)
                        })
                    )
                    
            except Exception as e:
                print(f"WebSocket emit error: {e}")
            
            return {
                "status": "success",
                "transaction": dict_to_json_serializable(dict(result)),
                "requires_confirmation": action in ["DELAY", "BLOCK"],
                "risk_level": "high" if risk_score >= block_threshold else "medium" if risk_score >= delay_threshold else "low",
                "daily_limit_exceeded": exceeds_daily_limit,
                "receiver_user_id": receiver_user_id
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_create_transaction)

@app.post("/api/user-decision")
async def handle_user_decision(decision_data: UserDecision, user_id: str = Depends(get_current_user)):
    """Handle user's decision on flagged transaction"""
    def _handle_decision():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Get transaction
            cur.execute(
                """
                SELECT tx_id, user_id, amount, recipient_vpa, receiver_user_id, action, db_status, amount_deducted_at
                FROM transactions
                WHERE tx_id = %s AND user_id = %s
                """,
                (decision_data.tx_id, user_id)
            )
            transaction = cur.fetchone()
            
            if not transaction:
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            if transaction["db_status"] != "pending":
                raise HTTPException(status_code=400, detail="Transaction is not pending")

            # Update transaction based on decision
            if decision_data.decision == "confirm":
                if transaction["action"] != "DELAY":
                    raise HTTPException(status_code=400, detail="Only delayed transactions can be confirmed")

                new_action = "ALLOW"
                new_status = "success"

                # Debit sender only if not already deducted
                if transaction["amount_deducted_at"] is None:
                    cur.execute(
                        "SELECT balance FROM users WHERE user_id = %s",
                        (user_id,)
                    )
                    sender = cur.fetchone()
                    if not sender or float(sender["balance"]) < float(transaction["amount"]):
                        raise HTTPException(status_code=400, detail="Insufficient balance")

                    cur.execute(
                        "UPDATE users SET balance = balance - %s, updated_at = NOW() WHERE user_id = %s",
                        (float(transaction["amount"]), user_id)
                    )

                    cur.execute(
                        """
                        INSERT INTO transaction_ledger (tx_id, operation, user_id, amount, remarks)
                        VALUES (%s, 'DEBIT', %s, %s, %s)
                        """,
                        (decision_data.tx_id, user_id, float(transaction["amount"]), "Confirm delayed transaction")
                    )

                # Credit receiver if registered
                if transaction["receiver_user_id"]:
                    cur.execute(
                        """
                        UPDATE users 
                        SET balance = balance + %s, updated_at = NOW()
                        WHERE user_id = %s
                        """,
                        (float(transaction["amount"]), transaction["receiver_user_id"])
                    )

                    cur.execute(
                        """
                        INSERT INTO transaction_ledger (tx_id, operation, user_id, amount, remarks)
                        VALUES (%s, 'CREDIT', %s, %s, %s)
                        """,
                        (decision_data.tx_id, transaction["receiver_user_id"], 
                         float(transaction["amount"]), f"Credit from {user_id}")
                    )
            else:
                new_action = "BLOCK"
                new_status = "cancelled"

                # Refund sender if funds were previously deducted (legacy safety)
                if transaction["amount_deducted_at"] is not None:
                    cur.execute(
                        "UPDATE users SET balance = balance + %s, updated_at = NOW() WHERE user_id = %s",
                        (float(transaction["amount"]), user_id)
                    )

                    cur.execute(
                        """
                        INSERT INTO transaction_ledger (tx_id, operation, user_id, amount, remarks)
                        VALUES (%s, 'REFUND', %s, %s, %s)
                        """,
                        (decision_data.tx_id, user_id, float(transaction["amount"]), "Cancelled delayed transaction")
                    )
            
            # Update transaction
            cur.execute(
                """
                UPDATE transactions 
                SET action = %s, 
                    db_status = %s, 
                    amount_deducted_at = CASE WHEN %s THEN COALESCE(amount_deducted_at, NOW()) ELSE amount_deducted_at END,
                    amount_credited_at = CASE WHEN %s THEN NOW() ELSE amount_credited_at END,
                    updated_at = NOW()
                WHERE tx_id = %s
                RETURNING tx_id, action, db_status, updated_at
                """,
                (new_action, new_status, decision_data.decision == "confirm", decision_data.decision == "confirm", decision_data.tx_id)
            )
            
            result = cur.fetchone()
            
            # Update fraud alert if it exists
            cur.execute(
                """
                UPDATE fraud_alerts 
                SET user_decision = %s, resolved_at = NOW()
                WHERE tx_id = %s
                """,
                (decision_data.decision, decision_data.tx_id)
            )
            
            conn.commit()

            # Clear dashboard cache for sender and receiver
            cache_delete(f"dashboard:{user_id}")
            if transaction.get("receiver_user_id"):
                cache_delete(f"dashboard:{transaction['receiver_user_id']}")
            
            return {
                "status": "success",
                "message": f"Transaction {decision_data.decision}ed successfully",
                "transaction": dict_to_json_serializable(dict(result))
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_handle_decision)

@app.get("/api/user/transactions")
async def get_user_transactions(
    user_id: str = Depends(get_current_user),
    limit: int = 20,
    status_filter: Optional[str] = None
):
    """Get user transaction history with optional filtering"""
    def _get_transactions():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Optimized query - avoid LEFT JOIN, fetch fraud_alerts separately only when needed
            query = """
                SELECT tx_id, amount, recipient_vpa, tx_type, action, risk_score, 
                       db_status, remarks, created_at
                FROM transactions
                WHERE user_id = %s
            """
            params = [user_id]
            
            if status_filter:
                query += " AND action = %s"
                params.append(status_filter.upper())
            
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            
            cur.execute(query, params)
            transactions = cur.fetchall()
            
            # Fetch fraud_alerts for all transactions in a single query (faster than LEFT JOIN)
            if transactions:
                tx_ids = [tx['tx_id'] for tx in transactions]
                placeholders = ','.join(['%s'] * len(tx_ids))
                cur.execute(
                    f"SELECT tx_id, reason FROM fraud_alerts WHERE tx_id IN ({placeholders})",
                    tx_ids
                )
                fraud_alerts_map = {row['tx_id']: row['reason'] for row in cur.fetchall()}
            else:
                fraud_alerts_map = {}
            
            # Process transactions to add fraud reasons and risk_level
            processed_transactions = []
            delay_threshold = 0.35
            block_threshold = 0.70
            
            for tx in transactions:
                tx_dict = dict(tx)
                fraud_reason = fraud_alerts_map.get(tx_dict['tx_id'])
                if fraud_reason:
                    tx_dict["fraud_reasons"] = [reason.strip() for reason in fraud_reason.split(";")]
                else:
                    tx_dict["fraud_reasons"] = []
                
                # Add risk_level based on risk_score
                risk_score = float(tx_dict.get('risk_score', 0))
                if risk_score >= block_threshold:
                    tx_dict["risk_level"] = "BLOCKED"
                elif risk_score >= delay_threshold:
                    tx_dict["risk_level"] = "DELAYED"
                else:
                    tx_dict["risk_level"] = "APPROVED"
                
                processed_transactions.append(tx_dict)
            
            return {
                "status": "success",
                "transactions": dict_to_json_serializable(processed_transactions),
                "count": len(processed_transactions)
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_get_transactions)

# ============================================================================
# API ENDPOINTS - PUSH NOTIFICATIONS
# ============================================================================

@app.post("/api/push-token")
async def register_push_token(token_data: PushToken, user_id: str = Depends(get_current_user)):
    """Register FCM push notification token for user"""
    def _register_token():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Check if token already exists
            cur.execute(
                "SELECT token_id FROM push_tokens WHERE fcm_token = %s AND user_id = %s",
                (token_data.fcm_token, user_id)
            )
            
            if cur.fetchone():
                # Update existing token
                cur.execute(
                    """
                    UPDATE push_tokens 
                    SET last_used = NOW(), is_active = TRUE
                    WHERE fcm_token = %s AND user_id = %s
                    """,
                    (token_data.fcm_token, user_id)
                )
            else:
                # Insert new token
                cur.execute(
                    """
                    INSERT INTO push_tokens (user_id, fcm_token, device_id, created_at, last_used)
                    VALUES (%s, %s, %s, NOW(), NOW())
                    """,
                    (user_id, token_data.fcm_token, token_data.device_id)
                )
            
            conn.commit()
            
            return {
                "status": "success",
                "message": "Push token registered successfully"
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_register_token)

# ============================================================================
# API ENDPOINTS - TRANSACTION LIMIT
# ============================================================================

@app.get("/api/user/transaction-limit")
async def get_transaction_limit(user_id: str = Depends(get_current_user)):
    """Get user's daily transaction limit"""
    def _get_limit():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Get daily limit from users table
            cur.execute(
                "SELECT daily_limit FROM users WHERE user_id = %s",
                (user_id,)
            )
            result = cur.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            
            return {
                "status": "success",
                "daily_limit": float(result['daily_limit']) if result['daily_limit'] else 10000.00
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_get_limit)

@app.post("/api/user/transaction-limit")
async def set_transaction_limit(limit_data: TransactionLimitUpdate, user_id: str = Depends(get_current_user)):
    """Set user's daily transaction limit"""
    def _set_limit():
        daily_limit = limit_data.daily_limit
        
        if not daily_limit or daily_limit <= 0:
            raise HTTPException(status_code=400, detail="Daily limit must be greater than 0")
        
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Update daily limit
            cur.execute(
                """
                UPDATE users 
                SET daily_limit = %s, updated_at = NOW()
                WHERE user_id = %s
                RETURNING user_id, daily_limit
                """,
                (float(daily_limit), user_id)
            )
            
            result = cur.fetchone()
            conn.commit()
            
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            
            return {
                "status": "success",
                "message": f"Daily transaction limit updated to ₹{daily_limit}",
                "daily_limit": float(result['daily_limit'])
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_set_limit)

# ============================================================================
# API ENDPOINTS - SEND MONEY FEATURE
# ============================================================================

@app.get("/api/users/search")
async def search_users(phone: str = "", user_id: str = Depends(get_current_user)):
    """Search for registered users by phone number"""
    def _search_users():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Search users by phone number (partial match)
            cur.execute(
                """
                SELECT user_id, name, phone FROM users 
                WHERE phone LIKE %s AND is_active = TRUE AND user_id != %s
                ORDER BY phone
                LIMIT 10
                """,
                (f"%{phone}%", user_id)
            )
            
            users = cur.fetchall()
            
            # Format results with UPI ID
            results = []
            for user in users:
                results.append({
                    "user_id": user["user_id"],
                    "name": user["name"],
                    "phone": user["phone"],
                    "upi_id": f"{user['phone'].replace('+91', '').replace('+', '')}@upi"
                })
            
            return {
                "status": "success",
                "results": results,
                "count": len(results)
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_search_users)

@app.post("/api/transaction/confirm")
async def confirm_transaction(confirm_data: TransactionConfirm, user_id: str = Depends(get_current_user)):
    """Confirm a delayed transaction and credit the receiver"""
    def _confirm():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Get transaction details
            cur.execute(
                """
                SELECT tx_id, user_id, amount, recipient_vpa, receiver_user_id, action, db_status, amount_deducted_at
                FROM transactions 
                WHERE tx_id = %s AND user_id = %s AND db_status = 'pending'
                """,
                (confirm_data.tx_id, user_id)
            )
            
            transaction = cur.fetchone()
            if not transaction:
                raise HTTPException(status_code=404, detail="Transaction not found or not pending")
            
            if transaction["action"] != "DELAY":
                raise HTTPException(status_code=400, detail="Only delayed transactions can be confirmed")

            receiver_balance = None
            sender_balance = None

            # Debit sender only at confirmation time (for delayed transactions)
            if transaction["amount_deducted_at"] is None:
                cur.execute(
                    "SELECT balance FROM users WHERE user_id = %s",
                    (user_id,)
                )
                sender = cur.fetchone()
                if not sender or float(sender["balance"]) < float(transaction["amount"]):
                    raise HTTPException(status_code=400, detail="Insufficient balance")

                cur.execute(
                    "UPDATE users SET balance = balance - %s, updated_at = NOW() WHERE user_id = %s RETURNING balance",
                    (float(transaction["amount"]), user_id)
                )
                sender_balance = cur.fetchone()

                cur.execute(
                    """
                    INSERT INTO transaction_ledger (tx_id, operation, user_id, amount, remarks)
                    VALUES (%s, 'DEBIT', %s, %s, %s)
                    """,
                    (confirm_data.tx_id, user_id, float(transaction["amount"]), "Confirm delayed transaction")
                )

            # Credit receiver if it's a registered user
            if transaction["receiver_user_id"]:
                cur.execute(
                    """
                    UPDATE users 
                    SET balance = balance + %s, updated_at = NOW()
                    WHERE user_id = %s
                    RETURNING balance
                    """,
                    (float(transaction["amount"]), transaction["receiver_user_id"])
                )
                receiver_balance = cur.fetchone()
                
                # Log credit operation in ledger
                cur.execute(
                    """
                    INSERT INTO transaction_ledger (tx_id, operation, user_id, amount, remarks)
                    VALUES (%s, 'CREDIT', %s, %s, %s)
                    """,
                    (confirm_data.tx_id, transaction["receiver_user_id"], 
                     float(transaction["amount"]), f"Credit from {user_id}")
                )
            
            # Update transaction status
            cur.execute(
                """
                UPDATE transactions 
                SET db_status = 'confirmed', 
                    action = 'ALLOW',
                    amount_deducted_at = COALESCE(amount_deducted_at, NOW()),
                    amount_credited_at = NOW(),
                    updated_at = NOW()
                WHERE tx_id = %s
                """,
                (confirm_data.tx_id,)
            )
            
            conn.commit()

            # Clear dashboard cache for sender and receiver
            cache_delete(f"dashboard:{user_id}")
            if transaction.get("receiver_user_id"):
                cache_delete(f"dashboard:{transaction['receiver_user_id']}")
            
            # Emit WebSocket events
            try:
                # Transaction confirmed event
                asyncio.create_task(
                    ws_manager.send_to_user(user_id, {
                        "type": "transaction_confirmed",
                        "tx_id": confirm_data.tx_id,
                        "amount": float(transaction["amount"]),
                        "recipient": transaction["recipient_vpa"]
                    })
                )

                if sender_balance:
                    asyncio.create_task(
                        ws_manager.send_to_user(user_id, {
                            "type": "balance_updated",
                            "amount": -float(transaction["amount"]),
                            "operation": "debit",
                            "new_balance": float(sender_balance["balance"])
                        })
                    )
                
                # If receiver is registered user, notify them
                if receiver_balance:
                    asyncio.create_task(
                        ws_manager.send_to_user(transaction["receiver_user_id"], {
                            "type": "transaction_credited",
                            "tx_id": confirm_data.tx_id,
                            "amount": float(transaction["amount"]),
                            "sender": user_id
                        })
                    )
                    
            except Exception as e:
                print(f"WebSocket emit error: {e}")
            
            return {
                "status": "success",
                "message": "Transaction confirmed successfully",
                "tx_id": confirm_data.tx_id,
                "amount": float(transaction["amount"]),
                "receiver_balance": float(receiver_balance["balance"]) if receiver_balance else None
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_confirm)

@app.post("/api/transaction/cancel")
async def cancel_transaction(cancel_data: TransactionCancel, user_id: str = Depends(get_current_user)):
    """Cancel a delayed transaction and refund the sender"""
    def _cancel():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Get transaction details
            cur.execute(
                """
                SELECT tx_id, user_id, amount, recipient_vpa, receiver_user_id, action, db_status, amount_deducted_at
                FROM transactions 
                WHERE tx_id = %s AND user_id = %s AND db_status = 'pending'
                """,
                (cancel_data.tx_id, user_id)
            )
            
            transaction = cur.fetchone()
            if not transaction:
                raise HTTPException(status_code=404, detail="Transaction not found or not pending")
            
            if transaction["action"] != "DELAY":
                raise HTTPException(status_code=400, detail="Only delayed transactions can be cancelled")

            sender_balance = None

            # Refund sender only if funds were previously deducted
            if transaction["amount_deducted_at"] is not None:
                cur.execute(
                    """
                    UPDATE users 
                    SET balance = balance + %s, updated_at = NOW()
                    WHERE user_id = %s
                    RETURNING balance
                    """,
                    (float(transaction["amount"]), user_id)
                )
                
                sender_balance = cur.fetchone()
                
                # Log refund operation in ledger
                cur.execute(
                    """
                    INSERT INTO transaction_ledger (tx_id, operation, user_id, amount, remarks)
                    VALUES (%s, 'REFUND', %s, %s, %s)
                    """,
                    (cancel_data.tx_id, user_id, float(transaction["amount"]), "Cancelled delayed transaction")
                )
            
            # Update transaction status
            cur.execute(
                """
                UPDATE transactions 
                SET db_status = 'cancelled', 
                    action = 'BLOCK',
                    updated_at = NOW()
                WHERE tx_id = %s
                """,
                (cancel_data.tx_id,)
            )
            
            conn.commit()

            # Clear dashboard cache for sender and receiver
            cache_delete(f"dashboard:{user_id}")
            if transaction.get("receiver_user_id"):
                cache_delete(f"dashboard:{transaction['receiver_user_id']}")
            
            # Emit WebSocket events
            try:
                # Transaction cancelled event
                asyncio.create_task(
                    ws_manager.send_to_user(user_id, {
                        "type": "transaction_cancelled",
                        "tx_id": cancel_data.tx_id,
                        "amount": float(transaction["amount"]),
                        "refunded": sender_balance is not None
                    })
                )
                    
            except Exception as e:
                print(f"WebSocket emit error: {e}")
            
            return {
                "status": "success",
                "message": "Transaction cancelled successfully",
                "tx_id": cancel_data.tx_id,
                "amount": float(transaction["amount"]),
                "refunded": sender_balance is not None,
                "refunded_balance": float(sender_balance["balance"]) if sender_balance else None
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_cancel)

@app.get("/api/transaction/{tx_id}")
async def get_transaction(tx_id: str, user_id: str = Depends(get_current_user)):
    """Get transaction details"""
    def _get_transaction():
        conn = get_db_conn()
        try:
            cur = conn.cursor()
            
            # Get transaction details (user must be sender or receiver)
            cur.execute(
                """
                SELECT t.*, 
                       u.name as sender_name, u.phone as sender_phone,
                       r.name as receiver_name, r.phone as receiver_phone
                FROM transactions t
                LEFT JOIN users u ON t.user_id = u.user_id
                LEFT JOIN users r ON t.receiver_user_id = r.user_id
                WHERE t.tx_id = %s AND (t.user_id = %s OR t.receiver_user_id = %s)
                """,
                (tx_id, user_id, user_id)
            )
            
            transaction = cur.fetchone()
            if not transaction:
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            return {
                "status": "success",
                "transaction": dict_to_json_serializable(dict(transaction))
            }
        finally:
            conn.close()
    
    return await run_in_threadpool(_get_transaction)

@app.websocket("/ws/user/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time updates"""
    await ws_manager.connect(websocket, user_id)
    
    try:
        while True:
            # Receive and handle incoming messages
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                
                # Handle different message types
                if message.get("type") == "ping":
                    await ws_manager.send_personal_message(websocket, {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
                elif message.get("type") == "confirm_transaction":
                    # Handle confirm transaction via WebSocket
                    tx_id = message.get("tx_id")
                    # This would trigger the same logic as /api/transaction/confirm
                    await ws_manager.send_personal_message(websocket, {
                        "type": "confirm_received",
                        "tx_id": tx_id,
                        "status": "processing"
                    })
                elif message.get("type") == "cancel_transaction":
                    # Handle cancel transaction via WebSocket
                    tx_id = message.get("tx_id")
                    # This would trigger the same logic as /api/transaction/cancel
                    await ws_manager.send_personal_message(websocket, {
                        "type": "cancel_received", 
                        "tx_id": tx_id,
                        "status": "processing"
                    })
                    
            except json.JSONDecodeError:
                await ws_manager.send_personal_message(websocket, {"type": "error", "message": "Invalid JSON format"})
            except Exception as e:
                await ws_manager.send_personal_message(websocket, {"type": "error", "message": str(e)})
                
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error for user {user_id}: {e}")
        ws_manager.disconnect(websocket)

# ============================================================================
# API ENDPOINTS - HEALTH & INFO
# ============================================================================

@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "FDT Backend",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/info")
def app_info():
    """App information endpoint"""
    return {
        "app_name": "FDT - Fraud Detection in UPI",
        "version": "1.0.0",
        "description": "Real-time fraud detection for UPI transactions using ML",
        "features": [
            "User registration and authentication",
            "Real-time fraud detection with ML",
            "Transaction history and analytics",
            "Push notifications for fraud alerts",
            "Multi-model ensemble scoring"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
