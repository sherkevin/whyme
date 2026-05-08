"""OpenAPI enrichment for PRD10 public API docs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


JSON = "application/json"


OPERATION_EXAMPLES: dict[tuple[str, str], dict[str, Any]] = {
    ("post", "/api/v1/auth/login"): {
        "summary": "Login with username/password",
        "request": {
            "demo": {
                "summary": "Demo user login",
                "value": {"username": "demo", "password": "demo123456"},
            }
        },
        "response": {
            "success": {
                "summary": "Token envelope",
                "value": {
                    "success": True,
                    "data": {
                        "access_token": "eyJhbGciOi...",
                        "refresh_token": "eyJhbGciOi...",
                        "token_type": "bearer",
                        "expires_in": 1800,
                    },
                    "request_id": "req_openapi_demo",
                },
            }
        },
        "curl": "curl -X POST http://localhost:8000/api/v1/auth/login "
        "-H 'Content-Type: application/json' "
        "-d '{\"username\":\"demo\",\"password\":\"demo123456\"}'",
    },
    ("post", "/api/v1/capture/text"): {
        "summary": "Capture raw inspiration text",
        "request": {
            "inspiration": {
                "summary": "Text capture with source metadata",
                "value": {
                    "content": "客户访谈里反复提到：知识库需要能按标签自动归档，并保留原始输入。",
                    "source_url": "https://example.com/interview/42",
                    "auto_process": True,
                },
            }
        },
        "response": {
            "created": {
                "summary": "Inbox item + card + job",
                "value": {
                    "success": True,
                    "data": {
                        "inbox_item": {
                            "id": "018f0d4c-8a13-7b79-b4e8-4f5f1a7f4d20",
                            "type": "text",
                            "status": "processed",
                            "processing_status": "completed",
                            "title": "知识库自动归档需求",
                            "tags": ["知识库", "标签归档", "用户访谈"],
                        },
                        "card": {
                            "id": "018f0d4c-8b45-7e51-9e85-5535c8ed9f23",
                            "title": "知识库自动归档需求",
                            "summary": "用户希望系统自动按标签归档并保留原文追溯。",
                        },
                        "job_id": "018f0d4c-8b00-7f2c-9c36-3450c9f39f15",
                    },
                    "request_id": "req_capture_text",
                }
            }
        },
        "curl": "curl -X POST http://localhost:8000/api/v1/capture/text "
        "-H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' "
        "-d '{\"content\":\"客户访谈里反复提到自动归档\",\"auto_process\":true}'",
    },
    ("post", "/api/v1/kb/folders"): {
        "summary": "Create a knowledge folder",
        "request": {
            "folder": {
                "summary": "Folder with visual metadata",
                "value": {
                    "name": "用户访谈",
                    "description": "沉淀访谈纪要、原始输入和 AI 摘要",
                    "color": "#3B82F6",
                    "icon": "messages-square",
                },
            }
        },
        "response": {
            "created": {
                "summary": "Folder DTO",
                "value": {
                    "success": True,
                    "data": {
                        "id": "018f0d4d-5a18-7e0c-8f05-91ef1f74a994",
                        "name": "用户访谈",
                        "parent_id": None,
                        "is_favorite": False,
                    },
                    "request_id": "req_kb_folder",
                },
            }
        },
        "curl": "curl -X POST http://localhost:8000/api/v1/kb/folders "
        "-H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' "
        "-d '{\"name\":\"用户访谈\",\"color\":\"#3B82F6\",\"icon\":\"messages-square\"}'",
    },
    ("post", "/api/v1/ai/conversations"): {
        "summary": "Create a Mydow AI conversation",
        "request": {
            "rag": {
                "summary": "RAG conversation scoped to KB",
                "value": {
                    "title": "本周用户洞察总结",
                    "mode": "knowledge",
                    "context_scope": {
                        "folder_ids": ["018f0d4d-5a18-7e0c-8f05-91ef1f74a994"]
                    },
                },
            }
        },
        "response": {
            "created": {
                "summary": "Conversation DTO",
                "value": {
                    "success": True,
                    "data": {
                        "id": "018f0d4d-7db5-7ec3-bf76-356502492fb6",
                        "title": "本周用户洞察总结",
                        "mode": "knowledge",
                        "message_count": 0,
                    },
                    "request_id": "req_ai_conversation",
                },
            }
        },
        "curl": "curl -X POST http://localhost:8000/api/v1/ai/conversations "
        "-H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' "
        "-d '{\"title\":\"本周用户洞察总结\",\"mode\":\"knowledge\"}'",
    },
    ("post", "/api/v1/ai/conversations/{conversation_id}/messages/stream"): {
        "summary": "Stream a RAG answer with SSE",
        "request": {
            "question": {
                "summary": "Question with selected context",
                "value": {
                    "content": "把用户访谈里关于自动归档的需求整理成 3 条产品建议。",
                    "model": "deepseek-v4-flash",
                    "context": {"use_knowledge_base": True},
                },
            }
        },
        "response": {
            "sse": {
                "summary": "SSE event stream",
                "value": "event: token\\ndata: {\"delta\":\"建议\"}\\n\\n",
            }
        },
        "curl": "curl -N -X POST "
        "http://localhost:8000/api/v1/ai/conversations/<conversation_id>/messages/stream "
        "-H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' "
        "-d '{\"content\":\"把用户访谈整理成 3 条建议\"}'",
    },
    ("post", "/api/v1/skills/{skill_id}/run"): {
        "summary": "Run a skill on real input/context",
        "request": {
            "run": {
                "summary": "Generate a report document",
                "value": {
                    "input": {
                        "goal": "把这些访谈记录生成一份产品机会报告",
                        "text": "用户希望自动归档、可追溯、可搜索。",
                    },
                    "context": {"folder_ids": ["018f0d4d-5a18-7e0c-8f05-91ef1f74a994"]},
                    "save_output": True,
                },
            }
        },
        "response": {
            "accepted": {
                "summary": "Skill run job",
                "value": {
                    "success": True,
                    "data": {
                        "skill_run_id": "018f0d4e-112f-7e7c-a661-b48a7f72fb32",
                        "job_id": "018f0d4e-119a-7690-bd27-0ee95b26ec40",
                        "status": "queued",
                    },
                    "request_id": "req_skill_run",
                },
            }
        },
        "curl": "curl -X POST http://localhost:8000/api/v1/skills/<skill_id>/run "
        "-H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' "
        "-d '{\"input\":{\"goal\":\"生成产品机会报告\",\"text\":\"用户希望自动归档\"},\"save_output\":true}'",
    },
    ("get", "/api/v1/search"): {
        "summary": "Search cards, documents, folders, messages, and skills",
        "response": {
            "results": {
                "summary": "Grouped search results",
                "value": {
                    "success": True,
                    "data": {
                        "items": [
                            {
                                "object_type": "document",
                                "title": "用户访谈摘要",
                                "summary": "自动归档与追溯是高频诉求。",
                            }
                        ],
                        "pagination": {
                            "page": 1,
                            "page_size": 20,
                            "total": 1,
                            "has_more": False,
                        },
                    },
                    "request_id": "req_search",
                },
            }
        },
        "curl": "curl 'http://localhost:8000/api/v1/search?q=自动归档&mode=hybrid&object_type=document' "
        "-H 'Authorization: Bearer <token>'",
    },
}


def install_openapi_examples(app: FastAPI) -> None:
    """Install a custom OpenAPI builder with PRD10 examples and code samples."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
            contact=app.contact,
            license_info=app.license_info,
        )
        schema["servers"] = [
            {"url": "http://localhost:8000", "description": "Local development"},
            {"url": "https://demo.mydow.com", "description": "Demo deployment"},
        ]
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Use the access_token returned by /api/v1/auth/login.",
        }

        for path, path_item in schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if method.lower() not in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "options",
                    "head",
                }:
                    continue
                if path.startswith("/api/v1/") and not _is_public_api(path):
                    operation["security"] = [{"BearerAuth": []}]
                _apply_operation_example(operation, method, path)

        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


def _is_public_api(path: str) -> bool:
    return path.startswith("/api/v1/auth/") or path.startswith("/api/v1/demo/")


def _apply_operation_example(
    operation: dict[str, Any],
    method: str,
    path: str,
) -> None:
    example = OPERATION_EXAMPLES.get((method.lower(), path))
    if not example:
        return

    if example.get("summary"):
        operation.setdefault("summary", example["summary"])
    operation.setdefault("x-codeSamples", []).append(
        {"lang": "cURL", "label": "cURL", "source": example["curl"]}
    )

    request_examples = example.get("request")
    if request_examples:
        content = (
            operation.setdefault("requestBody", {})
            .setdefault("content", {})
            .setdefault(JSON, {})
        )
        content["examples"] = deepcopy(request_examples)

    response_examples = example.get("response")
    if response_examples:
        responses = operation.setdefault("responses", {})
        response = responses.setdefault("200", {"description": "Successful Response"})
        content = response.setdefault("content", {}).setdefault(JSON, {})
        content["examples"] = deepcopy(response_examples)
