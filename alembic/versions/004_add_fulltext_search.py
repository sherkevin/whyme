"""Add full-text search support for hybrid search - Stage 2

Revision ID: 004_add_fulltext_search
Revises: 003_prd4_items
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_fulltext_search'
down_revision = '003_prd4_items'
branch_labels = None
depends_on = None


def upgrade():
    # 为 items 表添加 tsvector 列
    # 注意: SQLite 不支持 tsvector,使用 JSON 存储预处理结果
    # PostgreSQL 可以在后续升级时使用真正的 tsvector

    # 添加全文搜索支持 (SQLite兼容方案)
    with op.batch_alter_table('items') as batch_op:
        # 添加用于全文搜索的预处理列
        batch_op.add_column(
            sa.Column('title_tsv', sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column('content_tsv', sa.Text(), nullable=True)
        )

    # 为 items 表添加索引 (用于 LIKE 搜索,SQLite 兼容)
    # PostgreSQL 可以升级到 GIN 索引
    op.create_index(
        'idx_items_title',
        'items',
        ['title']
    )
    op.create_index(
        'idx_items_content',
        'items',
        ['content']
    )

    # 更新现有数据的预处理列
    op.execute("""
        UPDATE items
        SET title_tsv = lower(title),
            content_tsv = lower(content)
        WHERE title IS NOT NULL OR content IS NOT NULL
    """)


def downgrade():
    # 移除索引
    op.drop_index('idx_items_content', table_name='items')
    op.drop_index('idx_items_title', table_name='items')

    # 移除列
    with op.batch_alter_table('items') as batch_op:
        batch_op.drop_column('content_tsv')
        batch_op.drop_column('title_tsv')
