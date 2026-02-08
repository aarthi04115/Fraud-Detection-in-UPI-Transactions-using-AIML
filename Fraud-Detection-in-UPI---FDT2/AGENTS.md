# AGENTS.md - Coding Agent Guidelines

## Project Overview
FDT (Fraud Detection in UPI Transactions) - A production-ready fraud detection system using ensemble ML models with explainable fraud reasoning. The system analyzes 25+ transaction features across 10 risk categories.

**Stack:** Python 3.13 (FastAPI), React 18 (Frontend), PostgreSQL, Redis

---

## Build/Test/Run Commands

### Backend (Python/FastAPI)

```bash
# Start main application server (port 8000)
python -m app.main

# Start user-facing backend server (port 8001)
python backend/server.py

# Run all tests
python -m pytest tests/

# Run single test file
python tests/test_fraud_reasons.py
python tests/test_ml_standalone.py

# Run specific test with pytest (if installed)
python -m pytest tests/test_fraud_reasons.py::test_function_name

# Run ML model training
python train/train_models.py
python train/train_iforest.py

# Model evaluation
python tools/evaluate_model.py

# Database migration
python tools/migrate_schema_and_backfill.py
```

### Frontend (React)

```bash
cd frontend

# Install dependencies
npm install

# Start development server (port 3000)
npm start

# Build for production
npm run build

# Run tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run specific test file
npm test -- Dashboard.test.js
```

### Quick Setup

```bash
# Full setup (Windows PowerShell)
.\tools\setup_and_run.ps1

# Quick start (Unix)
bash quick_start.sh
```

---

## Code Style Guidelines

### Python

#### Import Order
1. Standard library imports
2. Third-party imports (FastAPI, numpy, etc.)
3. Local application imports (relative imports with `.`)

```python
# Standard library
import os
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Third-party
import numpy as np
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import psycopg2

# Local
from .scoring import score_transaction
from .fraud_reasons import generate_fraud_reasons
```

#### Naming Conventions
- **Files/Modules:** `snake_case` (e.g., `fraud_reasons.py`, `feature_engine.py`)
- **Classes:** `PascalCase` (e.g., `FraudReason`, `PatternMapper`)
- **Functions/Methods:** `snake_case` (e.g., `generate_fraud_reasons`, `extract_features`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `DB_URL`, `THRESHOLDS`, `REDIS_URL`)
- **Private functions:** prefix with `_` (e.g., `_MODELS_LOADED`, `_load_config`)

#### Type Hints
- Always use type hints for function parameters and return values
- Use `typing` module for complex types: `List`, `Dict`, `Optional`, `Tuple`, `Any`

```python
def generate_fraud_reasons(
    features: dict,
    scores: dict,
    thresholds: dict = None
) -> Tuple[List[FraudReason], float]:
    """Generate comprehensive fraud reasons."""
    pass
```

#### Docstrings
- Use triple-quoted docstrings for all modules, classes, and functions
- Format: Description + Args + Returns

```python
"""
Brief description of the module/function.

Args:
    param1: Description of param1
    param2: Description of param2

Returns:
    Description of return value
"""
```

#### Error Handling
- Use try-except blocks for external operations (DB, Redis, file I/O)
- Provide fallback behavior when possible
- Log errors with descriptive messages

```python
try:
    r = redis.from_url(redis_url, decode_responses=True)
    r.ping()
    print(f"✓ Connected to Redis at {redis_url}")
except Exception as e:
    print(f"⚠ Redis unavailable. Using fallback mode.")
    r = None
```

#### Code Formatting
- Indentation: 4 spaces (no tabs)
- Line length: Aim for 80-100 characters, max 120
- Use blank lines to separate logical sections
- Add section comments with `# ===` dividers for major sections

```python
# =========================================================================
# 1. ML MODEL CONFIDENCE
# =========================================================================
```

---

### JavaScript/React

#### Import Order
1. React imports
2. Third-party libraries
3. Local components/utilities
4. CSS files

```javascript
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import axios from 'axios';

import Dashboard from './components/Dashboard';
import { getUserDashboard } from './api';
import './App.css';
```

#### Naming Conventions
- **Components:** `PascalCase` (e.g., `Dashboard.js`, `FraudAlertEnhanced.js`)
- **Utilities/APIs:** `camelCase` (e.g., `api.js`, `cacheManager.js`)
- **Functions:** `camelCase` (e.g., `getUserDashboard`, `loadDashboard`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `API_BASE_URL`)

#### React Patterns
- Use functional components with hooks
- Destructure props in parameters
- Use `useState` and `useEffect` for state/lifecycle

```javascript
const Dashboard = ({ user, onLogout }) => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    loadDashboard();
  }, []);

  return (
    <div className="dashboard">
      {/* component content */}
    </div>
  );
};

export default Dashboard;
```

#### Async/Await
- Use async/await for API calls
- Always use try-catch for error handling

```javascript
const loadDashboard = async () => {
  try {
    setLoading(true);
    const data = await getUserDashboard();
    setDashboardData(data);
  } catch (err) {
    console.error('Failed to load dashboard:', err);
  } finally {
    setLoading(false);
  }
};
```

---

## Project Structure

```
FDT/
├── app/                    # Core Python application
│   ├── main.py            # FastAPI server (admin/dashboard)
│   ├── scoring.py         # ML scoring engine
│   ├── fraud_reasons.py   # Fraud reason generator
│   ├── feature_engine.py  # Feature extraction
│   ├── chatbot.py         # Chatbot integration
│   └── db_utils.py        # Database utilities
├── backend/               # User-facing API server
│   └── server.py          # FastAPI server (user auth + transactions)
├── frontend/              # React PWA
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── utils/         # Helper functions
│   │   ├── App.js         # Main app component
│   │   └── api.js         # API client
│   └── package.json
├── models/                # Trained ML models (.joblib)
├── tests/                 # Python test suite
├── train/                 # Model training scripts
├── tools/                 # Utility scripts
├── config/                # Configuration files
├── docs/                  # Documentation
└── requirements.txt       # Python dependencies
```

---

## Database Schema

### Key Tables
- `users` - User accounts (phone, name, email, password_hash)
- `transactions` - Transaction records with fraud scores
- `user_history` - Aggregated user behavior patterns
- `decisions` - User feedback on fraud alerts

---

## Testing Guidelines

### Python Tests
- All test files in `tests/` directory
- Prefix test files with `test_` (e.g., `test_fraud_reasons.py`)
- Use descriptive test function names: `test_<feature>_<scenario>`
- Import modules under test using absolute imports

```python
from app.fraud_reasons import generate_fraud_reasons, categorize_fraud_risk

def test_high_risk_transaction():
    scores = {'ensemble': 0.82, 'iforest': 0.85}
    features = {'amount': 50000.0, 'is_night': 1.0}
    reasons, composite = generate_fraud_reasons(features, scores)
    assert len(reasons) > 0
```

### React Tests
- Place test files next to components: `Component.test.js`
- Use React Testing Library patterns
- Test user interactions and data fetching

---

## Key Modules & APIs

### Python

**app/fraud_reasons.py**
- `generate_fraud_reasons(features, scores, thresholds) -> (List[FraudReason], float)`
- `categorize_fraud_risk(ensemble_score, reasons) -> dict`

**app/scoring.py**
- `score_transaction(tx) -> dict` - Main entry point
- `extract_features(tx) -> dict` - Extract 25+ features
- `score_with_ensemble(features) -> dict` - ML ensemble scoring

**app/feature_engine.py**
- `extract_features(tx) -> dict` - Feature extraction with Redis
- `get_feature_names() -> list` - Get feature names

### React

**src/api.js**
- `registerUser(userData)` - Register new user
- `loginUser(credentials)` - User login
- `getUserDashboard()` - Get dashboard data
- `createTransaction(transactionData)` - Create transaction
- `submitUserDecision(decisionData)` - Submit fraud feedback

---

## Environment Variables

Create `.env` file in root:

```bash
DB_URL=postgresql://fdt:fdtpass@localhost:5432/fdt_db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=change_in_production
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=<pbkdf2_sha256_hash>
```

Frontend `.env`:
```bash
REACT_APP_BACKEND_URL=http://localhost:8001
```

---

## Common Patterns

### Database Connection (Python)
```python
import psycopg2
import psycopg2.extras

def get_db_conn():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)

# Usage
with get_db_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM transactions WHERE tx_id = %s", (tx_id,))
        result = cur.fetchone()
```

### API Endpoints (FastAPI)
```python
@app.post("/api/transactions")
async def create_transaction(request: Request):
    data = await request.json()
    # Process transaction
    return JSONResponse({"status": "success"})
```

### React API Calls
```javascript
import { getUserDashboard } from './api';

const data = await getUserDashboard();
setDashboardData(data);
```

---

## Common Gotchas

1. **Redis Fallback:** Redis is optional - code gracefully falls back if unavailable
2. **UTF-8 BOM:** Config files may have UTF-8 BOM, handle with `.decode("utf-8-sig")`
3. **Timestamps:** Always use UTC timezone: `datetime.now(timezone.utc)`
4. **Model Loading:** Models are lazy-loaded and cached after first use
5. **Frontend Proxy:** React dev server proxies to `http://localhost:8001`

---

## Debugging

```bash
# Debug scoring
python tools/debug_scoring.py

# Analyze model scores
python tools/analyze_scores.py

# Check database schema
python scripts/check_schema.py

# Test database connection
python tests/test_db_conn.py

# Check dashboard data
python scripts/dashboard_check.py
```

---

## Git Workflow

```bash
# Standard workflow
git status
git add <files>
git commit -m "feat: descriptive commit message"
git push origin main

# Commit message prefixes
# feat: New feature
# fix: Bug fix
# refactor: Code refactoring
# test: Add/update tests
# docs: Documentation
# chore: Maintenance
```

---

**Last Updated:** January 2026  
**Python Version:** 3.13.11  
**React Version:** 18.3.1  
**FastAPI Version:** 0.123.9
