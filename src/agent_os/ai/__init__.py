"""PRD10 Mydow AI conversation domain."""

from agent_os.ai.models import (
    AIConversation,
    AIConversationMode,
    AIMessage,
    AIMessageRole,
    AIMessageStatus,
)


def __getattr__(name: str):
    """Lazy-export the FastAPI router without creating import cycles."""

    if name == "router":
        from agent_os.ai.router import router

        return router
    raise AttributeError(name)

__all__ = [
    "AIConversation",
    "AIConversationMode",
    "AIMessage",
    "AIMessageRole",
    "AIMessageStatus",
    "router",
]
