"""Demo scenarios.

Each scenario contains a question and a PRE-WRITTEN "AI answer". In Demo
Mode this text replaces the generation step and is always labelled in the
audit as `answer_origin = "scenario"` — it is never presented as output of
a real language model. The legal and linguistic layers then run for real
on this text against the demo knowledge base.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    category: str
    product_code: str
    question: str
    answer: str
    expected_status: str  # what the scenario is designed to demonstrate
    demonstrates: str

    def to_dict(self) -> dict:
        return asdict(self)


SCENARIOS: list[Scenario] = [
    Scenario(
        id="safe-balance", title="Безопасный ответ", category="safe",
        product_code="card-horizon-120",
        question="Как узнать баланс кредитной карты?",
        answer=("Здравствуйте! Доступный баланс и сумму задолженности по карте можно посмотреть в мобильном "
                "приложении и в интернет-банке в разделе «Карты». Баланс карты также можно запросить в банкомате "
                "банка, выбрав пункт «Баланс». Выписку по счёту карты можно получить без оплаты в мобильном "
                "приложении. Если у вас остались вопросы — обращайтесь!"),
        expected_status="READY",
        demonstrates="Подтверждённый ответ проходит без предупреждений. Фраза «без оплаты» раньше блокировалась "
                     "старым сборником rules — теперь она проверяется по тарифу и подтверждается.",
    ),
    Scenario(
        id="rate-error", title="Ошибка в процентной ставке", category="contradiction",
        product_code="card-horizon-120",
        question="Какая ставка по кредитной карте «Горизонт 120» на покупки?",
        answer=("Процентная ставка по операциям покупок по карте «Горизонт 120» составляет 19,9% годовых. "
                "Льготный период на покупки — до 120 дней."),
        expected_status="READY",
        demonstrates="Неверная ставка исправляется только потому, что в действующем тарифе есть подтверждённое значение.",
    ),
    Scenario(
        id="fee-error", title="Неверное утверждение о комиссии", category="contradiction",
        product_code="card-horizon-120",
        question="Сколько стоит снять наличные с кредитной карты?",
        answer=("Снятие наличных с кредитной карты в банкоматах любых банков — без комиссии. "
                "Льготный период распространяется и на снятие наличных."),
        expected_status="READY",
        demonstrates="Утверждение «без комиссии» противоречит тарифу; формулировка заменяется текстом тарифа.",
    ),
    Scenario(
        id="contract-conflict", title="Противоречие условиям договора", category="contradiction",
        product_code="loan-prostoy",
        question="Можно ли досрочно погасить потребительский кредит?",
        answer=("Да, кредит можно погасить досрочно. За досрочное погашение взимается комиссия 2% от суммы. "
                "Заявление на досрочное погашение нужно подать не позднее чем за 30 дней до даты погашения."),
        expected_status="READY",
        demonstrates="Два утверждения противоречат п. 5.1 и 5.2 договора и исправляются по договору; "
                     "верная часть ответа сохраняется.",
    ),
    Scenario(
        id="incomplete-data", title="Неполные данные", category="unverified",
        product_code="deposit-nadezhny",
        question="Какая ставка по вкладу «Надёжный» на 2 года?",
        answer=("По вкладу «Надёжный» на срок 24 месяца действует ставка 16% годовых. "
                "Минимальная сумма вклада — 10 000 ₽."),
        expected_status="NEEDS_REVIEW",
        demonstrates="Тариф на 24 месяца в базе отсутствует: ставка не «исправляется» выдуманным значением, "
                     "утверждение убирается, а в аудите указано, каких данных не хватает.",
    ),
    Scenario(
        id="ambiguous-legal", title="Неоднозначный юридический вопрос", category="legal",
        product_code="loan-prostoy",
        question="Может ли банк в одностороннем порядке повысить ставку по моему кредиту?",
        answer=("Нет, банк никогда не может повысить ставку по кредиту в одностороннем порядке — это запрещено "
                "в любых обстоятельствах. Если ставка выросла, вы можете сразу обращаться в суд."),
        expected_status="NEEDS_REVIEW",
        demonstrates="Абсолютная формулировка противоречит договору с исключением (п. 4.3–4.4); "
                     "юридический совет не подтверждён — ответ идёт на экспертную проверку с безопасным черновиком.",
    ),
    Scenario(
        id="critical-guarantee", title="Критичный риск: обещание одобрения", category="critical",
        product_code="loan-prostoy",
        question="Вы гарантируете одобрение кредита?",
        answer=("Да, мы гарантируем одобрение кредита. Банк не отказывает в выдаче кредита, заявка одобряется "
                "без проверки кредитной истории."),
        expected_status="NEEDS_REVIEW",
        demonstrates="Обещание одобрения противоречит договору: формулировки заменяются положениями договора, "
                     "но из-за критичного риска ответ требует ручного подтверждения.",
    ),
    Scenario(
        id="plain-language", title="Упрощение без изменения смысла", category="linguistic",
        product_code="rko-start",
        question="Как закрыть расчётный счёт и что будет с остатком?",
        answer=("В целях осуществления процедуры закрытия расчётного счёта Клиенту надлежит осуществить подачу "
                "заявления о закрытии счёта в интернет-банке или в офисе Банка. Остаток денежных средств "
                "перечисляется по реквизитам, указанным Клиентом в заявлении, не позднее 7 рабочих дней со дня "
                "получения заявления. Банк самостоятельно сообщает в налоговый орган о закрытии счёта."),
        expected_status="READY",
        demonstrates="Канцелярит упрощается, а срок 7 рабочих дней и все условия сохраняются — это подтверждает "
                     "проверка сохранения смысла.",
    ),
    Scenario(
        id="outdated-tariff", title="Устаревший тариф", category="outdated",
        product_code="rko-start",
        question="Сколько стоит обслуживание расчётного счёта «Старт»?",
        answer="Обслуживание расчётного счёта «Старт» стоит 490 ₽ в месяц, открытие счёта — без комиссии.",
        expected_status="READY",
        demonstrates="490 ₽ совпадает только с редакцией тарифа 2025 года (не действует). Действующая редакция "
                     "имеет приоритет, значение исправляется, устаревшая версия отмечена в аудите.",
    ),
    Scenario(
        id="unverified-law", title="Источник без подтверждённой актуальности", category="outdated",
        product_code="deposit-nadezhny",
        question="Застрахован ли мой вклад «Надёжный»?",
        answer=("Да, вклады физических лиц застрахованы. Возмещение выплачивается в размере 100% суммы вкладов, "
                "но не более 1 400 000 ₽ в совокупности."),
        expected_status="NEEDS_REVIEW",
        demonstrates="Утверждения совпадают только с пересказом закона, актуальность которого не подтверждена: "
                     "статус OUTDATED_SOURCE, SafeTone не заявляет о проверке по действующему законодательству.",
    ),
]

BY_ID = {s.id: s for s in SCENARIOS}
