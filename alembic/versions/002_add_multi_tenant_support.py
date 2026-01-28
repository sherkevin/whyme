"""Add multi-tenant support with organizations.

Revision ID: 002_multi_tenant
Revises: 001_initial
Create Date: 2026-01-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '002_multi_tenant'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add multi-tenant support to existing schema."""

    # ========================================================================
    # Step 1: Create organizations table
    # ========================================================================
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('plan', sa.String(length=20), nullable=True, server_default='free'),
        sa.Column('max_users', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('max_storage_gb', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=True),
        # 独立数据库配置（用于企业客户）
        sa.Column('db_host', sa.String(length=255), nullable=True),
        sa.Column('db_port', sa.Integer(), nullable=True),
        sa.Column('db_name', sa.String(length=100), nullable=True),
        sa.Column('db_user', sa.String(length=100), nullable=True),
        sa.Column('db_password', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_organizations_id'), 'organizations', ['id'])
    op.create_index(op.f('ix_organizations_slug'), 'organizations', ['slug'], unique=True)
    op.create_index(op.f('ix_organizations_is_active'), 'organizations', ['is_active'])
    op.create_index('idx_organizations_plan_active', 'organizations', ['plan', 'is_active'])

    # ========================================================================
    # Step 2: Add organization_id to users table
    # ========================================================================
    # 添加列（允许 NULL，先添加数据后再设为 NOT NULL）
    op.add_column('users',
        sa.Column('organization_id', sa.Integer(), nullable=True)
    )
    op.add_column('users',
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true')
    )
    op.add_column('users',
        sa.Column('is_admin', sa.Boolean(), nullable=True, server_default='false')
    )

    # 创建外键
    op.create_foreign_key(
        'fk_users_organization',
        'users', 'organizations',
        ['organization_id'], ['id'],
        ondelete='CASCADE'
    )

    # 为现有用户创建默认组织
    op.execute("""
        INSERT INTO organizations (name, slug, plan, max_users, max_storage_gb, is_active)
        VALUES ('Default Organization', 'default', 'free', 1000, 100, true)
        RETURNING id;
    """)

    # 更新现有用户，将他们分配到默认组织
    op.execute("""
        UPDATE users
        SET organization_id = (SELECT id FROM organizations WHERE slug = 'default'),
            is_active = true,
            is_admin = false
        WHERE organization_id IS NULL;
    """)

    # 现在将 organization_id 设为 NOT NULL
    op.alter_column('users', 'organization_id', nullable=False)

    # 创建索引
    op.create_index('idx_users_org_active', 'users', ['organization_id', 'is_active'])

    # 删除旧的唯一约束（用户名和邮箱）
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')

    # 添加新的复合唯一约束（同一组织内唯一）
    op.create_unique_constraint('uq_org_username', 'users', ['organization_id', 'username'])
    op.create_unique_constraint('uq_org_email', 'users', ['organization_id', 'email'])

    # 添加普通索引用于查询
    op.create_index(op.f('ix_users_username'), 'users', ['username'])
    op.create_index(op.f('ix_users_email'), 'users', ['email'])

    # ========================================================================
    # Step 3: Add organization_id to inbox_items table
    # ========================================================================
    op.add_column('inbox_items',
        sa.Column('organization_id', sa.Integer(), nullable=True)
    )

    # 从 users 表复制 organization_id
    op.execute("""
        UPDATE inbox_items
        SET organization_id = (SELECT organization_id FROM users WHERE users.id = inbox_items.user_id)
        WHERE organization_id IS NULL;
    """)

    # 设为 NOT NULL
    op.alter_column('inbox_items', 'organization_id', nullable=False)

    # 创建外键和索引
    op.create_foreign_key(
        'fk_inbox_items_organization',
        'inbox_items', 'organizations',
        ['organization_id'], ['id'],
        ondelete='CASCADE'
    )

    op.create_index('idx_inbox_org_user', 'inbox_items', ['organization_id', 'user_id'])
    op.create_index('idx_inbox_org_status', 'inbox_items', ['organization_id', 'status'])

    # ========================================================================
    # Step 4: Add organization_id to cards table
    # ========================================================================
    op.add_column('cards',
        sa.Column('organization_id', sa.Integer(), nullable=True)
    )

    # 从 users 表复制 organization_id
    op.execute("""
        UPDATE cards
        SET organization_id = (SELECT organization_id FROM users WHERE users.id = cards.user_id)
        WHERE organization_id IS NULL;
    """)

    # 设为 NOT NULL
    op.alter_column('cards', 'organization_id', nullable=False)

    # 创建外键和索引
    op.create_foreign_key(
        'fk_cards_organization',
        'cards', 'organizations',
        ['organization_id'], ['id'],
        ondelete='CASCADE'
    )

    op.create_index('idx_card_org_user', 'cards', ['organization_id', 'user_id'])
    op.create_index('idx_card_org_type', 'cards', ['organization_id', 'para_type'])
    op.create_index('idx_card_org_created', 'cards', ['organization_id', 'created_at'])

    # ========================================================================
    # Step 5: Add organization_id to tasks table
    # ========================================================================
    op.add_column('tasks',
        sa.Column('organization_id', sa.Integer(), nullable=True)
    )

    # 从 users 表复制 organization_id
    op.execute("""
        UPDATE tasks
        SET organization_id = (SELECT organization_id FROM users WHERE users.id = tasks.user_id)
        WHERE organization_id IS NULL;
    """)

    # 设为 NOT NULL
    op.alter_column('tasks', 'organization_id', nullable=False)

    # 创建外键和索引
    op.create_foreign_key(
        'fk_tasks_organization',
        'tasks', 'organizations',
        ['organization_id'], ['id'],
        ondelete='CASCADE'
    )

    op.create_index('idx_task_org_user', 'tasks', ['organization_id', 'user_id'])
    op.create_index('idx_task_org_status', 'tasks', ['organization_id', 'status'])
    op.create_index('idx_task_org_status_date', 'tasks', ['organization_id', 'status', 'scheduled_date'])

    # ========================================================================
    # Step 6: Enable Row Level Security (RLS)
    # ========================================================================
    # 注意：RLS 需要 PostgreSQL 9.5+
    # 取消注释以下代码以启用 RLS

    # op.execute("ALTER TABLE cards ENABLE ROW LEVEL SECURITY;")
    # op.execute("ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;")
    # op.execute("ALTER TABLE inbox_items ENABLE ROW LEVEL SECURITY;")

    # # 创建策略：用户只能访问自己组织的数据
    # op.execute("""
    #     CREATE POLICY card_org_isolation ON cards
    #     FOR ALL
    #     TO public
    #     USING (
    #         organization_id = (
    #             SELECT organization_id FROM users WHERE id = current_setting('app.user_id')::integer
    #         )
    #     );
    # """)

    # op.execute("""
    #     CREATE POLICY task_org_isolation ON tasks
    #     FOR ALL
    #     TO public
    #     USING (
    #         organization_id = (
    #             SELECT organization_id FROM users WHERE id = current_setting('app.user_id')::integer
    #         )
    #     );
    # """)

    # op.execute("""
    #     CREATE POLICY inbox_org_isolation ON inbox_items
    #     FOR ALL
    #     TO public
    #     USING (
    #         organization_id = (
    #             SELECT organization_id FROM users WHERE id = current_setting('app.user_id')::integer
    #         )
    #     );
    # """)

    # # 强制执行 RLS
    # op.execute("ALTER TABLE cards FORCE ROW LEVEL SECURITY;")
    # op.execute("ALTER TABLE tasks FORCE ROW LEVEL SECURITY;")
    # op.execute("ALTER TABLE inbox_items FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    """Remove multi-tenant support."""

    # Step 1: Remove RLS policies (if enabled)
    # op.execute("DROP POLICY IF EXISTS card_org_isolation ON cards;")
    # op.execute("DROP POLICY IF EXISTS task_org_isolation ON tasks;")
    # op.execute("DROP POLICY IF EXISTS inbox_org_isolation ON inbox_items;")
    # op.execute("ALTER TABLE cards NO FORCE ROW LEVEL SECURITY;")
    # op.execute("ALTER TABLE tasks NO FORCE ROW LEVEL SECURITY;")
    # op.execute("ALTER TABLE inbox_items NO FORCE ROW LEVEL SECURITY;")
    # op.execute("ALTER TABLE cards DISABLE ROW LEVEL SECURITY;")
    # op.execute("ALTER TABLE tasks DISABLE ROW LEVEL SECURITY;")
    # op.execute("ALTER TABLE inbox_items DISABLE ROW LEVEL SECURITY;")

    # Step 2: Remove organization_id from tasks
    op.drop_index('idx_task_org_status_date', table_name='tasks')
    op.drop_index('idx_task_org_status', table_name='tasks')
    op.drop_index('idx_task_org_user', table_name='tasks')
    op.drop_constraint('fk_tasks_organization', 'tasks', type_='foreignkey')
    op.alter_column('tasks', 'organization_id', nullable=True)
    op.drop_column('tasks', 'organization_id')

    # Step 3: Remove organization_id from cards
    op.drop_index('idx_card_org_created', table_name='cards')
    op.drop_index('idx_card_org_type', table_name='cards')
    op.drop_index('idx_card_org_user', table_name='cards')
    op.drop_constraint('fk_cards_organization', 'cards', type_='foreignkey')
    op.alter_column('cards', 'organization_id', nullable=True)
    op.drop_column('cards', 'organization_id')

    # Step 4: Remove organization_id from inbox_items
    op.drop_index('idx_inbox_org_status', table_name='inbox_items')
    op.drop_index('idx_inbox_org_user', table_name='inbox_items')
    op.drop_constraint('fk_inbox_items_organization', 'inbox_items', type_='foreignkey')
    op.alter_column('inbox_items', 'organization_id', nullable=True)
    op.drop_column('inbox_items', 'organization_id')

    # Step 5: Restore users table to original state
    op.drop_index('idx_users_org_active', table_name='users')
    op.drop_constraint('uq_org_username', 'users', type_='unique')
    op.drop_constraint('uq_org_email', 'users', type_='unique')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.drop_column('users', 'is_admin')
    op.drop_column('users', 'is_active')
    op.drop_constraint('fk_users_organization', 'users', type_='foreignkey')
    op.alter_column('users', 'organization_id', nullable=True)
    op.drop_column('users', 'organization_id')

    # Step 6: Drop organizations table
    op.drop_index('idx_organizations_plan_active', table_name='organizations')
    op.drop_index(op.f('ix_organizations_is_active'), table_name='organizations')
    op.drop_index(op.f('ix_organizations_slug'), table_name='organizations')
    op.drop_index(op.f('ix_organizations_id'), table_name='organizations')
    op.drop_table('organizations')
