"""Chat with the assistant. Conversations belong to a browser: the client
sends a random owner token in `X-Chat-Owner`; the server keeps only its HMAC.
Content is encrypted at rest (app/core/crypto.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core import crypto
from app.core.config import get_settings
from app.core.errors import LiveModeUnavailable, ValidationFailed
from app.db.session import get_db
from app.models import ChatConversation
from app.schemas.api import (ChatConversationDetail, ChatConversationOut, ChatMessageOut, ChatRenameRequest,
                             ChatSendRequest, ChatSendResponse, ErrorResponse)
from app.services import chat
from app.services.chat_files import read_attachment
from app.services.ai.router import get_router

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
ERRORS = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse},
          503: {"model": ErrorResponse}}


def owner(x_chat_owner: str = Header(description="Случайный токен браузера (32–128 символов base64url)")) -> str:
    if not crypto.OWNER_TOKEN.match(x_chat_owner):
        raise ValidationFailed("Некорректный X-Chat-Owner", code="INVALID_CHAT_OWNER")
    return crypto.owner_hash(x_chat_owner)


def _conv_out(c: ChatConversation) -> ChatConversationOut:
    return ChatConversationOut(id=c.id, title=chat.title_of(c), message_count=c.message_count,
                               created_at=c.created_at, updated_at=c.updated_at)


def _msg_out(m: chat.Plain) -> ChatMessageOut:
    att = {k: v for k, v in m.attachment.items() if k != "text"} if m.attachment else None
    return ChatMessageOut(id=m.id, role=m.role, content=m.content, sources=m.sources, mode=m.mode,  # type: ignore[arg-type]
                          model=m.model, created_at=m.created_at, attachment=att, findings=m.findings)


@router.get("/conversations", response_model=list[ChatConversationOut], responses=ERRORS)
def list_conversations(bank_id: str = Query(...), who: str = Depends(owner), db: Session = Depends(get_db)):
    return [_conv_out(c) for c in chat.list_conversations(db, bank_id, who)]


@router.get("/conversations/{conv_id}", response_model=ChatConversationDetail, responses=ERRORS)
def get_conversation(conv_id: str, who: str = Depends(owner), db: Session = Depends(get_db)):
    c = chat.get_conversation(db, conv_id, who)
    return ChatConversationDetail(**_conv_out(c).model_dump(), messages=[_msg_out(m) for m in chat.messages(db, c)])


@router.post("/messages", response_model=ChatSendResponse, responses={**ERRORS, 502: {"model": ErrorResponse}})
async def send_message(req: ChatSendRequest, who: str = Depends(owner), db: Session = Depends(get_db)):
    c, user_msg, bot_msg = await chat.send(db, get_router(), bank_id=req.bank_id, owner=who, content=req.content,
                                           conversation_id=req.conversation_id, mode=req.mode)
    return ChatSendResponse(conversation=_conv_out(c), user_message=_msg_out(user_msg),
                            assistant_message=_msg_out(bot_msg))


@router.post("/documents", response_model=ChatSendResponse, responses={**ERRORS, 413: {"model": ErrorResponse},
                                                                      502: {"model": ErrorResponse}})
async def send_document(bank_id: str = Form(...), file: UploadFile = File(...), content: str = Form(""),
                        conversation_id: str | None = Form(None), mode: str | None = Form(None),
                        who: str = Depends(owner), db: Session = Depends(get_db)):
    """Send a document (PDF, DOCX, TXT, MD, HTML, JPG, PNG) to the assistant for checking."""
    if mode not in (None, "", "live", "demo"):
        raise ValidationFailed("mode: live или demo", code="INVALID_MODE")
    if len(content) > get_settings().max_chat_message_chars:
        raise ValidationFailed("Сообщение слишком длинное", code="MESSAGE_TOO_LONG")
    router_ = get_router()
    if mode == "live" and not router_.live_available():
        raise LiveModeUnavailable("GigaChat не подключён: добавьте ключ в backend/.env или выберите Demo.")
    data = await file.read(get_settings().max_upload_bytes + 1)
    attachment = await read_attachment(file.filename or "document", data, router_.providers.get("gigachat"))
    c, user_msg, bot_msg = await chat.send(db, router_, bank_id=bank_id, owner=who, content=content,
                                           conversation_id=conversation_id or None, mode=mode or None,
                                           attachment=attachment)
    return ChatSendResponse(conversation=_conv_out(c), user_message=_msg_out(user_msg),
                            assistant_message=_msg_out(bot_msg))


@router.patch("/conversations/{conv_id}", response_model=ChatConversationOut, responses=ERRORS)
def rename_conversation(conv_id: str, req: ChatRenameRequest, who: str = Depends(owner),
                        db: Session = Depends(get_db)):
    c = chat.get_conversation(db, conv_id, who)
    chat.rename(db, c, req.title)
    return _conv_out(c)


@router.delete("/conversations/{conv_id}", status_code=204, responses=ERRORS)
def delete_conversation(conv_id: str, who: str = Depends(owner), db: Session = Depends(get_db)):
    chat.delete(db, chat.get_conversation(db, conv_id, who))
    return Response(status_code=204)
