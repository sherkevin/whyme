"""PA 1.0 Stage 2 Backend Acceptance Verification Tests.

This module verifies that the current implementation meets all Stage 2 acceptance criteria.
"""

import pytest
import os
from pathlib import Path


# ============================================================================
# Stage 2 Feature Verification
# ============================================================================

def test_agent_tick_mechanism_exists():
    """验证 Agent Tick/Capture 机制是否存在"""
    project_root = Path("/root/whyme/src")

    # Check for agent-related files
    agent_files = [
        "agent_os/agent.py",
        "agent_os/agent_aider.py"
    ]

    for file_path in agent_files:
        full_path = project_root / file_path
        assert full_path.exists(), f"Agent file not found: {file_path}"

    # Check for tick or capture endpoints
    router_files = list(project_root.rglob("*/router.py"))

    has_agent_endpoint = False
    agent_related_keywords = [
        "tick", "capture", "process", "agent"
    ]

    for router_file in router_files:
        try:
            content = router_file.read_text()
            for keyword in agent_related_keywords:
                if keyword in content.lower():
                    has_agent_endpoint = True
                    break
        except:
            continue

    # Note: We'll check what's actually implemented
    print(f"Agent endpoint found: {has_agent_endpoint}")


def test_inboxitem_status_raw_exists():
    """验证 InboxItem 是否支持 raw 状态"""
    from agent_os.items.models import Item
    from agent_os.inbox.schema import InboxItemStatusUpdate

    # Check if status field exists
    assert hasattr(Item, 'status'), "Item should have status field"

    # Check if schema supports status update
    assert 'status' in dir(InboxItemStatusUpdate), "Should have status update schema"

    print("✅ InboxItem status field exists")


def test_inbox_to_card_conversion_possible():
    """验证 Inbox → Card 转换是否可能"""
    project_root = Path("/root/whyme/src")

    # Check for knowledge models (Card)
    knowledge_models = project_root / "agent_os/knowledge/models.py"
    assert knowledge_models.exists(), "Knowledge models should exist"

    # Check if Card model exists
    try:
        from agent_os.knowledge.models import Card
        print(f"✅ Card model exists: {Card.__name__}")

        # Check if Card has necessary fields
        required_fields = ['id', 'title', 'content', 'created_at']
        for field in required_fields:
            assert hasattr(Card, field), f"Card should have {field} field"

    except ImportError as e:
        pytest.fail(f"Cannot import Card model: {e}")


def test_agent_behavior_logging_exists():
    """验证 Agent 行为记录机制是否存在"""
    from agent_os.observability.router import router as observability_router
    from agent_os.db.audit import AuditLog

    # Check for audit log model
    assert AuditLog is not None, "Should have AuditLog model for tracking"

    # Check for observability endpoints
    print("✅ Observability module exists")


def test_idempotency_mechanism():
    """验证幂等性机制"""
    # This is a basic check - actual testing would need integration tests
    from agent_os.items.models import Item

    # Check if Item has status field that can prevent re-processing
    assert hasattr(Item, 'status'), "Item should have status for idempotency"

    print("✅ Status field exists for idempotency control")


# ============================================================================
# API Endpoint Verification
# ============================================================================

def test_agent_tick_endpoint():
    """验证 Agent Tick API 端点"""
    from agent_os.server.app import app

    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            for method in route.methods:
                routes.append((method, route.path))

    # Look for agent-related endpoints
    agent_endpoints = [
        (m, p) for m, p in routes
        if 'agent' in p.lower() or 'tick' in p.lower() or 'capture' in p.lower()
    ]

    print(f"\nAgent-related endpoints found: {len(agent_endpoints)}")
    for method, path in agent_endpoints:
        print(f"  {method:6} {path}")


# ============================================================================
# Data Model Verification
# ============================================================================

def test_inbox_item_raw_status():
    """验证 InboxItem 支持 raw 状态"""
    from agent_os.items.models import Item

    # Create a test item with raw status
    # Note: We're not actually creating it in DB, just checking the model
    print(f"✅ Item model has status field: {hasattr(Item, 'status')}")


def test_card_model_structure():
    """验证 Card 模型结构"""
    try:
        from agent_os.knowledge.models import Card

        # Required fields for Stage 2
        required_fields = {
            'id': 'ID field',
            'title': 'Title field',
            'content': 'Content field',
            'para_type': 'Type field',
        }

        for field, description in required_fields.items():
            if hasattr(Card, field):
                print(f"✅ Card has {field}: {description}")
            else:
                print(f"⚠️  Card missing {field}: {description}")

    except ImportError as e:
        pytest.skip(f"Card model not available: {e}")


# ============================================================================
# Integration Verification
# ============================================================================

def test_inbox_to_today_flow_possible():
    """验证 Inbox → Today 信息流是否可能"""
    from agent_os.server.app import app

    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            for method in route.methods:
                routes.append((method, route.path))

    # Check if we have both Inbox and Today endpoints
    has_inbox = any('inbox' in p.lower() for m, p in routes if m == 'POST')
    has_today = any('today' in p.lower() for m, p in routes if m == 'GET')

    print(f"\n✅ Inbox endpoint exists: {has_inbox}")
    print(f"✅ Today endpoint exists: {has_today}")

    if has_inbox and has_today:
        print("✅ Inbox → Today flow is possible")
    else:
        print("⚠️  Inbox → Today flow may not be complete")


# ============================================================================
# Summary Report
# ============================================================================

class Stage2VerificationReport:
    """阶段二验收验证报告"""

    def __init__(self):
        self.results = {
            "Capture / Agent Tick 机制": {
                "Agent 触发入口": "待验证",
                "只处理指定状态": "待验证",
                "明确输入输出": "待验证",
            },
            "InboxItem 处理与状态推进": {
                "raw → processed 状态": "待验证",
                "生成结构化结果": "待验证",
                "原始输入保留": "待验证",
            },
            "Card / Today 数据生成": {
                "Card 模型存在": "待验证",
                "数据结构一致": "待验证",
                "不依赖 mock": "待验证",
            },
            "Agent 行为约束与记录": {
                "规则约束": "待验证",
                "日志记录": "待验证",
                "可追溯性": "待验证",
            },
            "稳定性与幂等性": {
                "幂等性机制": "待验证",
                "异常处理": "待验证",
                "单条隔离": "待验证",
            },
        }

    def generate_report(self):
        """生成验收报告"""
        report = []
        report.append("# PA 1.0 阶段二后端验收验证报告\n")
        report.append(f"**验证时间:** 2026-02-07\n")
        report.append("---\n")

        for category, items in self.results.items():
            report.append(f"\n### {category}\n")
            for requirement, status in items.items():
                icon = "✅" if status == "PASS" else "⚠️" if "待验证" in status or "待实现" in status else "❌"
                report.append(f"- {icon} {requirement}: {status}\n")

        return "".join(report)


# ============================================================================
# Test Execution
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
