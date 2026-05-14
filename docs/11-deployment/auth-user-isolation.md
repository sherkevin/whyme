# Mydow Auth / User Isolation Readiness

## Current decision

For the 50-user internal beta, Mydow keeps the existing FastAPI auth module and
hardens it in place instead of migrating the whole stack to an external identity
provider immediately. This avoids destabilizing PRD10 data flows while still
aligning the implementation with mature auth products.

Open-source options reviewed:

- FastAPI Users: mature FastAPI-native user management with register, login,
  reset password, email verification, JWT/cookie/database/Redis strategies, and
  async SQLAlchemy support. It is in maintenance mode, so it is a good reference
  or later migration target, not a reason to rewrite the beta branch today.
- SuperTokens: stronger full-stack auth/session product with email/password,
  passwordless, email verification, session rotation, revocation, and migration
  guides. It is the better candidate if Mydow later wants managed auth UI,
  multi-tenant account linking, passkeys, or central session admin.

## Implemented beta contract

- User identity is `users.id` (UUID). PRD10 data APIs must filter by
  `current_user.id`; the isolation regression suite covers cards, KB folders,
  KB documents, AI conversations/messages, skill runs, search, and settings.
- Passwords are never stored as plaintext. New hashes use bcrypt. Legacy
  `salt$sha256` hashes are accepted only for login compatibility and upgraded
  to bcrypt on successful login.
- Login persistence is not "remembering the password". The browser stores an
  access token plus a refresh token if the user chooses "remember login"; the
  backend stores only token hashes in `sessions` and rotates refresh tokens on
  use.
- Registration supports email verification through
  `POST /api/v1/auth/send-code` followed by `POST /api/v1/auth/register/email`.
  Password login remains available for existing accounts and API clients.
- Verification codes are 6-digit one-time codes stored in Redis with TTL,
  email/IP rate limits, attempt counts, lockout, and cryptographic randomness.
- Demo login is opt-in only. Internal beta and production should keep
  `AGENTOS_DEMO_MODE=off`; investor/local demo can set it to `on`.

## Required environment for real email-code registration

```env
REDIS_URL=redis://:<password>@redis:6379/0
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...
SMTP_FROM=noreply@mydow.example
SMTP_USE_TLS=true
JWT_SECRET_KEY=<long-random-secret>
SECRET_KEY=<long-random-secret>
AGENTOS_DEMO_MODE=off
```

If Redis or SMTP is missing, `/auth/send-code` must fail visibly; the frontend
must not pretend a verification code was sent.

## Beta checklist

- [ ] `AGENTOS_DEMO_MODE=off` in the beta `.env`.
- [ ] Redis health check green before opening registration.
- [ ] SMTP smoke test can receive an actual code.
- [ ] `POST /auth/register/email` creates `users.is_verified=true`.
- [ ] `POST /auth/login` creates one active `sessions` row.
- [ ] `POST /auth/refresh` rotates refresh token and rejects replay.
- [ ] `POST /auth/logout` revokes the current server-side session.
- [ ] `tests/integration/api/test_prd10_user_isolation.py` passes before deploy.
