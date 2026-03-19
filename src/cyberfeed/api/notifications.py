"""Notification rules API: CRUD, test send, list channels."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.api.deps import get_current_user, get_db
from cyberfeed.core.exceptions import NotFoundError, ValidationError
from cyberfeed.models.user import User
from cyberfeed.schemas.notification import (
    NotificationRuleCreate,
    NotificationRuleRead,
    NotificationRuleUpdate,
    NotificationTestRequest,
)
from cyberfeed.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])
notification_service = NotificationService()


@router.get("/channels")
async def list_channels(
    _user: User = Depends(get_current_user),
) -> dict:
    """List available notification channels."""
    return {"channels": notification_service.available_channels()}


@router.get("/rules")
async def list_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List the current user's notification rules."""
    rules = await notification_service.get_rules_for_user(db, user.id)
    return {"rules": [NotificationRuleRead.model_validate(r) for r in rules]}


@router.post("/rules")
async def create_rule(
    body: NotificationRuleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationRuleRead:
    """Create a new notification rule for the current user."""
    if body.channel not in notification_service.available_channels():
        raise ValidationError(f"Channel '{body.channel}' is not available")

    notifier = notification_service.get_notifier(body.channel)
    if notifier:
        is_valid, error = await notifier.validate_recipient(body.destination)
        if not is_valid:
            raise ValidationError(f"Invalid destination: {error}")

    rule = await notification_service.create_rule(
        db,
        user_id=user.id,
        channel=body.channel,
        destination=body.destination,
        keywords=body.keywords,
        category_ids=body.category_ids,
        source_platforms=body.source_platforms,
        is_active=body.is_active,
    )
    return NotificationRuleRead.model_validate(rule)


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: uuid.UUID,
    body: NotificationRuleUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationRuleRead:
    """Update one of the current user's notification rules."""
    rule = await notification_service.get_rule(db, rule_id, user.id)
    if not rule:
        raise NotFoundError("Notification rule")

    updates = body.model_dump(exclude_unset=True)
    rule = await notification_service.update_rule(db, rule, **updates)
    return NotificationRuleRead.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete one of the current user's notification rules."""
    deleted = await notification_service.delete_rule(db, rule_id, user.id)
    if not deleted:
        raise NotFoundError("Notification rule")


@router.post("/test")
async def test_notification(
    body: NotificationTestRequest,
    _user: User = Depends(get_current_user),
) -> dict:
    """Send a test notification to verify channel configuration."""
    success, message = await notification_service.test_notification(body.channel, body.destination)
    return {"success": success, "message": message}
