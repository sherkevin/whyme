"""Create unified items table - PRD4 implementation

Revision ID: 003_prd4_items
Revises: 002_add_multi_tenant_support
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '003_prd4_items'
down_revision = '002_add_multi_tenant_support'
branch_labels = None
depends_on = None


def upgrade():
    # Create workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
    )
    op.create_index('idx_workspace_owner', 'workspaces', ['owner_id'])

    # Create areas table
    op.create_table(
        'areas',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['areas.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_areas_workspace', 'areas', ['workspace_id'])
    op.create_index('idx_areas_parent', 'areas', ['parent_id'])

    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('area_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('start_date', sa.DateTime, nullable=True),
        sa.Column('end_date', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['area_id'], ['areas.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_projects_workspace', 'projects', ['workspace_id'])
    op.create_index('idx_projects_area', 'projects', ['area_id'])

    # Create items table (unified content index)
    op.create_table(
        'items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('title', sa.Text, nullable=True),
        sa.Column('content', sa.Text, nullable=True),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float), nullable=True),  # Fallback if pgvector not available
        sa.Column('area_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source_type', sa.String(20), nullable=True),
        sa.Column('source_meta', postgresql.JSON, nullable=True, server_default='{}'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['area_id'], ['areas.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_items_workspace_user', 'items', ['workspace_id', 'creator_id'])
    op.create_index('idx_items_type', 'items', ['type'])
    op.create_index('idx_items_area', 'items', ['area_id'])
    op.create_index('idx_items_project', 'items', ['project_id'])
    op.create_index('idx_items_status', 'items', ['status'])

    # Try to create pgvector embedding column (if available)
    try:
        op.execute('ALTER TABLE items ADD COLUMN embedding_vector vector(1536)')
        op.execute('CREATE INDEX idx_items_embedding_vector ON items USING ivfflat (embedding_vector vector_cosine_ops)')
    except Exception:
        # pgvector not available, use ARRAY fallback
        pass

    # Create task_extensions table
    op.create_table(
        'task_extensions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('goal', sa.Text, nullable=True),
        sa.Column('constraints', sa.Text, nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=False, server_default='low'),
        sa.Column('execution_status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ondelete='CASCADE'),
        sa.CheckConstraint("risk_level IN ('low', 'medium', 'high')", name='check_risk_level'),
        sa.CheckConstraint("execution_status IN ('draft', 'planning', 'decision', 'executing', 'done')", name='check_execution_status'),
    )

    # Create decision_points table
    op.create_table(
        'decision_points',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('options', postgresql.JSON, nullable=False, server_default='[]'),
        sa.Column('user_choice', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['items.id'], ondelete='CASCADE'),
        sa.CheckConstraint("type IN ('selection', 'info', 'boundary')", name='check_decision_type'),
    )
    op.create_index('idx_decision_points_task', 'decision_points', ['task_id'])

    # Create ledger_events table
    op.create_table(
        'ledger_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('snapshot', postgresql.JSON, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['items.id'], ondelete='CASCADE'),
        sa.CheckConstraint("event_type IN ('agent_suggested', 'user_confirmed', 'deliverable_generated')", name='check_event_type'),
    )
    op.create_index('idx_ledger_events_task', 'ledger_events', ['task_id'])

    # Create graph_edges table
    op.create_table(
        'graph_edges',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('from_node_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('to_node_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('weight', sa.Float, nullable=False, server_default='0.0'),
        sa.Column('relation_type', sa.String(20), nullable=False),
        sa.Column('is_strong', sa.Boolean, nullable=False, server_default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['from_node_id'], ['items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_node_id'], ['items.id'], ondelete='CASCADE'),
        sa.CheckConstraint("relation_type IN ('topic', 'causal', 'supplement')", name='check_relation_type'),
        sa.CheckConstraint("weight >= 0 AND weight <= 1", name='check_weight_range'),
    )
    op.create_index('idx_graph_from', 'graph_edges', ['from_node_id'])
    op.create_index('idx_graph_to', 'graph_edges', ['to_node_id'])
    op.create_index('idx_graph_strong', 'graph_edges', ['is_strong'])
    op.create_index('unique_edge', 'graph_edges', ['from_node_id', 'to_node_id'], unique=True)


def downgrade():
    # Drop in reverse order
    op.drop_table('graph_edges')
    op.drop_table('ledger_events')
    op.drop_table('decision_points')
    op.drop_table('task_extensions')
    op.drop_table('items')
    op.drop_table('projects')
    op.drop_table('areas')
    op.drop_table('workspaces')
