"""Add knowledge card links and daily insights tables - PRD7 Module 1

Revision ID: 005_add_garden_models_prd7
Revises: 004_add_fulltext_search
Create Date: 2026-02-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '005_add_garden_models_prd7'
down_revision = '004_add_fulltext_search'
branch_labels = None
depends_on = None


def upgrade():
    # ===========================================
    # Create knowledge_card_links table
    # ===========================================
    op.create_table(
        'knowledge_card_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('to_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('relation_strength', sa.Float(), nullable=False, default=0.0),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        # Unique constraint: prevent duplicate edges of same type between same nodes
        sa.UniqueConstraint('from_id', 'to_id', 'type', name='uq_knowledge_card_link_from_to_type'),
        # Check constraints
        sa.CheckConstraint(
            "type IN ('related', 'support', 'contradict', 'reference')",
            name='ck_knowledge_card_link_type'
        ),
        sa.CheckConstraint(
            "relation_strength >= 0.0 AND relation_strength <= 1.0",
            name='ck_knowledge_card_link_strength_range'
        ),
    )

    # Create indexes for knowledge_card_links
    op.create_index('idx_kcl_workspace', 'knowledge_card_links', ['workspace_id'])
    op.create_index('idx_kcl_workspace_strength', 'knowledge_card_links', ['workspace_id', 'relation_strength'])
    op.create_index('idx_kcl_from_id', 'knowledge_card_links', ['from_id'])
    op.create_index('idx_kcl_to_id', 'knowledge_card_links', ['to_id'])

    # Add foreign key constraints
    op.create_foreign_key(
        'fk_kcl_workspace',
        'knowledge_card_links', 'workspaces',
        ['workspace_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_kcl_from',
        'knowledge_card_links', 'items',
        ['from_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_kcl_to',
        'knowledge_card_links', 'items',
        ['to_id'], ['id'],
        ondelete='CASCADE'
    )

    # ===========================================
    # Create daily_insights table
    # ===========================================
    op.create_table(
        'daily_insights',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, default='draft'),
        sa.Column('level', sa.Integer(), nullable=False, default=1),
        sa.Column('canonical_hash', sa.String(length=64), nullable=True),
        sa.Column('stability_score', sa.Float(), nullable=False, default=0.0),
        sa.Column('evidence_count', sa.Integer(), nullable=False, default=1),
        sa.Column('source_item_ids', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        # Check constraints
        sa.CheckConstraint(
            "status IN ('draft', 'candidate', 'stable', 'rejected')",
            name='ck_daily_insight_status'
        ),
        sa.CheckConstraint(
            "level IN (1, 2, 3)",
            name='ck_daily_insight_level'
        ),
        sa.CheckConstraint(
            "stability_score >= 0.0 AND stability_score <= 1.0",
            name='ck_daily_insight_stability_range'
        ),
        sa.CheckConstraint(
            "evidence_count >= 1",
            name='ck_daily_insight_evidence_min'
        ),
    )

    # Create indexes for daily_insights
    op.create_index('idx_di_workspace', 'daily_insights', ['workspace_id'])
    op.create_index('idx_di_workspace_user', 'daily_insights', ['workspace_id', 'user_id'])
    op.create_index('idx_di_user', 'daily_insights', ['user_id'])
    op.create_index('idx_di_status', 'daily_insights', ['status'])
    op.create_index('idx_di_created_at', 'daily_insights', ['created_at'])
    op.create_index('idx_di_canonical_hash', 'daily_insights', ['canonical_hash'])

    # Add foreign key constraints
    op.create_foreign_key(
        'fk_di_workspace',
        'daily_insights', 'workspaces',
        ['workspace_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_di_user',
        'daily_insights', 'users',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    # ===========================================
    # Drop daily_insights table
    # ===========================================
    op.drop_constraint('fk_di_user', 'daily_insights', type_='foreignkey')
    op.drop_constraint('fk_di_workspace', 'daily_insights', type_='foreignkey')

    op.drop_index('idx_di_canonical_hash', table_name='daily_insights')
    op.drop_index('idx_di_created_at', table_name='daily_insights')
    op.drop_index('idx_di_status', table_name='daily_insights')
    op.drop_index('idx_di_workspace_user', table_name='daily_insights')
    op.drop_index('idx_di_workspace', table_name='daily_insights')
    op.drop_index('idx_di_user', table_name='daily_insights')

    op.drop_table('daily_insights')

    # ===========================================
    # Drop knowledge_card_links table
    # ===========================================
    op.drop_constraint('fk_kcl_to', 'knowledge_card_links', type_='foreignkey')
    op.drop_constraint('fk_kcl_from', 'knowledge_card_links', type_='foreignkey')
    op.drop_constraint('fk_kcl_workspace', 'knowledge_card_links', type_='foreignkey')

    op.drop_index('idx_kcl_to_id', table_name='knowledge_card_links')
    op.drop_index('idx_kcl_from_id', table_name='knowledge_card_links')
    op.drop_index('idx_kcl_workspace_strength', table_name='knowledge_card_links')
    op.drop_index('idx_kcl_workspace', table_name='knowledge_card_links')

    op.drop_table('knowledge_card_links')
