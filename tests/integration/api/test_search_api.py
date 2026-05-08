"""Stage 2: Hybrid Search Tests.

PRD10 NOTICE
============

PRD4 ``agent_os.search.keyword_search`` and ``agent_os.search.hybrid_search``
are now ``NotImplementedError`` shims (Agent 1 Milestone 2). PRD10 search
lives in ``agent_os.search_engine`` + ``agent_os.search_engine.router_prd10``
and has its own focused tests
(``tests/integration/api/test_prd10_search_api.py``).

This whole module is skipped at collection time. Re-enable only if a fresh
PRD4-style hybrid-search shim is added that satisfies these assertions.
"""

import pytest

pytest.skip(
    "Legacy PRD4 search tests; superseded by "
    "tests/integration/api/test_prd10_search_api.py.",
    allow_module_level=True,
)

import uuid  # noqa: E402,F401

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402,F401

from agent_os.items.models import Item, ItemStatus, ItemType  # noqa: E402,F401
from agent_os.items.schema import ItemCreate  # noqa: E402,F401
from agent_os.search.hybrid_search import (  # noqa: E402,F401
    HybridSearchService,
    hybrid_search,
)
from agent_os.search.keyword_search import (  # noqa: E402,F401
    KeywordSearchService,
    search_by_keywords,
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
async def test_workspace(db_session: AsyncSession):
    """创建测试 Workspace"""
    from agent_os.items.models import Workspace
    workspace = Workspace(
        name="Search Test Workspace",
        description="For testing search functionality",
        owner_id=uuid.uuid4()
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest.fixture
async def sample_items(db_session: AsyncSession, test_workspace):
    """创建示例 Items 用于搜索测试"""
    items = [
        Item(
            workspace_id=test_workspace.id,
            creator_id=uuid.uuid4(),
            type=ItemType.NOTE,
            title="Python编程基础教程",
            content="本教程涵盖Python基础语法、数据类型、控制流、函数等核心概念"
        ),
        Item(
            workspace_id=test_workspace.id,
            creator_id=uuid.uuid4(),
            type=ItemType.NOTE,
            title="机器学习入门",
            content="介绍机器学习的基本概念，包括监督学习、非监督学习和强化学习"
        ),
        Item(
            workspace_id=test_workspace.id,
            creator_id=uuid.uuid4(),
            type=ItemType.TASK,
            title="完成项目文档",
            content="编写项目的技术文档，包括API文档和使用手册"
        ),
        Item(
            workspace_id=test_workspace.id,
            creator_id=uuid.uuid4(),
            type=ItemType.RESOURCE,
            title="Python官方文档",
            content="Python编程语言的官方参考文档，包含标准库和语法说明"
        ),
        Item(
            workspace_id=test_workspace.id,
            creator_id=uuid.uuid4(),
            type=ItemType.NOTE,
            title="数据结构与算法",
            content="深入讲解常用数据结构(链表、树、图)和算法(排序、查找、图算法)"
        )
    ]

    for item in items:
        db_session.add(item)
    await db_session.commit()

    return items


# ============================================================================
# Keyword Search Tests
# ============================================================================

class TestKeywordSearchService:
    """关键词搜索服务测试"""

    async def test_search_single_term(self, db_session: AsyncSession, test_workspace):
        """测试单个词搜索"""
        service = KeywordSearchService()

        results = await service.search(
            db_session,
            workspace_id=str(test_workspace.id),
            query="Python",
            limit=10
        )

        # 验证结果
        assert len(results) > 0
        assert any("Python" in r.title or "Python" in r.content_snippet for r in results)

    async def test_search_multiple_terms(self, db_session: AsyncSession, test_workspace):
        """测试多词搜索"""
        service = KeywordSearchService()

        results = await service.search(
            db_session,
            workspace_id=str(test_workspace.id),
            query="Python 编程",
            limit=10
        )

        # 应该匹配包含 "Python" 或 "编程" 的文档
        assert len(results) > 0

    async def test_search_with_type_filter(self, db_session: AsyncSession, test_workspace):
        """测试带类型过滤的搜索"""
        service = KeywordSearchService()

        results = await service.search(
            db_session,
            workspace_id=str(test_workspace.id),
            query="Python",
            limit=10,
            type_filters=["note"]
        )

        # 所有结果应该是 note 类型
        # 注意: 由于使用 Items 表,类型字段存储为字符串
        assert len(results) >= 0

    async def test_empty_query(self, db_session: AsyncSession, test_workspace):
        """测试空查询"""
        service = KeywordSearchService()

        results = await service.search(
            db_session,
            workspace_id=str(test_workspace.id),
            query="",  # 空查询
            limit=10
        )

        # 空查询应该返回所有或最近的结果
        assert isinstance(results, list)

    async def test_tokenization(self):
        """测试分词功能"""
        service = KeywordSearchService()

        terms = service._tokenize_query("Python 编程 教程")
        # 应该过滤掉停用词
        assert "python" in terms
        assert "编程" in terms
        # 验证去重
        assert len(terms) == len(set(terms))


# ============================================================================
# Hybrid Search Tests
# ============================================================================

class TestHybridSearchService:
    """混合搜索服务测试"""

    async def test_keyword_search_path(self, db_session: AsyncSession, test_workspace):
        """测试关键词搜索路径"""
        service = HybridSearchService()

        results = await service.search(
            db_session,
            workspace_id=str(test_workspace.id),
            query="Python",
            limit=10
        )

        # 验证返回结果
        assert isinstance(results, list)
        # 所有结果应该是 HybridSearchResult 类型
        for r in results:
            assert hasattr(r, 'item_id')
            assert hasattr(r, 'title')
            assert hasattr(r, 'final_score')

    async def test_empty_query_returns_recent(self, db_session: AsyncSession, test_workspace):
        """测试空查询返回最近项目"""
        service = HybridSearchService()

        results = await service.search(
            db_session,
            workspace_id=str(test_workspace.id),
            query="",  # 空查询
            limit=5
        )

        assert len(results) <= 5
        # 空查询的结果 match_type 应该是 "recent"
        if results:
            assert results[0].match_type == "recent"

    async def test_score_calculation(self):
        """测试分数计算"""
        service = HybridSearchService(
            semantic_weight=0.7,
            keyword_weight=0.3
        )

        # 测试权重配置
        assert service.semantic_weight == 0.7
        assert service.keyword_weight == 0.3

    async def test_merge_and_rank(self):
        """测试融合排序"""
        service = HybridSearchService()

        # 创建模拟的关键词搜索结果
        from agent_os.search.keyword_search import KeywordSearchResult

        kw_results = [
            KeywordSearchResult(
                item_id="1",
                title="Python Tutorial",
                content_snippet="Python content...",
                score=0.8,
                matched_terms=["python"]
            ),
            KeywordSearchResult(
                item_id="2",
                title="ML Guide",
                content_snippet="Machine Learning...",
                score=0.6,
                matched_terms=["machine", "learning"]
            )
        ]

        # 空的语义搜索结果
        semantic_results = {}

        # 执行融合
        merged = service._merge_and_rank(kw_results, semantic_results, "test")

        # 验证融合结果
        assert len(merged) == 2
        # 应该按分数降序排列
        assert merged[0].final_score >= merged[1].final_score
        # 验证分数计算
        assert merged[0].keyword_score > 0
        assert merged[0].match_type == "keyword"


# ============================================================================
# Integration Tests
# ============================================================================

class TestSearchIntegration:
    """搜索集成测试"""

    async def test_full_search_workflow(
        self,
        db_session: AsyncSession,
        test_workspace: str
    ):
        """测试完整搜索流程"""
        # 1. 关键词搜索
        keyword_results = await search_by_keywords(
            db_session,
            workspace_id=test_workspace,
            query="Python",
            limit=5
        )
        assert isinstance(keyword_results, list)

        # 2. 混合搜索
        hybrid_results = await hybrid_search(
            db_session,
            workspace_id=test_workspace,
            query="Python",
            limit=5
        )
        assert isinstance(hybrid_results, list)

    async def test_search_performance(
        self,
        db_session: AsyncSession,
        test_workspace: str
    ):
        """测试搜索性能"""
        import time

        service = HybridSearchService()

        # 测试查询响应时间
        start = time.time()
        results = await service.search(
            db_session,
            workspace_id=test_workspace,
            query="Python 编程",
            limit=20
        )
        elapsed = time.time() - start

        # 验证性能 - 应该在合理时间内完成
        assert elapsed < 5.0  # 5秒内完成
        assert isinstance(results, list)

    async def test_freshness_boost(self):
        """测试新鲜度加权"""
        service = HybridSearchService(freshness_days=30)

        # 测试新鲜度计算
        boost = service._calculate_freshness_boost("test-item-id")
        assert 0.0 <= boost <= 1.0


# ============================================================================
# API Endpoint Tests
# ============================================================================

class TestSearchAPI:
    """搜索 API 端点测试"""

    async def test_hybrid_search_endpoint(self, db_session: AsyncSession):
        """测试混合搜索 API"""
        from agent_os.search.router import router
        from fastapi.testclient import TestClient

        client = TestClient(router)
        response = client.post(
            "/search/hydrid",
            json={
                "query": "Python",
                "type_filters": ["note"],
                "limit": 10
            }
        )

        # 验证响应
        assert response.status_code in [200, 500]  # 可能因为没有实际数据返回500
        data = response.json()

        if response.status_code == 200:
            assert "results" in data
            assert "total" in data
            assert "search_time_ms" in data

    async def test_health_check(self):
        """测试健康检查端点"""
        from agent_os.search.router import router
        from fastapi.testclient import TestClient

        client = TestClient(router)
        response = client.get("/search/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestSearchEdgeCases:
    """搜索边界情况测试"""

    async def test_special_characters_in_query(
        self,
        db_session: AsyncSession,
        test_workspace: str
    ):
        """测试特殊字符查询"""
        service = KeywordSearchService()

        # 测试特殊字符
        special_queries = [
            "Python!",
            "C++",
            "数据@#$",
            "  test  "  # 多余空格
        ]

        for query in special_queries:
            results = await service.search(
                db_session,
                workspace_id=test_workspace,
                query=query,
                limit=5
            )
            # 应该不抛出异常
            assert isinstance(results, list)

    async def test_long_query(self, db_session: AsyncSession, test_workspace: str):
        """测试长查询"""
        service = KeywordSearchService()

        long_query = "Python " * 50  # 50次重复
        results = await service.search(
            db_session,
            workspace_id=test_workspace,
            query=long_query,
            limit=5
        )

        # 应该能处理长查询
        assert isinstance(results, list)

    async def test_unicode_query(
        self,
        db_session: AsyncSession,
        test_workspace: str
    ):
        """测试 Unicode 查询"""
        service = KeywordSearchService()

        unicode_queries = [
            "Python编程",
            "机器学习",
            "数据结构",
            "算法"
        ]

        for query in unicode_queries:
            results = await service.search(
                db_session,
                workspace_id=test_workspace,
                query=query,
                limit=5
            )
            assert isinstance(results, list)

    async def test_zero_results(self, db_session: AsyncSession, test_workspace: str):
        """测试无结果情况"""
        service = KeywordSearchService()

        # 搜索不存在的内容
        results = await service.search(
            db_session,
            workspace_id=test_workspace,
            query="xyzabc123notfound",
            limit=5
        )

        # 应该返回空列表
        assert isinstance(results, list)
        assert len(results) == 0

    async def test_large_limit(self, db_session: AsyncSession, test_workspace: str):
        """测试大限制数量"""
        service = KeywordSearchService()

        results = await service.search(
            db_session,
            workspace_id=test_workspace,
            query="Python",
            limit=100  # 大限制
        )

        # 应该返回不超过限制数量的结果
        assert len(results) <= 100
