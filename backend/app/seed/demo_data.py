"""Reproducible demo dataset: a fictional bank, its products and documents.

Everything seeded here is marked `is_demo=True` (except materials carried
over from the previous SafeTone version, which are marked as reference
documents with *unverified* actuality).
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Bank, BankSettings, Product
from app.services.knowledge.ingest import DocumentMeta, ingest_text

log = logging.getLogger("safetone.seed")
DOCS = Path(__file__).parent / "documents"

DEMO_BANK_SLUG = "yasny-bereg"
BANK_NAME = "Банк «Ясный Берег» (DEMO)"
# Earlier demo banks; removed on startup so the installation has exactly one bank.
RETIRED_SLUGS = ("demo-horizon", "demo-isolation-check")
OTHER_BANK_SLUG = "test-isolation-bank"  # created only by the test suite

PRODUCTS = [
    ("card-bereg-120", "Кредитная карта «Берег 120»", "credit_card",
     "Кредитная карта с льготным периодом на покупки. Демонстрационный продукт."),
    ("loan-prostoy", "Потребительский кредит «Простой»", "loan",
     "Потребительский кредит без обеспечения. Демонстрационный продукт."),
    ("deposit-nadezhny", "Вклад «Надёжный»", "deposit",
     "Срочный вклад без пополнения. Демонстрационный продукт."),
    ("rko-start", "Расчётный счёт «Старт»", "account",
     "Расчётно-кассовое обслуживание для ИП и компаний. Демонстрационный продукт."),
    ("debit-yasnaya", "Дебетовая карта «Ясная»", "debit_card",
     "Бесплатная дебетовая карта с кэшбэком. Демонстрационный продукт."),
    ("savings-priboy", "Накопительный счёт «Прибой»", "savings",
     "Накопительный счёт с ежемесячной выплатой процентов. Демонстрационный продукт."),
    ("mortgage-svoy-dom", "Ипотека «Свой дом»", "mortgage",
     "Ипотечный кредит на покупку квартиры. Демонстрационный продукт."),
]

DEMO_NOTE = "Демонстрационный документ: условия вымышлены."

# (file, product_code|None, meta kwargs)
BANK_DOCS = [
    ("card_tariff_v1.md", "card-bereg-120", dict(
        title="Тарифы по кредитной карте «Берег 120»", doc_type="tariff", document_key="card-bereg-tariffs",
        document_date=date(2026, 2, 10), effective_from=date(2026, 3, 1), actuality_status="current")),
    ("loan_contract_v1.md", "loan-prostoy", dict(
        title="Общие условия договора потребительского кредита «Простой»", doc_type="contract",
        document_key="loan-prostoy-general-terms", document_date=date(2026, 1, 15),
        effective_from=date(2026, 2, 1), actuality_status="current")),
    ("deposit_tariff_v1.md", "deposit-nadezhny", dict(
        title="Условия вклада «Надёжный»", doc_type="tariff", document_key="deposit-nadezhny-terms",
        document_date=date(2026, 4, 1), effective_from=date(2026, 4, 15), actuality_status="current")),
    ("rko_tariff_v1.md", "rko-start", dict(
        title="Тарифы РКО «Старт»", doc_type="tariff", document_key="rko-start-tariffs",
        document_date=date(2024, 12, 1), effective_from=date(2025, 1, 1), effective_to=date(2026, 1, 31),
        actuality_status="current")),
    ("rko_tariff_v2.md", "rko-start", dict(
        title="Тарифы РКО «Старт»", doc_type="tariff", document_key="rko-start-tariffs",
        document_date=date(2026, 1, 10), effective_from=date(2026, 2, 1), actuality_status="current")),
    ("rko_rules_v1.md", "rko-start", dict(
        title="Правила открытия, ведения и закрытия расчётного счёта", doc_type="internal",
        document_key="rko-rules", document_date=date(2025, 11, 20), effective_from=date(2025, 12, 1),
        actuality_status="current")),
    ("debit_card_tariff.md", "debit-yasnaya", dict(
        title="Тарифы по дебетовой карте «Ясная»", doc_type="tariff", document_key="debit-yasnaya-tariffs",
        document_date=date(2026, 3, 1), effective_from=date(2026, 3, 15), actuality_status="current")),
    ("savings_account.md", "savings-priboy", dict(
        title="Условия накопительного счёта «Прибой»", doc_type="tariff", document_key="savings-priboy-terms",
        document_date=date(2026, 5, 1), effective_from=date(2026, 5, 15), actuality_status="current")),
    ("mortgage_terms.md", "mortgage-svoy-dom", dict(
        title="Условия ипотечного кредита «Свой дом»", doc_type="contract", document_key="mortgage-svoy-dom-terms",
        document_date=date(2026, 2, 1), effective_from=date(2026, 2, 15), actuality_status="current")),
    ("about_bank.md", None, dict(
        title="О банке «Ясный Берег»: история и контакты", doc_type="internal", document_key="about-bank",
        document_date=date(2026, 1, 10), effective_from=date(2026, 1, 10), actuality_status="current")),
    ("general_terms.md", None, dict(
        title="Общие условия обслуживания физических лиц", doc_type="contract", document_key="general-terms",
        document_date=date(2026, 1, 10), effective_from=date(2026, 2, 1), actuality_status="current")),
    ("complaints_rules.md", None, dict(
        title="Порядок рассмотрения обращений клиентов", doc_type="internal", document_key="complaints-rules",
        document_date=date(2025, 12, 1), effective_from=date(2026, 1, 1), actuality_status="current")),
    ("security_rules.md", None, dict(
        title="Правила безопасности клиентов", doc_type="internal", document_key="security-rules",
        document_date=date(2026, 4, 1), effective_from=date(2026, 4, 1), actuality_status="current")),
    ("faq.md", None, dict(
        title="Частые вопросы клиентов", doc_type="reference", document_key="faq",
        document_date=date(2026, 6, 1), effective_from=date(2026, 6, 1), actuality_status="current")),
]

def retire_old_demo_banks(db: Session) -> None:
    """Remove earlier demo banks (cascades to their documents, runs and chats)."""
    for old in db.scalars(select(Bank).where(Bank.slug.in_(RETIRED_SLUGS), Bank.is_demo.is_(True))):
        log.info("Removing retired demo bank %s", old.slug)
        db.delete(old)
    db.commit()


def seed_isolation_bank(db: Session) -> Bank:
    """An empty second bank — the test suite uses it to prove tenant isolation."""
    bank = db.scalar(select(Bank).where(Bank.slug == OTHER_BANK_SLUG))
    if not bank:
        bank = Bank(slug=OTHER_BANK_SLUG, name="Банк «Контроль изоляции» (TEST)", is_demo=True)
        db.add(bank)
        db.flush()
        db.add(BankSettings(bank_id=bank.id))
        db.commit()
    return bank


def seed_demo(db: Session) -> Bank:
    bank = db.scalar(select(Bank).where(Bank.slug == DEMO_BANK_SLUG))
    if bank:
        return bank
    log.info("Seeding demo dataset")
    bank = Bank(slug=DEMO_BANK_SLUG, name=BANK_NAME, is_demo=True)
    db.add(bank)
    db.flush()
    # The bank is fictional, so its documents may be shown to GigaChat as context.
    db.add(BankSettings(bank_id=bank.id, allow_documents_to_llm=True))
    products: dict[str, Product] = {}
    for code, name, category, descr in PRODUCTS:
        p = Product(bank_id=bank.id, code=code, name=name, category=category, description=descr, is_demo=True)
        db.add(p)
        products[code] = p
    db.flush()

    for fname, code, meta in BANK_DOCS:
        ingest_text(db, bank_id=bank.id, text=(DOCS / fname).read_text("utf-8"), meta=DocumentMeta(
            product_id=products[code].id if code else None, is_demo=True,
            scope_label=f"{bank.name} · {products[code].name}" if code else bank.name,
            actuality_note=DEMO_NOTE, **meta))
    db.commit()
    return bank
