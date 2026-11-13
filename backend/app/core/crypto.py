"""Encryption of chat history at rest.

* Content (messages, titles, summaries, source lists) is encrypted with
  AES-256-GCM — authenticated encryption: a modified ciphertext fails to
  decrypt instead of producing garbage.
* Every conversation gets its own key, derived from the master key with
  HKDF-SHA256 (info = conversation id). A leaked conversation key does not
  open other conversations.
* Each ciphertext is bound to its record via AAD (e.g. "<message id>:user"),
  so ciphertexts cannot be swapped between messages, roles or chats.
* A fresh random 96-bit nonce per encryption.
* The browser's owner token is stored only as HMAC-SHA256 under a key
  derived from the master key: a database dump alone reveals neither the
  token nor who owns which chat.

Hashing is deliberately NOT used for content: a hash is one-way, and the
assistant must read the history to remember the dialogue.

The master key lives only in the backend environment (CHAT_ENCRYPTION_KEY),
never in the database. Without it the stored history is unreadable — back
it up. The "v1." prefix leaves room for key rotation.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings
from app.core.errors import AppError

VERSION = "v1"
_NONCE = 12
OWNER_TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


class CryptoUnavailable(AppError):
    status_code = 503
    code = "CHAT_ENCRYPTION_NOT_CONFIGURED"


class DecryptionFailed(AppError):
    status_code = 500
    code = "CHAT_DECRYPTION_FAILED"


@lru_cache
def _master() -> bytes:
    raw = get_settings().chat_encryption_key
    if raw is None:
        raise CryptoUnavailable("Шифрование переписки не настроено: задайте CHAT_ENCRYPTION_KEY в backend/.env.")
    try:
        key = base64.b64decode(raw.get_secret_value(), validate=True)
    except ValueError as exc:
        raise CryptoUnavailable("CHAT_ENCRYPTION_KEY должен быть в base64.") from exc
    if len(key) != 32:
        raise CryptoUnavailable("CHAT_ENCRYPTION_KEY должен содержать ровно 32 байта (256 бит).")
    return key


def _derive(purpose: bytes, context: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b"safetone/" + purpose,
                info=context.encode()).derive(_master())


def encrypt(conversation_id: str, plaintext: str, aad: str) -> str:
    nonce = os.urandom(_NONCE)
    ct = AESGCM(_derive(b"chat", conversation_id)).encrypt(nonce, plaintext.encode("utf-8"), aad.encode())
    return f"{VERSION}.{base64.urlsafe_b64encode(nonce + ct).decode()}"


def decrypt(conversation_id: str, token: str, aad: str) -> str:
    version, _, payload = token.partition(".")
    if version != VERSION:
        raise DecryptionFailed("Неизвестная версия шифрования записи.")
    try:
        data = base64.urlsafe_b64decode(payload)
        pt = AESGCM(_derive(b"chat", conversation_id)).decrypt(data[:_NONCE], data[_NONCE:], aad.encode())
    except (InvalidTag, ValueError) as exc:
        raise DecryptionFailed("Запись не расшифровывается: изменён ключ или данные повреждены.") from exc
    return pt.decode("utf-8")


def owner_hash(owner_token: str) -> str:
    return hmac.new(_derive(b"owner", "chat-owner"), owner_token.encode(), hashlib.sha256).hexdigest()


def reset_cache() -> None:
    """Forget the cached master key (tests / key rotation)."""
    _master.cache_clear()
