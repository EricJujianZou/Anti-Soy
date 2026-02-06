# Anti-Soy: Security & Stability Backlog

> Issues identified during security scan. Prioritized for post-pilot fixes.

---

## Medium Priority

### 1. CORS Configuration Tightening
**File:** `server/main.py`
- Duplicate origin entries with different capitalization (`ericjujianzou.github.io` vs `EricJujianZou.github.io`) — only one will match
- Localhost ports should be removed or env-gated for production
- Consider loading `ALLOWED_ORIGINS` from environment variable

### 2. SQLite on Cloud Run — Ephemeral Storage
**File:** `server/main.py`
- Cloud Run instances are ephemeral — `database.db` is wiped on container restart
- All cached analysis results and user data are lost
- **Options:** Migrate to Cloud SQL (PostgreSQL), or back up SQLite to Cloud Storage on write

### 3. No Content Security Policy (CSP) Headers
- No CSP headers set on responses
- React's JSX escaping helps, but CSP adds defense in depth
- Add middleware to set `Content-Security-Policy` header

### 4. Client-Side URL Validation
**File:** `client/src/services/api.ts`
- GitHub URLs are sent to backend without client-side format validation
- Add a regex check before submitting to improve UX and reduce junk requests

### 5. Gemini API Cost Controls
- No spending alerts configured in Google Cloud
- No per-repo or per-day cost caps
- **Action:** Set up Google Cloud Budget Alerts, consider tracking API call counts in DB

---

## Low Priority

### 6. Database Schema Versioning
**File:** `server/main.py`
- Tables created via `Base.metadata.create_all()` at import time
- No migration system (Alembic) for schema changes
- Risk: schema changes require manual DB resets

### 7. HTTPS Enforcement
- Relies on Cloud Run to enforce HTTPS
- No explicit redirect from HTTP to HTTPS in application code
- **Verify:** Cloud Run settings have HTTPS-only traffic enabled

### 8. Error Message Mapping (Frontend)
**File:** `client/src/pages/Index.tsx`, `Repositories.tsx`
- Backend error messages are shown directly to users
- Should map common errors to user-friendly messages on the frontend

### 9. Client-Side Rate Limiting / Debouncing
**File:** `client/src/hooks/useApi.ts`
- No request deduplication or debounce on API calls
- Users can spam analyze button
- Add React Query `staleTime` and disable button while request is in-flight
