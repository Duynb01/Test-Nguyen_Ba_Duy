# Authentication & Authorization Test Plan

## 1. Overview
This document outlines the manual test strategy for verifying the Authentication & Authorization flows in the Todo application. Automated tests cover the happy paths and primary isolation boundaries, but manual testing is necessary to cover edge cases, session lifecycles, and environment-specific behaviors.

## 2. Test Environment & Tools
- **Environment:** Staging / Local Development.
- **Backend:** FastAPI running locally (`http://localhost:8000`).
- **Frontend:** React application running locally (`http://localhost:3000`).
- **Database:** PostgreSQL (for user and todo persistence) and Redis (for token blocklisting and caching).
- **Tools Required:** 
  - Web Browsers: Chrome, Firefox.
  - API Testing Tool: Postman, cURL, or Insomnia.
  - Inspect Tools: Chrome DevTools (Network & Application tabs), Redis CLI (optional, to verify blocklist).

## 3. Setup Requirements
1. Run `docker-compose up -d` to start Redis and PostgreSQL.
2. Start the Backend: `cd backend && uvicorn app.main:app --reload`.
3. Start the Frontend: `cd frontend && npm run dev`.
4. Create test users:
   - `admin@example.com` / `password123`
   - `user1@example.com` / `password123`
   - `user2@example.com` / `password123`

---

## 4. Manual Test Scenarios

### Scenario 1: Access Token Expiry and Refresh Flow
**Objective:** Verify that access tokens properly expire and the frontend seamlessly uses refresh tokens to maintain the session.
- **Steps:**
  1. Login with `user1@example.com` on the browser.
  2. In the backend `app/core/security.py`, temporarily change `ACCESS_TOKEN_EXPIRE_MINUTES` to `1` (1 minute) and restart the backend.
  3. Wait for 2 minutes on the frontend without refreshing the page.
  4. Attempt to create a new Todo.
- **Expected Result:** The frontend interceptor should detect the 401 error, automatically call `/api/v1/auth/refresh` using the stored refresh token, obtain a new access token, and replay the original Todo creation request seamlessly.

### Scenario 2: Concurrent Sessions & Global Logout
**Objective:** Verify that logging out explicitly revokes the token on the server-side, preventing reuse by malicious actors.
- **Steps:**
  1. Login with `user1@example.com` using **Browser A**.
  2. Extract the `access_token` from Browser A's local storage.
  3. Login with `user1@example.com` using **Browser B**.
  4. On **Browser A**, click "Sign Out".
  5. Open Postman, make a `GET /api/v1/todos` request using the `access_token` extracted from Browser A.
- **Expected Result:** Postman request should return a `401 Unauthorized` (Token has been revoked/blocklisted in Redis). Browser B's session might still be active if it uses a different token, but the token from Browser A must be dead.

### Scenario 3: Token Manipulation and Tampering
**Objective:** Ensure the backend rejects forged or altered JWTs.
- **Steps:**
  1. Login via Postman and receive an `access_token`.
  2. Go to `jwt.io` and decode the token.
  3. Change the payload (e.g., change the `sub` from `user1`'s ID to `user2`'s ID).
  4. Generate the new token without the correct server secret.
  5. Send a `GET /api/v1/todos` request using the altered token.
- **Expected Result:** The backend should reject the token with `401 Unauthorized` (Signature verification failed).

### Scenario 4: Cross-Origin Resource Sharing (CORS) Restrictions
**Objective:** Ensure that unauthorized domains cannot make API calls to the backend on behalf of a user.
- **Steps:**
  1. Open a terminal and run a simple HTTP server on a random port (e.g., `python -m http.server 9999`).
  2. Open `http://localhost:9999` in your browser.
  3. Open DevTools Console and execute a `fetch('http://localhost:8000/api/v1/auth/me')` request.
- **Expected Result:** The browser should block the request due to CORS policy, as `http://localhost:9999` is not in the allowed `CORS_ORIGINS`.

### Scenario 5: Brute Force / User Enumeration Prevention
**Objective:** Confirm that the login endpoint does not reveal whether an email exists in the system.
- **Steps:**
  1. Using Postman, send a login request with a completely non-existent email (`doesnotexist@example.com`) and any password. Note the HTTP status and error message.
  2. Send a login request with a valid email (`user1@example.com`) but a wrong password. Note the HTTP status and error message.
- **Expected Result:** In both cases, the exact same HTTP status (`401 Unauthorized`) and message ("Incorrect email or password") must be returned. The response time should also be similar to prevent timing attacks.
