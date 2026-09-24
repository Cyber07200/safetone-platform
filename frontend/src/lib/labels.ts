import type { Actuality, ClaimStatus, ResultStatus, Risk, StageStatus } from "../types/api";

export type Tone3 = "ok" | "warn" | "bad" | "info" | "muted";

export const RESULT: Record<ResultStatus, { label: string; tone: Tone3; hint: string }> = {
  READY: { label: "READY", tone: "ok", hint: "Готово к отправке клиенту" },
  NEEDS_REVIEW: { label: "NEEDS REVIEW", tone: "warn", hint: "Черновик готов, нужна проверка специалистом" },
  FAILED: { label: "FAILED", tone: "bad", hint: "Обработка не завершена" },
};

export const CLAIM: Record<ClaimStatus, { label: string; tone: Tone3; ru: string }> = {
  CONFIRMED: { label: "CONFIRMED", tone: "ok", ru: "Подтверждено" },
  CONTRADICTED: { label: "CONTRADICTED", tone: "bad", ru: "Противоречит источнику" },
  UNVERIFIED: { label: "UNVERIFIED", tone: "warn", ru: "Недостаточно данных" },
  OUTDATED_SOURCE: { label: "OUTDATED SOURCE", tone: "warn", ru: "Актуальность источника не подтверждена" },
  NEEDS_REVIEW: { label: "NEEDS REVIEW", tone: "warn", ru: "Требуется экспертная проверка" },
};

export const RISK: Record<Risk, { label: string; tone: Tone3; ru: string }> = {
  LOW: { label: "LOW", tone: "ok", ru: "Низкий" },
  MEDIUM: { label: "MEDIUM", tone: "warn", ru: "Средний" },
  HIGH: { label: "HIGH", tone: "bad", ru: "Высокий" },
  CRITICAL: { label: "CRITICAL", tone: "bad", ru: "Критичный" },
};

export const ACTUALITY: Record<Actuality, { label: string; tone: Tone3 }> = {
  current: { label: "Действует", tone: "ok" },
  superseded: { label: "Заменён новой версией", tone: "muted" },
  expired: { label: "Утратил силу", tone: "bad" },
  not_yet_effective: { label: "Ещё не вступил в силу", tone: "warn" },
  unverified: { label: "Актуальность не подтверждена", tone: "warn" },
};

export const STAGE: Record<StageStatus, { label: string; tone: Tone3 }> = {
  pending: { label: "Ожидает", tone: "muted" },
  running: { label: "Выполняется", tone: "info" },
  completed: { label: "Выполнен", tone: "ok" },
  failed: { label: "Ошибка", tone: "bad" },
  skipped: { label: "Не выполнялся", tone: "muted" },
};

export const DOC_TYPES: Record<string, string> = {
  law: "Закон", regulation: "Нормативный акт", contract: "Договор", tariff: "Тариф", internal: "Внутренний документ",
  reference: "Справочный материал",
};

export const ACTIONS: Record<string, string> = {
  keep: "Без изменений", corrected: "Исправлено по источнику", replaced_with_source: "Заменено формулировкой источника",
  removed: "Удалено как неподтверждённое", kept_with_caution: "Оставлено с оговоркой",
};

export const ORIGIN: Record<string, string> = {
  scenario: "Заранее подготовленный демо-сценарий", provider: "Сгенерировано AI-провайдером", user: "Вставлено пользователем",
};

export const TONES = {
  neutral: "Нейтральный банковский", friendly: "Дружелюбный", concise: "Краткий и деловой", detailed: "Подробное объяснение",
} as const;
