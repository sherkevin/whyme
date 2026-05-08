"""Account compliance & lifecycle endpoints (PRD10 §11.10).

Provides:
- ``DELETE /api/v1/me`` — soft-delete the current account.
- ``GET    /api/v1/me/export`` — export all user-owned data as JSON.
- ``POST   /api/v1/me/unsubscribe`` — opt out of all notifications.

These are the GDPR-style "right to be forgotten" / "right to data portability"
endpoints required for the V1 launch acceptance gate (todo §11.10).
"""

from agent_os.account.router import router as account_router

__all__ = ["account_router"]
