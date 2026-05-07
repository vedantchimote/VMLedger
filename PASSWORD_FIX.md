# Password Registration Fix - RESOLVED ✅

## Issue
Users were unable to register with the error: "Password is too long. Maximum is 72 bytes."

This occurred even with passwords as short as 12 characters.

## Root Cause
The issue was caused by incompatibility between bcrypt versions and passlib 1.7.4:

### Initial Problem (bcrypt 5.0.0)
- bcrypt 5.0.0 introduced breaking API changes
- passlib 1.7.4 doesn't support these changes
- This caused bcrypt to incorrectly reject all passwords

### Second Problem (bcrypt 4.1.3)
- bcrypt 4.1.3 removed the `__about__` attribute
- passlib 1.7.4 tries to read `_bcrypt.__about__.__version__`
- This caused an AttributeError and fallback to incorrect behavior

### Final Solution (bcrypt 3.2.2)
- bcrypt 3.2.2 is fully compatible with passlib 1.7.4
- All password operations work correctly

## Solution
Downgraded bcrypt from 5.0.0 → 4.1.3 → 3.2.2 (final working version).

### Changes Made

1. **Updated requirements.txt**
   - Changed `bcrypt==5.0.0` to `bcrypt==3.2.2`
   - This version is fully compatible with passlib 1.7.4

2. **Added password byte length validation** (defensive programming)
   - Added validation in `vmledger/services/auth_service.py`:
     - `_validate_password_complexity()` now checks password byte length
     - `_hash_password()` now checks byte length before hashing
   - Added frontend validation in `frontend/lib/validation.ts`

3. **Installed bcrypt 3.2.2 in all running containers**
   ```bash
   docker exec vmledger-api pip install "passlib[bcrypt]==1.7.4" "bcrypt==3.2.2" --force-reinstall
   docker exec vmledger-celery-worker pip install "bcrypt==3.2.2" --force-reinstall
   docker exec vmledger-celery-beat pip install "bcrypt==3.2.2" --force-reinstall
   ```

4. **Restarted API container**
   ```bash
   docker restart vmledger-api
   ```

## Testing Results ✅

### Registration Test
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/auth/register" -Method POST -ContentType "application/json" -Body '{"username":"testuser6","email":"test6@example.com","password":"TestPass123!"}'
```
**Result**: SUCCESS - User registered successfully

### Login Test
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/auth/login" -Method POST -ContentType "application/json" -Body '{"username":"testuser6","password":"TestPass123!"}'
```
**Result**: SUCCESS - User authenticated successfully

## Password Requirements
- Minimum 12 characters
- Maximum 72 bytes (bcrypt limitation)
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

## Status
✅ **RESOLVED** - Registration and login are now working correctly with bcrypt 3.2.2

## Next Steps
- Frontend registration at http://localhost:3000/register should now work
- For permanent fix, rebuild Docker images: `docker-compose build`
- All containers now have bcrypt 3.2.2 installed

## Technical Details

### Why bcrypt 3.2.2?
- passlib 1.7.4 was released in 2018 and expects older bcrypt API
- bcrypt 4.x removed `__about__` attribute that passlib relies on
- bcrypt 5.x introduced additional breaking changes
- bcrypt 3.2.2 (released 2021) is the last version fully compatible with passlib 1.7.4

### Alternative Solutions (not chosen)
1. **Upgrade passlib**: passlib hasn't been updated since 2020, no newer version available
2. **Switch to argon2**: Would require rewriting authentication code
3. **Use bcrypt directly**: Would lose passlib's password context features

---

**Fixed**: May 8, 2026  
**Status**: ✅ Resolved
