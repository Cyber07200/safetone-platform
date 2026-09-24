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

from app.models import Bank, BankSettings, Document, Product
from app.services.knowledge.ingest import DocumentMeta, ingest_text, ingest_upload

log = logging.getLogger("safetone.seed")
DOCS = Path(__file__).parent / "documents"
LEGACY = Path(__file__).parent / "legacy"

DEMO_BANK_SLUG = "demo-horizon"
OTHER_BANK_SLUG = "demo-isolation-check"

PRODUCTS = [
    ("card-horizon-120", "Кредитная карта «Горизонт 120»", "credit_card",
     "Кредитная карта с льготным периодом на покупки. Демонстрационный продукт."),
    ("loan-prostoy", "Потребительский кредит «Простой»", "loan",
     "Потребительский кредит без обеспечения. Демонстрационный продукт."),
    ("deposit-nadezhny", "Вклад «Надёжный»", "deposit",
     "Срочный вклад без пополнения. Демонстрационный продукт."),
    ("rko-start", "Расчётный счёт «Старт»", "account",
     "Расчётно-кассовое обслуживание для ИП и компаний. Демонстрационный продукт."),
]

DEMO_NOTE = "Демонстрационный документ: условия вымышлены."
LAW_NOTE = ("Справочный пересказ, а не официальный текст. Актуальность редакции не подтверждена — "
            "требуется сверка с официальным источником.")

# (file, product_code|None, meta kwargs)
BANK_DOCS = [
    ("card_tariff_v1.md", "card-horizon-120", dict(
        title="Тарифы по кредитной карте «Горизонт 120»", doc_type="tariff", document_key="card-horizon-tariffs",
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
]

GLOBAL_DOCS = [
    ("law_353fz_excerpt.md", dict(
        title="353-ФЗ «О потребительском кредите (займе)» — пересказ ст. 11", doc_type="law",
        document_key="law-353fz-art11", document_date=date(2013, 12, 21),
        source_url="http://pravo.gov.ru/", actuality_status="unverified")),
    ("law_395_excerpt.md", dict(
        title="395-1 «О банках и банковской деятельности» — пересказ ст. 29", doc_type="law",
        document_key="law-395-1-art29", document_date=date(1990, 12, 2),
        source_url="http://pravo.gov.ru/", actuality_status="unverified")),
    ("law_177fz_excerpt.md", dict(
        title="177-ФЗ «О страховании вкладов» — пересказ ст. 11", doc_type="law",
        document_key="law-177fz-art11", document_date=date(2003, 12, 23),
        source_url="http://pravo.gov.ru/", actuality_status="unverified")),
]

LEGACY_DOCS = [
    ("raschetny_schet.docx", "rko-start", dict(
        title="Расчётный счёт — справочный материал (из предыдущей версии SafeTone)", doc_type="reference",
        document_key="legacy-raschetny-schet", actuality_status="unverified",
        actuality_note="Материал перенесён из исходного проекта. Дата и актуальность не подтверждены.")),
    ("obshchie_usloviya_kreditovaniya.html", "loan-prostoy", dict(
        title="Общие условия кредитования — справочный материал (из предыдущей версии SafeTone)",
        doc_type="reference", document_key="legacy-obshchie-usloviya", actuality_status="unverified",
        actuality_note="Типовая форма стороннего банка из исходного проекта. Не является документом "
                       "демонстрационного банка; актуальность не подтверждена.")),
]


def seed_demo(db: Session) -> Bank:
    bank = db.scalar(select(Bank).where(Bank.slug == DEMO_BANK_SLUG))
    if bank:
        return bank
    log.info("Seeding demo dataset")
    bank = Bank(slug=DEMO_BANK_SLUG, name="Банк «Горизонт» (DEMO)", is_demo=True)
    db.add(bank)
    db.flush()
    db.add(BankSettings(bank_id=bank.id))
    products: dict[str, Product] = {}
    for code, name, category, descr in PRODUCTS:
        p = Product(bank_id=bank.id, code=code, name=name, category=category, description=descr, is_demo=True)
        db.add(p)
        products[code] = p
    db.flush()

    # A second, empty bank used to demonstrate / test tenant isolation.
    other = Bank(slug=OTHER_BANK_SLUG, name="Банк «Контроль изоляции» (DEMO)", is_demo=True)
    db.add(other)
    db.flush()
    db.add(BankSettings(bank_id=other.id))

    for fname, code, meta in BANK_DOCS:
        ingest_text(db, bank_id=bank.id, text=(DOCS / fname).read_text("utf-8"), meta=DocumentMeta(
            product_id=products[code].id if code else None, is_demo=True,
            scope_label=f"{bank.name} · {products[code].name}" if code else bank.name,
            actuality_note=DEMO_NOTE, **meta))
    for fname, meta in GLOBAL_DOCS:
        existing = db.scalar(select(Document).where(Document.bank_scope == "global",
                                                   Document.document_key == meta["document_key"]))
        if existing:
            continue
        ingest_text(db, bank_id=None, text=(DOCS / fname).read_text("utf-8"), meta=DocumentMeta(
            is_demo=True, scope_label="Российская Федерация · все банки", actuality_note=LAW_NOTE, **meta))
    for fname, code, meta in LEGACY_DOCS:
        path = LEGACY / fname
        if path.exists():
            ingest_upload(db, bank_id=bank.id, filename=fname, data=path.read_bytes(), meta=DocumentMeta(
                product_id=products[code].id, scope_label=f"{bank.name} · справочно", **meta))
    db.commit()
    return bank
