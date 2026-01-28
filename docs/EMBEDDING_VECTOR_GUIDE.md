# 向量嵌入完全指南

**最后更新**: 2026-01-28
**版本**: v1.0

---

## 📚 什么是向量嵌入？

向量嵌入（Vector Embedding）是将文本转换为数字向量的技术，使计算机能够理解文本的**语义**而不仅仅是关键词匹配。

### 简单解释

```
传统关键词搜索:
  查询: "dog"
  匹配: 包含 "dog" 的文档 ✅
  不匹配: "puppy", "canine" ❌

向量语义搜索:
  查询: "dog"
  匹配: "dog", "puppy", "canine", "pet" ✅
  原理: 这些词在语义空间中距离相近
```

### 工作原理

```
文本 → 嵌入模型 → 384维向量
"The cat sits" → [0.12, -0.34, 0.56, ..., 0.23]
                      └───── 384个数字 ─────┘

向量相似度计算:
相似度 = cos(向量1, 向量2)
范围: -1 到 1 (通常 0 到 1)
越高 = 越相似
```

---

## 🎯 AgentOS 中的向量嵌入

### 1. 嵌入模型配置

**使用的模型**: `sentence-transformers/all-MiniLM-L6-v2`

```python
# src/agent_os/knowledge/embeddings.py

class EmbeddingService:
    _model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    _embedding_dim: int = 384  # 向量维度
```

**模型特点**:
- 🚀 **快速**: 小型模型，推理速度快
- 📦 **轻量**: 模型大小约 80MB
- 🎯 **准确**: 对英文和多语言支持良好
- 💰 **免费**: 开源，无需 API 费用

**性能**:
- 嵌入维度: 384
- 平均推理时间: ~10-50ms/文本
- 支持语言: 100+ 种语言

### 2. 向量存储

**存储位置**: PostgreSQL + pgvector 扩展

```sql
-- cards 表
CREATE TABLE cards (
    id INTEGER PRIMARY KEY,
    organization_id INTEGER,
    user_id INTEGER,
    title VARCHAR(200),
    content TEXT,
    embedding VECTOR(384),  -- ← 向量嵌入存储在这里
    ...
);

-- 向量索引（高性能搜索）
CREATE INDEX idx_cards_embedding_hnsw
ON cards USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

**为什么用 PostgreSQL**:
- ✅ 事务支持（ACID）
- ✅ 向量索引（HNSW）- 10x 搜索性能提升
- ✅ 无需额外的向量数据库
- ✅ 数据一致性保证

---

## 🔧 如何获得向量嵌入

### 方法 1: 创建卡片时自动生成

```python
# 当创建 Card 时，自动生成向量嵌入

from agent_os.knowledge.crud import create_card
from agent_os.knowledge.schema import CardCreate

# 创建卡片（嵌入自动生成）
card_in = CardCreate(
    title="Python 异步编程",
    content="使用 async/await 语法编写异步代码...",
    para_type="concept",
    tags=["python", "async"]
)

# CRUD 层自动调用 EmbeddingService
card = await create_card(db, user_id=1, obj_in=card_in)

# card.embedding 现在包含 384 维向量
print(f"Embedding dimension: {len(card.embedding)}")  # 384
```

**内部流程**:
```
1. 用户提交卡片数据
   ↓
2. create_card() 被调用
   ↓
3. generate_embedding_for_card() 生成嵌入
   - 组合: title + content
   - 调用: EmbeddingService.embed_text()
   - 返回: [0.12, -0.34, ..., 0.23]
   ↓
4. 嵌入存储到 cards.embedding
   ↓
5. 返回创建的卡片
```

### 方法 2: 手动生成嵌入

```python
from agent_os.knowledge.embeddings import EmbeddingService

# 生成单个文本的嵌入
text = "Machine learning is a subset of artificial intelligence"
embedding = EmbeddingService.embed_text(text)

print(f"Dimension: {len(embedding)}")  # 384
print(f"First 5 values: {embedding[:5]}")  # [0.12, -0.34, 0.56, -0.12, 0.78]
```

### 方法 3: 批量生成嵌入

```python
from agent_os.knowledge.embeddings import EmbeddingService

texts = [
    "Python programming language",
    "JavaScript web development",
    "Machine learning algorithms"
]

# 批量生成（更高效）
embeddings = EmbeddingService.embed_texts(texts)

for i, emb in enumerate(embeddings):
    print(f"Text {i}: {len(emb)} dimensions")
```

### 方法 4: 为收件项生成嵌入

```python
from agent_os.knowledge.embeddings import generate_embedding_for_inbox
from agent_os.knowledge.crud import create_inbox_item

# 创建收件项（自动生成嵌入）
inbox_in = InboxItemCreate(
    content="IDEA: Build a task management app with AI features",
    source="manual"
)

item = await create_inbox_item(db, user_id=1, obj_in=inbox_in)
# item.embedding 已自动生成
```

---

## 🔍 向量搜索使用场景

### 场景 1: 语义搜索卡片

**API 端点**: `POST /api/v1/knowledge/cards/search`

```python
import requests

# 搜索与 "python 异步编程" 语义相似的卡片
response = requests.post(
    "http://localhost:8000/api/v1/knowledge/cards/search",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "query": "python async programming",  # 查询文本
        "limit": 10,                           # 返回结果数
        "para_type": None,                     # 可选：过滤卡片类型
        "similarity_threshold": 0.5            # 最低相似度
    }
)

results = response.json()

for item in results["results"]:
    print(f"Title: {item['title']}")
    print(f"Similarity: {item['similarity']:.2f}")  # 0.85
    print(f"Content: {item['content'][:100]}...")
    print()
```

**搜索原理**:
```
1. 查询文本 "python async programming"
   ↓
2. 生成查询嵌入: [0.23, -0.45, 0.67, ...]
   ↓
3. 数据库计算余弦相似度
   SELECT 1 - (embedding <=> query_embedding) AS similarity
   ↓
4. 返回相似度最高的卡片
```

### 场景 2: 查找相似卡片

**API 端点**: `GET /api/v1/knowledge/cards/{card_id}/similar`

```python
# 查找与某个卡片相似的其他卡片
card_id = 123

response = requests.get(
    f"http://localhost:8000/api/v1/knowledge/cards/{card_id}/similar",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    params={"limit": 5}
)

similar_cards = response.json()

print(f"Found {len(similar_cards)} similar cards:")
for card in similar_cards:
    print(f"- {card['title']} (similarity: {card['similarity']:.2f})")
```

**使用场景**:
- 📚 知识关联：找到相关的知识点
- 🔄 去重检测：识别重复内容
- 💡 灵感推荐：推荐相似知识

### 场景 3: RAG（检索增强生成）

```python
from agent_os.knowledge.rag_provider import CardRAGProvider

# 初始化 RAG 提供器
rag = CardRAGProvider(db)

# 根据任务检索相关知识
task_description = "需要实现用户认证功能"

# 检索相关的知识卡片
context = await rag.get_context_for_task(
    task_id=None,
    user_id=current_user.id,
    max_cards=5,
    query_text=task_description
)

# context 包含最相关的知识卡片
print("Retrieved context:")
for card in context["cards"]:
    print(f"- {card['title']}: {card['content'][:100]}...")
```

**RAG 工作流程**:
```
1. 用户提问/任务
   ↓
2. 向量化查询
   ↓
3. 检索相关知识（向量搜索）
   ↓
4. 将知识注入到 AI 提示词
   ↓
5. AI 生成更准确的回答
```

---

## 📊 向量相似度计算

### 余弦相似度

```python
from agent_os.knowledge.embeddings import EmbeddingService

# 两个嵌入向量
embedding1 = EmbeddingService.embed_text("dog")
embedding2 = EmbeddingService.embed_text("puppy")

# 计算相似度
similarity = EmbeddingService.compute_similarity(embedding1, embedding2)

print(f"Similarity: {similarity:.2f}")  # 0.87 (非常相似)
```

### 相似度范围解释

```
相似度范围: 0.0 到 1.0

1.0  → 完全相同（同一个文本）
0.8-0.9 → 非常相似（同义词，相同概念）
0.6-0.8 → 相似（相关概念）
0.4-0.6 → 部分相关
0.2-0.4 → 弱相关
0.0-0.2 → 基本不相关
```

### 实际示例

```python
# 测试不同文本的相似度
examples = [
    ("cat", "cat"),           # 1.0 (完全相同)
    ("cat", "kitten"),        # 0.85 (非常相似)
    ("cat", "dog"),           # 0.65 (相关 - 都是动物)
    ("cat", "car"),           # 0.15 (不相关)
    ("cat", "python"),        # 0.08 (完全不相关)
]

for text1, text2 in examples:
    emb1 = EmbeddingService.embed_text(text1)
    emb2 = EmbeddingService.embed_text(text2)
    sim = EmbeddingService.compute_similarity(emb1, emb2)
    print(f"'{text1}' vs '{text2}': {sim:.2f}")
```

---

## 🚀 性能优化

### 1. 向量索引

```sql
-- HNSW 索引（高性能）
CREATE INDEX idx_cards_embedding_hnsw
ON cards USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 性能对比:
-- 无索引: 1000 卡片 ~5秒
-- HNSW:   1000 卡片 ~10ms (500x 提升)
```

### 2. 批量处理

```python
# ❌ 慢：循环生成
for text in texts:
    embedding = EmbeddingService.embed_text(text)  # 每次加载模型

# ✅ 快：批量生成
embeddings = EmbeddingService.embed_texts(texts)  # 一次性处理
```

### 3. 缓存嵌入

```python
# 缓存已生成的嵌入
cache = {}

def get_embedding(text):
    if text not in cache:
        cache[text] = EmbeddingService.embed_text(text)
    return cache[text]
```

---

## 🔧 配置和安装

### 1. 安装依赖

```bash
# 安装 sentence-transformers
pip install sentence-transformers

# 安装 pgvector (PostgreSQL 扩展)
# Ubuntu/Debian:
git clone --branch v0.5.0 https://github.com/pgvector/pgvector.git
cd pgvector
make
make install

# 或使用 Docker:
# 在 Dockerfile 中:
# RUN git clone --branch v0.5.0 https://github.com/pgvector/pgvector.git /tmp/pgvector
# RUN cd /tmp/pgvector && make && make install
```

### 2. 启用 pgvector

```sql
-- 在 PostgreSQL 中
CREATE EXTENSION vector;

-- 验证安装
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### 3. 环境变量配置

```bash
# .env
# PostgreSQL 数据库 URL（必须支持 pgvector）
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname

# 可选：OpenAI API (如果想用 OpenAI 嵌入)
# OPENAI_API_KEY=sk-...
# EMBEDDING_MODEL=text-embedding-3-small
```

---

## 📈 使用示例

### 完整工作流

```python
from sqlalchemy.ext.asyncio import AsyncSession
from agent_os.db.base import AsyncSessionLocal
from agent_os.knowledge.embeddings import EmbeddingService
from agent_os.knowledge.crud import create_card
from agent_os.knowledge.schema import CardCreate
from agent_os.knowledge.vector_search import search_cards_by_text

async def main():
    # 1. 创建数据库会话
    async with AsyncSessionLocal() as db:
        # 2. 创建卡片（自动生成嵌入）
        card = await create_card(
            db,
            user_id=1,
            obj_in=CardCreate(
                title="Python 异步编程最佳实践",
                content="使用 async/await 编写高效的异步代码...",
                para_type="concept",
                tags=["python", "async"]
            )
        )

        print(f"Created card with embedding: {len(card.embedding)} dimensions")

        # 3. 语义搜索
        results = await search_cards_by_text(
            db,
            user_id=1,
            query_text="如何编写异步代码",
            limit=5
        )

        print(f"\nFound {len(results)} similar cards:")
        for result in results:
            print(f"- {result.title} (similarity: {result.similarity:.2f})")
```

### Python 交互式示例

```python
# 在 Python shell 中测试
>>> from agent_os.knowledge.embeddings import EmbeddingService

# 生成嵌入
>>> emb = EmbeddingService.embed_text("Hello world")
>>> len(emb)
384

# 查看前 10 个值
>>> emb[:10]
[0.123, -0.456, 0.789, -0.234, 0.567, -0.891, 0.345, -0.678, 0.901, -0.123]

# 计算相似度
>>> sim = EmbeddingService.compute_similarity(emb1, emb2)
>>> print(f"Similarity: {sim:.2f}")
0.87
```

---

## 🎓 最佳实践

### ✅ DO

1. **组合标题和内容**: 为卡片生成嵌入时，同时使用标题和内容
   ```python
   combined_text = f"{title}. {content}"
   ```

2. **使用相似度阈值**: 过滤不相关的结果
   ```python
   similarity_threshold=0.5  # 只返回相似度 > 0.5 的结果
   ```

3. **批量处理**: 生成多个嵌入时使用批量接口
   ```python
   embeddings = EmbeddingService.embed_texts(texts)
   ```

4. **缓存结果**: 缓存频繁查询的嵌入
   ```python
   cache = {}  # 或使用 Redis
   ```

### ❌ DON'T

1. **不要对空文本生成嵌入**
   ```python
   if not text or not text.strip():
       return None  # 避免错误
   ```

2. **不要忽略维度检查**
   ```python
   if len(embedding) != 384:
       raise ValueError("Invalid embedding dimension")
   ```

3. **不要在生产环境使用 echo=True**
   ```python
   engine = create_async_engine(DATABASE_URL, echo=False)  # 关闭 SQL 日志
   ```

---

## 🔗 相关文档

- [数据库架构](./DATABASE_ARCHITECTURE.md) - 向量存储和索引
- [API 文档](../openapi.json) - REST API 端点
- [知识管理](./01-prd/prd2-knowledge-management.md) - 产品需求

---

**维护者**: AgentOS 开发团队
**最后更新**: 2026-01-28
**文档版本**: v1.0
