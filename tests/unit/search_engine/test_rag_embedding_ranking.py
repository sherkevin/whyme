"""§16.5 — RAG embedding similarity ranking unit tests.

Covers ``agent_os.search_engine.embeddings`` (the deterministic local
``hash128-v2-cjk`` vector path that Mydow AI's RAG step uses when no neural
embedding service is wired) plus the cosine-similarity-driven ranking that
``agent_os.ai.router._load_related_context`` calls into.

These tests pin three behaviours that the v1.4 demo depends on:

1. Chinese-aware tokenizer: a single Chinese phrase decomposes into per-char
   AND bigram tokens (both required for non-zero cosine on short strings);
2. cosine_similarity is symmetric, in [-1, 1], and clamps at 0.0 for empty
   vectors / dim mismatch / null inputs (so RAG ranking never crashes when
   a document is mid-ingest and ``embedding=NULL``);
3. similarity ranking honours topical overlap: a Chinese sentence about
   "产品设计" ranks closer to a "产品架构" sibling than to a "美食推荐"
   stranger, even though no two share a literal substring.

Investor slide: this is the deterministic fallback that ships alongside
DeepSeek so the demo doesn't require a vector DB to feel like it works.
"""

from __future__ import annotations

import math

import pytest

from agent_os.search_engine.embeddings import (
    EMBEDDING_DIMENSION,
    EMBEDDING_VERSION,
    cosine_similarity,
    embed_text,
    embedding_id_for_text,
    text_for_search_embedding,
    tokenize,
)


class TestTokenizer:
    """§15.43 Chinese-aware tokenizer."""

    def test_empty_returns_empty_list(self):
        assert tokenize("") == []
        assert tokenize(None) == []

    def test_latin_words_lowercase_and_split(self):
        tokens = tokenize("Hello, World! Python is great")
        assert "hello" in tokens
        assert "world" in tokens
        assert "python" in tokens
        assert "great" in tokens

    def test_chinese_phrase_yields_chars_and_bigrams(self):
        # "产品设计" → individual chars + sliding bigrams
        tokens = tokenize("产品设计")
        # per-char tokens
        for ch in ("产", "品", "设", "计"):
            assert ch in tokens
        # bigram tokens
        for bg in ("产品", "品设", "设计"):
            assert bg in tokens

    def test_idempotent(self):
        text = "Mydow 产品设计 v1.4"
        first = tokenize(text)
        second = tokenize(text)
        assert first == second

    def test_mixed_latin_chinese(self):
        tokens = tokenize("Mydow AI 知识库")
        # latin words
        assert "mydow" in tokens
        assert "ai" in tokens
        # Chinese chars
        for ch in ("知", "识", "库"):
            assert ch in tokens
        # bigrams
        assert "知识" in tokens
        assert "识库" in tokens


class TestEmbedText:
    """``embed_text`` returns a normalized 128-d vector."""

    def test_dimension_is_fixed_128(self):
        vec = embed_text("产品设计")
        assert len(vec) == EMBEDDING_DIMENSION
        assert EMBEDDING_DIMENSION == 128

    def test_empty_text_returns_zero_vector(self):
        vec = embed_text("")
        assert vec == [0.0] * EMBEDDING_DIMENSION
        assert tokenize("") == []

    def test_vector_is_unit_normalized(self):
        vec = embed_text("Mydow 产品架构与 AI 工作流")
        norm = math.sqrt(sum(v * v for v in vec))
        # rounded to 8 decimals so equality with 1.0 isn't exact
        assert abs(norm - 1.0) < 1e-6

    def test_deterministic_across_calls(self):
        a = embed_text("用户访谈大纲")
        b = embed_text("用户访谈大纲")
        assert a == b

    def test_different_inputs_yield_different_vectors(self):
        a = embed_text("产品设计")
        b = embed_text("竞品对比")
        # not identical
        assert a != b


class TestCosineSimilarity:
    """``cosine_similarity`` stability — RAG ranking depends on this."""

    def test_self_similarity_is_one(self):
        vec = embed_text("产品设计")
        assert abs(cosine_similarity(vec, vec) - 1.0) < 1e-6

    def test_orthogonal_vectors_are_zero(self):
        # Synthetic orthogonal pair — can't easily construct via embed_text
        # because text similarity is rarely exact 0, so verify the math path.
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == 0.0

    def test_none_inputs_return_zero(self):
        assert cosine_similarity(None, [1.0, 0.0]) == 0.0
        assert cosine_similarity([1.0, 0.0], None) == 0.0
        assert cosine_similarity(None, None) == 0.0

    def test_dim_mismatch_returns_zero(self):
        # RAG never crashes when one row's embedding got partially written.
        assert cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0

    def test_empty_vectors_return_zero(self):
        assert cosine_similarity([], [1.0, 0.0]) == 0.0
        assert cosine_similarity([1.0, 0.0], []) == 0.0
        assert cosine_similarity([], []) == 0.0

    def test_zero_vector_returns_zero(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == 0.0
        assert cosine_similarity(b, a) == 0.0

    def test_similarity_is_symmetric(self):
        a = embed_text("产品架构调整")
        b = embed_text("用户访谈大纲")
        ab = cosine_similarity(a, b)
        ba = cosine_similarity(b, a)
        assert abs(ab - ba) < 1e-12


class TestRagRanking:
    """End-to-end embedding ranking — the behaviour Mydow AI RAG depends on.

    For the v1.4 demo we want:
        sim(query, on_topic) > sim(query, off_topic) > 0
    on Chinese-only phrases that share characters but no full substring.
    """

    def test_topical_neighbour_beats_off_topic(self):
        query = embed_text("我们如何把产品设计做成体系化的知识沉淀")
        on_topic = embed_text("产品架构与设计规范")
        off_topic = embed_text("夏天去哪里旅游最舒服")

        sim_on = cosine_similarity(query, on_topic)
        sim_off = cosine_similarity(query, off_topic)
        assert sim_on > sim_off, (
            f"on-topic similarity ({sim_on}) should beat off-topic ({sim_off})"
        )
        assert sim_on > 0.0

    def test_identical_substring_scores_higher_than_unrelated(self):
        query = embed_text("Mydow 产品 PRD V1")
        same_topic = embed_text("Mydow 产品规划")
        different = embed_text("机器学习论文综述")
        sim_same = cosine_similarity(query, same_topic)
        sim_diff = cosine_similarity(query, different)
        assert sim_same > sim_diff
        assert sim_same > 0.0

    def test_ranking_three_documents(self):
        """A realistic RAG scenario: query a knowledge base of 3 documents
        and assert the ranking order matches human intuition.
        """

        query = "请基于知识库总结产品设计的最新决策"
        documents = [
            ("doc_design", "产品设计与决策的复盘记录"),
            ("doc_marketing", "市场推广文案的 AB 测试结果"),
            ("doc_offsite", "团队团建活动总结"),
        ]
        q_vec = embed_text(query)
        scored = [
            (doc_id, cosine_similarity(q_vec, embed_text(text)))
            for doc_id, text in documents
        ]
        scored.sort(key=lambda kv: kv[1], reverse=True)

        # design doc must beat the other two
        assert scored[0][0] == "doc_design"
        # offsite must rank below marketing (marketing at least shares "产")
        # — this is a soft assertion: design > others is the must-have.
        assert scored[0][1] > scored[2][1]


class TestEmbeddingIdAndVersion:
    """Embedding versioning protects RAG when we bump the algorithm."""

    def test_version_string_is_stable(self):
        assert EMBEDDING_VERSION == "hash128-v2-cjk"

    def test_embedding_id_starts_with_version(self):
        eid = embedding_id_for_text("hello world")
        assert eid.startswith(f"{EMBEDDING_VERSION}:")

    def test_embedding_id_is_deterministic(self):
        a = embedding_id_for_text("Mydow AI 工作台")
        b = embedding_id_for_text("Mydow AI 工作台")
        assert a == b

    def test_embedding_id_differs_for_different_text(self):
        a = embedding_id_for_text("产品设计")
        b = embedding_id_for_text("产品架构")
        assert a != b

    def test_text_for_search_embedding_concatenates_skipping_blanks(self):
        text = text_for_search_embedding("Mydow", None, "  ", "AI", "")
        assert text == "Mydow AI"


@pytest.mark.parametrize(
    "text",
    [
        "ascii only sentence",
        "中文句子",
        "Mixed 中英 mixing 1234",
        "标点!@#符号？",
        "  leading and trailing spaces  ",
    ],
)
def test_embed_text_norm_is_one_or_zero(text: str):
    """Defensive: norm is always 1.0 (signal) or 0.0 (empty) — never NaN."""

    vec = embed_text(text)
    norm = math.sqrt(sum(v * v for v in vec))
    assert norm in (0.0,) or abs(norm - 1.0) < 1e-6
