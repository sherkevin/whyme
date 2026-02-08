"""Quick test to check Card generation."""

import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from agent_os.items.models import Item, ItemStatus
from agent_os.auth.models import User
from agent_os.knowledge.models import Card
from agent_os.auth.security import create_access_token, get_password_hash
from tests.conftest import engine


async def main():
    """Test Card generation manually."""
    # Create engine and tables
    async with engine.begin() as conn:
        from agent_os.items.models import Workspace
        Workspace.__table__.create(conn, checkfirst=True)
        User.__table__.create(conn, checkfirst=True)
        Item.__table__.create(conn, checkfirst=True)
        Card.__table__.create(conn, checkfirst=True)

    # Create session
    from sqlalchemy.ext.asyncio import async_sessionmaker
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        # Create user
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            username="testuser",
            email="test@example.com",
            password_hash=get_password_hash("password123"),
            is_active=True
        )
        session.add(user)

        # Create workspace
        workspace_id = uuid.uuid4()
        from agent_os.items.models import Workspace
        workspace = Workspace(
            id=workspace_id,
            name="Test Workspace",
            owner_id=user.id
        )
        session.add(workspace)
        user.default_workspace_id = workspace_id

        await session.commit()
        await session.refresh(user)

        # Create a PROCESSED item
        item = Item(
            workspace_id=workspace_id,
            creator_id=user.id,
            type="note",
            title="Test Note",
            content="This is a test note about important concepts",
            status=ItemStatus.PROCESSED,
            item_type="note"
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)

        print(f"Created Item: {item.id}")

        # Generate Card
        from agent_os.knowledge.card_generator import generate_card_from_item

        card = await generate_card_from_item(session, item)
        print(f"Generated Card: {card.id}")
        print(f"  Title: {card.title}")
        print(f"  Type: {card.para_type}")
        print(f"  Tags: {card.tags}")

        # Query to verify
        result = await session.execute(select(Card).where(Card.source_inbox_item_id == item.id))
        found_card = result.scalar_one_or_none()

        if found_card:
            print(f"\n✅ Card successfully created and found in database!")
            print(f"   Card ID: {found_card.id}")
            print(f"   Source Item: {found_card.source_inbox_item_id}")
        else:
            print(f"\n❌ Card not found in database!")

    # Cleanup
    async with engine.begin() as conn:
        Card.__table__.drop(conn)
        Item.__table__.drop(conn)
        User.__table__.drop(conn)
        Workspace.__table__.drop(conn)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
