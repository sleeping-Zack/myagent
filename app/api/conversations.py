from __future__ import annotations

import uuid
from typing import cast, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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


async def _visitor(request: Request, response: Response, db: AsyncSession):
    context = await visitor_session_service.resolve(request, db)
    visitor_session_service.set_cookie(response, context)
    return context


@router.get("", response_model=ConversationList)
async def list_conversations(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    visitor = await _visitor(request, response, db)
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
    visitor = await _visitor(request, response, db)
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
    visitor = await _visitor(request, response, db)
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
    visitor = await _visitor(request, response, db)
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
    visitor = await _visitor(request, response, db)
    repository = ConversationRepository()
    conversation = await repository.get_owned(db, conversation_id, visitor.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    await repository.soft_delete(db, conversation)
