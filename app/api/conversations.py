from __future__ import annotations

import uuid
from typing import cast, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import get_settings
from app.core.rate_limit import (
    conversation_create_rate_limiter,
    visitor_create_rate_limiter,
)
from app.core.security import get_client_ip, hash_ip
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.conversation import (
    ConversationCreate,
    ConversationItem,
    ConversationList,
    ConversationUpdate,
    MessageItem,
    MessageList,
)
from app.services.visitor_session_service import visitor_session_service


router = APIRouter(prefix="/api/v1/conversations")


async def _existing_visitor(request: Request, db: AsyncSession):
    return await visitor_session_service.get_existing(request, db)


@router.get("", response_model=ConversationList)
async def list_conversations(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    visitor = await _existing_visitor(request, db)
    if visitor is None:
        return ConversationList(items=[])
    rows = await ConversationRepository().list_owned(db, visitor.id)
    return ConversationList(items=[
        ConversationItem(
            id=conversation.id,
            title=conversation.title or "新对话",
            message_count=conversation.message_count or 0,
            last_message_preview=(preview[:80] if preview else None),
            updated_at=(
                conversation.last_message_at
                or conversation.last_active_at
                or conversation.created_at
            ),
        )
        for conversation, preview in rows
    ])


@router.post("", response_model=ConversationItem, status_code=201)
async def create_conversation(
    body: ConversationCreate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    client_key = hash_ip(get_client_ip(request))
    if not await conversation_create_rate_limiter.allow(
        "new-conversation:" + client_key,
        minute_limit=settings.conversation_create_ip_minute_limit,
        daily_limit=settings.conversation_create_daily_limit,
    ):
        raise HTTPException(
            status_code=429,
            detail="新建对话过于频繁，请稍后再试",
            headers={"Retry-After": "60"},
        )
    visitor = await _existing_visitor(request, db)
    if visitor is None:
        if not await visitor_create_rate_limiter.allow(
            "new-visitor:" + client_key,
            minute_limit=settings.visitor_create_ip_minute_limit,
            daily_limit=settings.visitor_create_daily_limit,
        ):
            raise HTTPException(
                status_code=429,
                detail="新建匿名会话过于频繁，请稍后再试",
                headers={"Retry-After": "60"},
            )
        visitor = await visitor_session_service.create(db)
        visitor_session_service.set_cookie(response, visitor)
    conversation = await ConversationRepository().create_conversation(
        db, visitor.id, body.title
    )
    return ConversationItem(
        id=conversation.id,
        title=conversation.title or "新对话",
        message_count=0,
        last_message_preview=None,
        updated_at=conversation.created_at,
    )


@router.get("/{conversation_id}/messages", response_model=MessageList)
async def list_messages(
    conversation_id: uuid.UUID,
    request: Request,
    response: Response,
    before_sequence: Optional[int] = None,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
):
    visitor = await _existing_visitor(request, db)
    if visitor is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    repository = ConversationRepository()
    conversation = await repository.get_owned(db, conversation_id, visitor.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    safe_limit = max(1, min(limit, 50))
    messages = await repository.get_messages(
        db, conversation.id, safe_limit + 1, before_sequence
    )
    has_more = len(messages) > safe_limit
    if has_more:
        messages = messages[1:]
    return MessageList(
        items=[
            MessageItem(
                id=message.id,
                sequence_no=message.sequence_no or 0,
                role=cast(Literal["user", "assistant"], message.role),
                content=message.content,
                status=message.status,
                citation_data=message.citation_data or [],
                latency_ms=message.latency_ms,
                created_at=message.created_at,
            )
            for message in messages
            if message.role in {"user", "assistant"}
        ],
        has_more=has_more,
    )


@router.patch("/{conversation_id}", status_code=204)
async def rename_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    visitor = await _existing_visitor(request, db)
    if visitor is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    repository = ConversationRepository()
    conversation = await repository.get_owned(db, conversation_id, visitor.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    await repository.rename(db, conversation, body.title)


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    visitor = await _existing_visitor(request, db)
    if visitor is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    repository = ConversationRepository()
    conversation = await repository.get_owned(db, conversation_id, visitor.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    await repository.soft_delete(db, conversation)
