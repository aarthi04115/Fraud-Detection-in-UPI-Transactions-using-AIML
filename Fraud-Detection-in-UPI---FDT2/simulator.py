#!/usr/bin/env python3
"""
FDT Transaction Simulator - Improved Version
Generates realistic transaction patterns for testing the fraud detection system.
"""

import requests
import uuid
import random
import time
import sys
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Optional
import json

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# Transaction patterns with realistic characteristics
PATTERNS = {
    "normal": {
        "weight": 75,  # Increased from 60 - most transactions are legitimate
        "amount_range": (50, 1500),  # Reduced max from 2000 - typical UPI amounts
        "users": (1, 50),  # Reduced pool - reuse users more often to build history
        "devices": (1, 40),  # Reduced pool - consistent devices
        "channels": ["app", "app", "app", "qr"],
        "new_device_prob": 0.02,  # Very low - people use same devices
        "description": "Regular small-medium transactions"
    },
    "medium_amount": {
        "weight": 10,  # New pattern - legitimate but larger amounts
        "amount_range": (1500, 5000),
        "users": (1, 50),
        "devices": (1, 40),
        "channels": ["app", "app", "qr"],
        "new_device_prob": 0.05,
        "description": "Legitimate larger transactions (bills, transfers)"
    },
    "suspicious": {
        "weight": 10,  # Reduced from 20
        "amount_range": (3000, 10000),  # Adjusted range
        "users": (40, 80),  # Different user pool
        "devices": (100, 200),  # New/unusual devices
        "channels": ["web", "qr", "qr"],
        "new_device_prob": 0.7,
        "description": "Larger amounts, new devices, unusual patterns"
    },
    "high_risk": {
        "weight": 3,  # Reduced from 10 - fraud is rare
        "amount_range": (8000, 25000),
        "users": (70, 100),  # Even different pool
        "devices": "uuid",  # Always new devices
        "channels": ["web", "web", "qr"],
        "new_device_prob": 1.0,
        "description": "Very large amounts, always new devices"
    },
    "burst": {
        "weight": 2,  # Reduced from 10 - velocity attacks are rare
        "amount_range": (500, 3000),
        "users": (1, 15),
        "devices": (1, 10),
        "channels": ["app", "qr", "web"],
        "new_device_prob": 0.1,
        "description": "Multiple rapid transactions (velocity risk)"
    }
}

# VPA patterns
VPA_PATTERNS = {
    "merchants": ["amazon", "flipkart", "swiggy", "zomato", "uber", "ola", "paytm", "phonepe", "gpay"],
    "common_names": ["rajesh", "priya", "amit", "neha", "suresh", "divya", "rahul", "pooja", "vijay", "sneha"]
}

class TransactionSimulator:
    def __init__(self, url: str, mode: str = "user", auth_token: Optional[str] = None, backend_url: Optional[str] = None):
        self.url = url
        self.mode = mode  # 'user' or 'admin'
        self.auth_token = auth_token
        self.backend_url = backend_url if backend_url else "http://localhost/8001"
        self.user_tokens: Dict[str, str] = {}  # Cache of user_id -> token
        self.current_user_index = 0
        self.stats = {
            "total": 0,
            "allowed": 0,
            "delayed": 0,
            "blocked": 0,
            "errors": 0,
            "balance_errors": 0
        }
    
    def get_or_create_user_token(self, user_id: str) -> Optional[str]:
        """Get cached token or create new user and get token"""
        if user_id in self.user_tokens:
            return self.user_tokens[user_id]
        
        # Create new user
        phone = f"99{user_id.replace('user_', '').zfill(8)}"  # e.g., user_001 -> 9900000001
        user_data = {
            "name": f"Simulator User {user_id}",
            "phone": phone,
            "password": "sim123",
            "email": f"{user_id}@simulator.test"
        }
        
        try:
            # Try to register
            response = requests.post(
                f"{self.backend_url}/api/register",
                json=user_data,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                token = result.get("token")
                if token:
                    self.user_tokens[user_id] = token
                    return token
            elif response.status_code == 400 and "already registered" in response.text:
                # User exists, try to login
                login_response = requests.post(
                    f"{self.backend_url}/api/login",
                    json={"phone": phone, "password": "sim123"},
                    timeout=5
                )
                if login_response.status_code == 200:
                    result = login_response.json()
                    token = result.get("token")
                    if token:
                        self.user_tokens[user_id] = token
                        return token
        except Exception as e:
            print(f"⚠️  Failed to get token for {user_id}: {e}")
        
        # Fallback to provided token
        return self.auth_token
        
    def generate_transaction(self, pattern_name: str = None) -> Dict:
        """Generate a realistic transaction based on pattern"""
        if pattern_name is None:
            # Random pattern based on weights
            pattern_name = random.choices(
                list(PATTERNS.keys()),
                weights=[p["weight"] for p in PATTERNS.values()]
            )[0]
        
        pattern = PATTERNS[pattern_name]
        
        # Generate amount
        min_amt, max_amt = pattern["amount_range"]
        amount = round(random.uniform(min_amt, max_amt), 2)
        
        # Generate user and device
        user_min, user_max = pattern["users"]
        user_id = f"user_{random.randint(user_min, user_max):03d}"
        
        if pattern["devices"] == "uuid":
            device_id = f"device_{uuid.uuid4().hex[:12]}"
        else:
            dev_min, dev_max = pattern["devices"]
            device_id = f"device_{random.randint(dev_min, dev_max):03d}"
        
        # Channel
        channel = random.choice(pattern["channels"])
        
        # Transaction type and recipient
        tx_type = random.choice(["P2P", "P2M", "P2M"])
        if tx_type == "P2P":
            name = random.choice(VPA_PATTERNS["common_names"])
            recipient_vpa = f"{name}{random.randint(1,99)}@upi"
        else:
            merchant = random.choice(VPA_PATTERNS["merchants"])
            recipient_vpa = f"{merchant}{random.randint(1,20)}@upi"
        
        # Generate transaction
        tx = {
            "tx_id": f"tx_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "device_id": device_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "amount": amount,
            "recipient_vpa": recipient_vpa,
            "tx_type": tx_type,
            "channel": channel,
        }
        
        # Add metadata for display
        tx["_metadata"] = {
            "pattern": pattern_name,
            "is_new_device": random.random() < pattern["new_device_prob"],
            "description": pattern["description"]
        }
        
        return tx
    
    def send_transaction(self, tx: Dict) -> Dict:
        """Send transaction to backend"""
        metadata = tx.pop("_metadata", {})
        
        try:
            headers = {}
            if self.mode == "user":
                # Get token for the specific user
                user_id = tx.get("user_id", "user_001")
                token = self.get_or_create_user_token(user_id)
                
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                
                # For user mode, use the API endpoint format
                payload = {
                    "amount": tx["amount"],
                    "recipient_vpa": tx["recipient_vpa"],
                    "tx_type": tx["tx_type"],
                    "remarks": f"Simulated {metadata.get('pattern', 'normal')} transaction",
                    "device_id": tx.get("device_id")
                }
                response = requests.post(self.url, json=payload, headers=headers, timeout=5)
            else:
                # Admin mode
                response = requests.post(self.url, json=tx, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                tx["_metadata"] = metadata
                tx["_response"] = result
                return tx
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            error_msg = str(e)
            tx["_metadata"] = metadata
            tx["_error"] = error_msg
            
            # Track balance errors separately
            if "Insufficient balance" in error_msg:
                self.stats["balance_errors"] += 1
            
            return tx
    
    def display_transaction(self, tx: Dict):
        """Display transaction result with colors"""
        metadata = tx.get("_metadata", {})
        response = tx.get("_response")
        error = tx.get("_error")
        
        # Pattern display
        pattern = metadata.get("pattern", "unknown")
        pattern_icons = {
            "normal": f"{Colors.GREEN}✅ Normal{Colors.RESET}",
            "medium_amount": f"{Colors.CYAN}💰 Medium Amount{Colors.RESET}",
            "suspicious": f"{Colors.YELLOW}⚠️  Suspicious{Colors.RESET}",
            "high_risk": f"{Colors.RED}🚨 High Risk{Colors.RESET}",
            "burst": f"{Colors.MAGENTA}⚡ Burst{Colors.RESET}"
        }
        
        print(f"\n{Colors.CYAN}{'─' * 80}{Colors.RESET}")
        print(f"{Colors.BOLD}Pattern:{Colors.RESET}    {pattern_icons.get(pattern, pattern)}")
        print(f"{Colors.BOLD}TX ID:{Colors.RESET}      {tx.get('tx_id', 'N/A')}")
        print(f"{Colors.BOLD}User:{Colors.RESET}       {tx.get('user_id', 'N/A'):<15} {Colors.BOLD}Device:{Colors.RESET} {tx.get('device_id', 'N/A')[:25]}")
        print(f"{Colors.BOLD}Amount:{Colors.RESET}     ₹{tx.get('amount', 0):<10.2f} {Colors.BOLD}Type:{Colors.RESET} {tx.get('tx_type', 'N/A'):<5} {Colors.BOLD}Channel:{Colors.RESET} {tx.get('channel', 'N/A')}")
        print(f"{Colors.BOLD}Recipient:{Colors.RESET}  {tx.get('recipient_vpa', 'N/A')}")
        
        if error:
            print(f"{Colors.RED}{Colors.BOLD}❌ Error:{Colors.RESET} {error}")
            self.stats["errors"] += 1
        elif response:
            # Extract risk score and action based on mode
            if self.mode == "user":
                risk_score = response.get("transaction", {}).get("risk_score", 0)
                action = response.get("transaction", {}).get("action", "UNKNOWN")
            else:
                risk_score = response.get("inserted", {}).get("risk_score", 0)
                action = response.get("inserted", {}).get("action", "UNKNOWN")
            
            # Action icons
            action_display = {
                "ALLOW": f"{Colors.GREEN}🟢 ALLOW{Colors.RESET}",
                "DELAY": f"{Colors.YELLOW}🟡 DELAY{Colors.RESET}",
                "BLOCK": f"{Colors.RED}🔴 BLOCK{Colors.RESET}"
            }
            
            print(f"{Colors.BOLD}Risk Score:{Colors.RESET} {risk_score:.4f} ({risk_score*100:.2f}%)")
            print(f"{Colors.BOLD}Action:{Colors.RESET}     {action_display.get(action, action)}")
            
            # Update stats
            self.stats["total"] += 1
            if action == "ALLOW":
                self.stats["allowed"] += 1
            elif action == "DELAY":
                self.stats["delayed"] += 1
            elif action == "BLOCK":
                self.stats["blocked"] += 1
    
    def display_stats(self):
        """Display running statistics"""
        total = self.stats["total"]
        if total == 0:
            return
        
        print(f"\n{Colors.BLUE}{'═' * 80}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}📊 Statistics (Total: {total}){Colors.RESET}")
        print(f"{Colors.GREEN}  Allowed: {self.stats['allowed']} ({self.stats['allowed']/total*100:.1f}%){Colors.RESET}")
        print(f"{Colors.YELLOW}  Delayed: {self.stats['delayed']} ({self.stats['delayed']/total*100:.1f}%){Colors.RESET}")
        print(f"{Colors.RED}  Blocked: {self.stats['blocked']} ({self.stats['blocked']/total*100:.1f}%){Colors.RESET}")
        if self.stats['errors'] > 0:
            print(f"{Colors.RED}  Errors:  {self.stats['errors']}{Colors.RESET}")
            if self.stats['balance_errors'] > 0:
                print(f"{Colors.YELLOW}    └─ Balance errors: {self.stats['balance_errors']}{Colors.RESET}")
        if self.mode == "user":
            print(f"{Colors.CYAN}  Users created: {len(self.user_tokens)}{Colors.RESET}")
        print(f"{Colors.BLUE}{'═' * 80}{Colors.RESET}\n")

def main():
    parser = argparse.ArgumentParser(description="FDT Transaction Simulator")
    parser.add_argument("--url", default="http://localhost:8001/api/transaction", help="Backend URL")
    parser.add_argument("--backend", default="http://localhost:8001", help="Backend base URL")
    parser.add_argument("--mode", choices=["user", "admin"], default="user", help="Simulation mode")
    parser.add_argument("--token", help="Auth token for user mode (optional - will create users automatically)")
    parser.add_argument("--pattern", choices=list(PATTERNS.keys()), help="Specific pattern to test")
    parser.add_argument("--count", type=int, help="Number of transactions (default: infinite)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between transactions (seconds)")
    parser.add_argument("--stats-interval", type=int, default=10, help="Show stats every N transactions")
    
    args = parser.parse_args()
    
    # Adjust URL based on mode
    if args.mode == "admin":
        if "api/transaction" in args.url:
            args.url = "http://localhost:8000/transactions"
    
    simulator = TransactionSimulator(args.url, args.mode, args.token, args.backend)
    
    # Print header
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}🚀 UPI Fraud Detection Simulator{Colors.RESET}")
    print(f"{Colors.BLUE}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}Mode:{Colors.RESET}       {args.mode.upper()}")
    print(f"{Colors.BOLD}URL:{Colors.RESET}        {args.url}")
    if args.mode == "user":
        print(f"{Colors.BOLD}Backend:{Colors.RESET}    {args.backend}")
        if args.token:
            print(f"{Colors.BOLD}Auth:{Colors.RESET}       Single user token provided")
        else:
            print(f"{Colors.BOLD}Auth:{Colors.RESET}       Multi-user mode (auto-create)")
    if args.pattern:
        print(f"{Colors.BOLD}Pattern:{Colors.RESET}    {args.pattern} only")
    print(f"{Colors.BOLD}Delay:{Colors.RESET}      {args.delay}s between transactions")
    print(f"{Colors.BLUE}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.YELLOW}Press Ctrl+C to stop{Colors.RESET}\n")
    
    try:
        count = 0
        while True:
            # Generate and send transaction
            tx = simulator.generate_transaction(args.pattern)
            result = simulator.send_transaction(tx)
            simulator.display_transaction(result)
            
            count += 1
            
            # Show stats periodically
            if count % args.stats_interval == 0:
                simulator.display_stats()
            
            # Check if we've reached the limit
            if args.count and count >= args.count:
                break
            
            time.sleep(args.delay)
            
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⏹️  Simulator stopped by user{Colors.RESET}")
        simulator.display_stats()
        sys.exit(0)

if __name__ == "__main__":
    main()
