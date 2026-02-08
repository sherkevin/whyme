# 向量嵌入快速参考

## 🎯 一句话总结

**向量嵌入 = 文本转数字向量，让计算机理解语义相似度**

---

## 📦 核心组件

```
┌─────────────────────────────────────────────────┐
│            向量嵌入系统架构                      │
└─────────────────────────────────────────────────┘

输入文本
  ↓
┌──────────────────────────────────────┐
│  EmbeddingService                     │
│  - 模型: all-MiniLM-L6-v2            │
│  - 维度: 384                          │
│  - 语言: 100+                         │
└──────────────────────────────────────┘
  ↓
384维向量 [0.12, -0.34, 0.56, ..., 0.23]
  ↓
┌──────────────────────────────────────┐
│  PostgreSQL + pgvector               │
│  - 存储: cards.embedding             │
│  - 索引: HNSW (高性能)               │
│  - 搜索: 余弦相似度                  │
└──────────────────────────────────────┘
  ↓
语义搜索结果
```

---

## 🚀 快速开始

### 1. 生成嵌入

```python
from agent_os.knowledge.embeddings import EmbeddingService

# 单个文本
embedding = EmbeddingService.embed_text("Hello world")
# 返回: [0.12, -0.34, 0.56, ..., 0.23] (384 个数字)

# 批量文本
embeddings = EmbeddingService.embed_texts([
    "text 1",
    "text 2",
    "text 3"
])
```

### 2. 创建卡片（自动生成嵌入）

```python
from agent_os.knowledge.crud import create_card
from agent_os.knowledge.schema import CardCreate

card = await create_card(
    db,
    user_id=1,
    obj_in=CardCreate(
        title="Python 编程",
        content="Python 是一种高级编程语言",
        para_type="concept"
    )
)
# card.embedding 已自动生成
```

### 3. 语义搜索

```python
from agent_os.knowledge.vector_search import search_cards_by_text

results = await search_cards_by_text(
    db,
    user_id=1,
    query_text="如何学习编程",
    limit=10
)

for result in results:
    print(f"{result.title}: 相似度 {result.similarity:.2f}")
```

### 4. 计算相似度

```python
from agent_os.knowledge.embeddings import EmbeddingService

emb1 = EmbeddingService.embed_text("cat")
emb2 = EmbeddingService.embed_text("kitten")

similarity = EmbeddingService.compute_similarity(emb1, emb2)
print(f"相似度: {similarity:.2f}")  # 0.85
```

---

## 📊 API 端点

### 语义搜索

```
POST /api/v1/knowledge/cards/search

请求:
{
    "query": "python 异步编程",
    "limit": 10,
    "para_type": null,
    "similarity_threshold": 0.5
}

响应:
{
    "results": [
        {
            "card_id": 123,
            "title": "Python Asyncio 完全指南",
            "content": "使用 async/await...",
            "similarity": 0.87
        },
        ...
    ]
}
```

### 查找相似卡片

```
GET /api/v1/knowledge/cards/{card_id}/similar?limit=5

响应:
[
    {
        "card_id": 124,
        "title": "异步编程最佳实践",
        "similarity": 0.85
    },
    ...
]
```

---

## 🔧 配置

### 模型配置

```python
# src/agent_os/knowledge/embeddings.py

class EmbeddingService:
    _model_name = "sentence-transformers/all-MiniLM-L6-v2"
    _embedding_dim = 384  # 向量维度
```

### 数据库配置

```sql
-- 启用 pgvector
CREATE EXTENSION vector;

-- 创建向量索引
CREATE INDEX idx_cards_embedding_hnsw
ON cards USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

---

## 📈 性能指标

| 操作 | 时间 | 说明 |
|------|------|------|
| 生成嵌入 | 10-50ms | 单个文本 |
| 批量嵌入 | 5-20ms/文本 | 批处理更快 |
| 向量搜索 | 5-15ms | 1000 卡片 (有索引) |
| 相似度计算 | <1ms | Python 内存计算 |

---

## 🎓 使用场景

| 场景 | API | 说明 |
|------|-----|------|
| 语义搜索 | `POST /cards/search` | 理解查询意图 |
| 查找相似 | `GET /cards/{id}/similar` | 推荐相关内容 |
| RAG 检索 | `CardRAGProvider` | AI 知识注入 |
| 去重检测 | `compute_similarity()` | 识别重复内容 |

---

## 📚 相关文档

- [完整指南](./EMBEDDING_VECTOR_GUIDE.md) - 详细文档
- [数据库架构](./DATABASE_ARCHITECTURE.md) - 存储和索引
- [API 文档](../openapi.json) - REST API

---

**快速参考** - 2026-01-28
