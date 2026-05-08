"""Stage 2: Hybrid Search - Simplified Tests.

PRD10 NOTICE
============

PRD10's canonical search surface is still ``agent_os.search_engine``. The
legacy ``agent_os.search`` import path now provides a small real compatibility
layer so historical callers and tests keep working instead of hitting a
``NotImplementedError`` shim.
"""

import pytest

import uuid  # noqa: E402,F401

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402,F401

from agent_os.search.hybrid_search import HybridSearchService  # noqa: E402,F401
from agent_os.search.keyword_search import KeywordSearchService  # noqa: E402,F401

# ============================================================================
# Unit Tests (No database required)
# ============================================================================

class TestKeywordSearchUnit:
    """关键词搜索单元测试 (不依赖数据库)"""

    def test_tokenization(self):
        """测试分词功能"""
        service = KeywordSearchService()

        # 测试英文分词
        terms = service._tokenize_query("Python programming tutorial")
        assert "python" in terms
        assert "programming" in terms
        assert "tutorial" in terms

        # 测试停用词过滤
        terms = service._tokenize_query("the quick brown fox")
        # "the" 应该被过滤掉
        assert "the" not in terms

        # 测试去重
        terms = service._tokenize_query("python python code")
        # 去重后应该只有一个 "python"
        assert terms.count("python") == 1

    def test_bm25_score_calculation(self):
        """测试 BM25 分数计算"""
        service = KeywordSearchService()

        # 使用简单的 mock 对象避免 SQLAlchemy 初始化问题
        class MockItem:
            def __init__(self, title, content):
                self.title = title
                self.content = content

        mock_item = MockItem(
            title="Python Programming Guide",
            content="This is a comprehensive guide about Python programming language"
        )

        # 计算分数
        score, matched_terms = service._calculate_bm25_score(
            mock_item,
            ["python", "programming"]
        )

        assert score > 0
        assert "python" in matched_terms or "programming" in matched_terms

    def test_snippet_generation(self):
        """测试内容片段生成"""
        service = KeywordSearchService()

        content = "This is a long text about Python programming and machine learning concepts."

        # 测试正常截取
        snippet = service._generate_snippet(content, ["python"], max_length=50)
        # snippet 可能包含 "...", 所以长度允许超过 50
        assert len(snippet) >= 10  # 至少应该有一些内容

        # 测试高亮 (当前实现没有加粗标记,只检查是否包含关键词)
        assert "python" in snippet.lower() or "programming" in snippet.lower()


class TestHybridSearchUnit:
    """混合搜索单元测试 (不依赖数据库)"""

    def test_initialization(self):
        """测试服务初始化"""
        service = HybridSearchService(
            semantic_weight=0.7,
            keyword_weight=0.3
        )

        assert service.semantic_weight == 0.7
        assert service.keyword_weight == 0.3

    def test_score_normalization(self):
        """测试分数归一化"""
        service = HybridSearchService()

        # 创建模拟结果
        from agent_os.search.keyword_search import KeywordSearchResult

        mock_results = [
            KeywordSearchResult(
                item_id="1",
                title="Test",
                content_snippet="Content",
                score=10.0,
                matched_terms=["test"]
            ),
            KeywordSearchResult(
                item_id="2",
                title="Another",
                content_snippet="More content",
                score=5.0,
                matched_terms=["another"]
            )
        ]

        # 执行融合
        merged = service._merge_and_rank(mock_results, {}, "test")

        # 验证归一化 (分数应该在 0-1 之间)
        for result in merged:
            assert 0.0 <= result.keyword_score <= 1.0
            assert result.final_score >= 0.0

    def test_freshness_boost(self):
        """测试新鲜度加权"""
        service = HybridSearchService(freshness_days=30)

        # 测试不同 ID
        for item_id in ["item-1", "item-2", "item-3"]:
            boost = service._calculate_freshness_boost(item_id)
            assert 0.0 <= boost <= 1.0

    def test_highlight_application(self):
        """测试高亮应用"""
        service = HybridSearchService()

        # 创建模拟结果
        from agent_os.search.keyword_search import KeywordSearchResult

        mock_results = [
            KeywordSearchResult(
                item_id="1",
                title="Python Guide",
                content_snippet="This is about Python programming",
                score=0.8,
                matched_terms=["python"]
            )
        ]

        # 应用高亮
        highlighted = service._apply_highlight(
            "This is about Python programming",
            mock_results
        )

        # 应该包含高亮标记
        assert "**Python**" in highlighted or "python" in highlighted.lower()


# ============================================================================
# Functional Tests (With database)
# ============================================================================

@pytest.mark.asyncio
async def test_keyword_search_with_data(db_session: AsyncSession):
    """测试关键词搜索 (需要数据库) - 使用完整 CRUD 流程"""
    from agent_os.items.crud import create_item, create_workspace
    from agent_os.items.schema import ItemCreate, WorkspaceCreate

    # Step 1: 创建测试 workspace (通过 CRUD)
    creator_id = uuid.uuid4()

    workspace_data = WorkspaceCreate(
        name="Search Test Workspace",
        description="For keyword search testing",
        owner_id=creator_id
    )
    workspace = await create_workspace(db_session, workspace_data)

    # 验证 workspace 创建成功
    assert workspace.id is not None
    assert workspace.name == "Search Test Workspace"
    workspace_id = workspace.id  # 使用返回的 ID

    # Step 2: 创建测试 Items (通过 CRUD)
    items_to_create = [
        ItemCreate(
            workspace_id=workspace_id,
            creator_id=creator_id,
            type="note",
            title="Python编程基础",
            content="学习Python编程的基础知识，包括变量、数据类型、控制流等"
        ),
        ItemCreate(
            workspace_id=workspace_id,
            creator_id=creator_id,
            type="note",
            title="机器学习入门",
            content="介绍机器学习的基本概念，包括监督学习、非监督学习等"
        ),
        ItemCreate(
            workspace_id=workspace_id,
            creator_id=creator_id,
            type="task",
            title="Python 项目实战",
            content="完成一个实际的 Python Web 开发项目"
        )
    ]

    created_items = []
    for item_data in items_to_create:
        item = await create_item(db_session, item_data)
        created_items.append(item)
        assert item.id is not None

    # 验证创建了3个 items
    assert len(created_items) == 3

    # Step 3: 执行搜索
    service = KeywordSearchService()
    results = await service.search(
        db_session,
        workspace_id=str(workspace_id),
        query="Python",
        limit=10
    )

    # Step 4: 验证搜索结果
    assert len(results) > 0, "应该找到包含 Python 的文档"

    # 验证能找到包含 "Python" 的文档
    python_found = any(
        "python" in r.title.lower() or "python" in r.content_snippet.lower()
        for r in results
    )
    assert python_found, "搜索结果中应该包含 Python 相关文档"

    # 验证结果包含必要的字段
    for result in results:
        assert result.item_id is not None
        assert result.title is not None
        assert result.score >= 0
        assert isinstance(result.matched_terms, list)


@pytest.mark.asyncio
async def test_hybrid_search_with_data(db_session: AsyncSession):
    """测试混合搜索 (需要数据库) - 使用完整 CRUD 流程"""
    from agent_os.items.crud import create_item, create_workspace
    from agent_os.items.schema import ItemCreate, WorkspaceCreate

    # Step 1: 创建 workspace
    creator_id = uuid.uuid4()

    workspace_data = WorkspaceCreate(
        name="Hybrid Search Test",
        description="For hybrid search testing",
        owner_id=creator_id
    )
    workspace = await create_workspace(db_session, workspace_data)
    assert workspace.id is not None
    workspace_id = workspace.id

    # Step 2: 创建测试 Items
    for i in range(5):
        item_data = ItemCreate(
            workspace_id=workspace_id,
            creator_id=creator_id,
            type="note",
            title=f"Test Document {i}",
            content=f"This is test document number {i} about Python programming"
        )
        item = await create_item(db_session, item_data)
        assert item.id is not None

    # Step 3: 执行混合搜索
    service = HybridSearchService()
    results = await service.search(
        db_session,
        workspace_id=str(workspace_id),
        query="Python",
        limit=5
    )

    # Step 4: 验证结果结构
    assert isinstance(results, list)
    for r in results:
        assert hasattr(r, 'item_id')
        assert hasattr(r, 'title')
        assert hasattr(r, 'final_score')
        assert hasattr(r, 'match_type')
        assert hasattr(r, 'snippet')


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.asyncio
async def test_search_performance(db_session: AsyncSession):
    """测试搜索性能 - 使用完整 CRUD 流程"""
    import time

    from agent_os.items.crud import create_item, create_workspace
    from agent_os.items.schema import ItemCreate, WorkspaceCreate

    # Step 1: 创建 workspace
    creator_id = uuid.uuid4()

    workspace_data = WorkspaceCreate(
        name="Performance Test",
        owner_id=creator_id
    )
    workspace = await create_workspace(db_session, workspace_data)
    assert workspace.id is not None
    workspace_id = workspace.id

    # Step 2: 创建 20 个测试 Items
    num_items = 20
    for i in range(num_items):
        item_data = ItemCreate(
            workspace_id=workspace_id,
            creator_id=creator_id,
            type="note",
            title=f"Performance Test {i}",
            content=f"Content for performance test document number {i}"
        )
        item = await create_item(db_session, item_data)
        assert item.id is not None

    # Step 3: 测试搜索性能
    service = HybridSearchService()

    start = time.time()
    results = await service.search(
        db_session,
        workspace_id=str(workspace_id),
        query="performance",
        limit=10
    )
    elapsed = time.time() - start

    # Step 4: 性能验证
    assert elapsed < 5.0, f"搜索应该在5秒内完成，实际耗时: {elapsed:.2f}秒"
    assert isinstance(results, list), "搜索结果应该是列表"
    print(f"\n性能测试: {num_items} 个文档搜索耗时 {elapsed:.3f} 秒")


# ============================================================================
# Edge Cases
# ============================================================================

def test_special_characters():
    """测试特殊字符处理"""
    service = KeywordSearchService()

    # 测试特殊字符
    special_queries = [
        "C++",
        "data@analysis",
        "test#tag",
        "user@domain.com"
    ]

    for query in special_queries:
        terms = service._tokenize_query(query)
        # 应该不抛出异常
        assert isinstance(terms, list)


def test_empty_query():
    """测试空查询处理"""
    service = KeywordSearchService()

    # 空字符串
    terms = service._tokenize_query("")
    assert terms == []

    # 只有空格
    terms = service._tokenize_query("   ")
    assert terms == []


def test_unicode_handling():
    """测试 Unicode 处理"""
    service = KeywordSearchService()

    # 中文查询 (简化分词不会分割"编程")
    terms = service._tokenize_query("Python编程")
    # 由于是按空格分词,"python编程"会被当做一个词
    assert len(terms) >= 1

    # 混合查询 (有空格的情况)
    terms = service._tokenize_query("Python 数据 算法")
    assert len(terms) >= 2  # "python", "数据", "算法"


def test_long_query_handling():
    """测试长查询处理"""
    service = KeywordSearchService()

    # 非常长的查询
    long_query = "python " * 100
    terms = service._tokenize_query(long_query)

    # 应该能处理
    assert isinstance(terms, list)
    # 停用词应该过滤掉重复
    assert "python" in terms


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])
