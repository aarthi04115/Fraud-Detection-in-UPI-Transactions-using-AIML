# Debugging Session Persistence Issue

## Quick Diagnostic Steps

### Step 1: Check localStorage
Open DevTools (F12) → Application → Storage → Local Storage → [Your Domain]

Look for:
- `fdt_token` - Should contain a JWT token
- `fdt_user` - Should contain a JSON object with user data

**If these exist:** Token is being saved ✓
**If these are empty:** Token not being saved to localStorage ✗

### Step 2: Check Console Messages
Open DevTools → Console tab

After refreshing, you should see:
- `🔧 FDT API Configuration:` - Shows backend URL
- `✓ Session restored from localStorage` - Token was found and restored
- OR `⚠ Token has expired, clearing session` - Token is expired

**If you see neither:** Session restoration didn't run properly

### Step 3: Check Token Validity
Run this in the console:

```javascript
const token = localStorage.getItem('fdt_token');
console.log('Token:', token);

if (token) {
  try {
    const parts = token.split('.');
    const decoded = JSON.parse(atob(parts[1]));
    console.log('Token decoded:', decoded);
    
    const expiryTime = decoded.exp * 1000;
    const currentTime = Date.now();
    const msUntilExpiry = expiryTime - currentTime;
    const minUntilExpiry = msUntilExpiry / 1000 / 60;
    
    console.log(`Token expires in: ${minUntilExpiry.toFixed(0)} minutes`);
    console.log(`Expired? ${currentTime > expiryTime ? 'YES ✗' : 'NO ✓'}`);
  } catch (e) {
    console.error('Could not decode token:', e);
  }
}
```

### Step 4: Test API Call
Run this to test if the token works:

```javascript
const token = localStorage.getItem('fdt_token');
fetch('https://w1r757gb-8001.inc1.devtunnels.ms/api/user/dashboard', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})
  .then(r => {
    console.log('Status:', r.status);
    return r.json();
  })
  .then(data => console.log('Response:', data))
  .catch(e => console.error('Error:', e));
```

---

## Expected Behavior

### ✓ Working (After Login → Refresh)
1. User logs in successfully
2. localStorage now has `fdt_token` and `fdt_user`
3. User refreshes page
4. Console shows: `✓ Session restored from localStorage`
5. User stays on dashboard
6. API calls work normally

### ✗ Not Working (Current Issue)
1. User logs in successfully
2. localStorage has data
3. User refreshes page
4. User is redirected to login page
5. Console shows either:
   - `⚠ Token has expired, clearing session`
   - OR `❌ Received 401 - token invalid or expired`
   - OR error message from failed API call

---

## Common Issues & Solutions

### Issue: "Token has expired"
**Problem:** JWT token has `exp` claim in the past
**Solution:** Login generates tokens with very short expiry

**Check in backend `/api/login` endpoint:**
- Look for: `exp = datetime.now(...) + timedelta(hours=24)`
- Make sure expiry is set to 24 hours from now, not 24 seconds

### Issue: "Received 401" on Dashboard load
**Problem:** API returns 401, but token looks valid
**Solution:** Backend is rejecting the token for some reason

**Check in backend:**
1. Is the JWT secret key the same? (`JWT_SECRET_KEY` in env)
2. Is the token algorithm correct? (Should be HS256)
3. Check server logs for exact error

### Issue: localStorage is empty after refresh
**Problem:** Session isn't being saved at login
**Solution:** `handleLogin` in App.js not being called properly

**Check:**
1. Did you see success message after login?
2. Check LoginScreen → does it call `onLogin(userData, token)`?
3. Check NetworkTab → does `/api/login` return both `user` and `token`?

---

## Files to Check

1. **Frontend Session Restoration:**
   - `frontend/src/App.js` - Lines 45-77 (Session restore logic)
   - `frontend/src/App.js` - Lines 79-87 (Logout event listener)

2. **API Configuration:**
   - `frontend/src/api.js` - Lines 35-57 (Response interceptor)

3. **Login Flow:**
   - `frontend/src/components/LoginScreen.js` - Look for `handleLogin` call
   - `frontend/src/api.js` - `loginUser()` function

4. **Backend Token Generation:**
   - `backend/server.py` - Look for `create_access_token` or JWT generation
   - Check the `exp` (expiry) claim value

---

## If Still Not Working

Please provide:
1. Console output after refresh (copy-paste entire console)
2. Network tab → login request → Response (scroll to see full response)
3. Storage tab → localStorage values for `fdt_token` and `fdt_user`
4. Backend logs when you make API calls

With this info, I can identify the exact issue.
