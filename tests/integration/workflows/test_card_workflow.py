"""Integration test for Card generation."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.models import User
from agent_os.auth.security import get_password_hash
from agent_os.items.models import Item, ItemStatus, Workspace
from agent_os.knowledge.models import Card


@pytest.fixture
async def card_test_setup(db_session: AsyncSession):
    """Create user and workspace for Card generation testing."""
    import time
    # Create user with unique username
    timestamp = int(time.time() * 1000)
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        username=f"cardtest_user_{timestamp}",
        email=f"cardtest_{timestamp}@example.com",
        password_hash=get_password_hash("password123"),
        is_active=True
    )
    db_session.add(user)

    # Create workspace
    workspace_id = uuid.uuid4()
    workspace = Workspace(
        id=workspace_id,
        name="Card Test Workspace",
        owner_id=user.id
    )
    db_session.add(workspace)

    user.default_workspace_id = workspace_id
    await db_session.commit()
    await db_session.refresh(user)

    return {"user": user, "workspace": workspace}


@pytest.mark.asyncio
async def test_card_generation_from_item(
    db_session: AsyncSession,
    card_test_setup
):
    """Test Card generation from a PROCESSED Item."""
    workspace = card_test_setup["workspace"]
    user = card_test_setup["user"]

    # Create a RAW item and process it (to set item_type in metadata)
    item = Item(
        workspace_id=workspace.id,
        creator_id=user.id,
        type="note",
        title="Important Concept",
        content="This is a note about an important system design concept",
        status=ItemStatus.RAW
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    # Process the item using the agent
    from agent_os.agent.processor import process_inbox_item

    result = await process_inbox_item(db_session, str(item.id), force_reprocess=False)
    assert result.success is True

    # Refresh to get updated data
    await db_session.refresh(item)

    print(f"\n✅ Created and processed Item: {item.id}")
    print(f"   Status: {item.status}")
    print(f"   Type: {item.type}")
    print(f"   Metadata: {item.source_meta}")

    # Verify Card was created during processing
    assert "card_id" in item.source_meta
    assert item.source_meta["card_generation"] == "success"

    card_id_str = item.source_meta["card_id"]
    print(f"✅ Card ID from processing: {card_id_str}")

    # Query to verify Card was persisted
    result = await db_session.execute(
        select(Card).where(Card.source_inbox_item_id == item.id)
    )
    cards = result.scalars().all()

    assert len(cards) == 1, f"Expected 1 card, found {len(cards)}"
    card = cards[0]

    print("✅ Card successfully persisted in database!")
    print(f"   Card ID: {card.id}")
    print(f"   Title: {card.title}")
    print(f"   Type: {card.para_type}")
    print(f"   Tags: {card.tags}")
    print(f"   Source Item ID: {card.source_inbox_item_id}")

    # Verify Card properties
    assert card.id is not None
    assert card.title == "Important Concept"
    assert card.para_type == "concept"  # NOTE should map to concept
    assert "note" in card.tags  # Item type should be in tags
    assert card.source_inbox_item_id == item.id
    assert card.workspace_id == workspace.id
    assert card.user_id == user.id
    assert str(card.id) == card_id_str  # Verify the ID matches
