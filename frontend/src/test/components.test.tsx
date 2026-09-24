import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { diffWords } from "../lib/diff";
import { PipelineProgress } from "../features/workspace/PipelineProgress";
import { ResultView } from "../features/workspace/ResultView";
import { ClaimBadge, EmptyState, ErrorState, ResultBadge, RiskBadge } from "../components/ui";
import { ApiError } from "../services/api";
import { FAILED_RUN, RUN, stages } from "./fixtures";

describe("diffWords", () => {
  it("marks changed value as deleted and added", () => {
    const parts = diffWords("Ставка 19,9% годовых", "Ставка 29,9% годовых");
    expect(parts.find((p) => p.type === "del")?.text).toBe("19,9%");
    expect(parts.find((p) => p.type === "add")?.text).toBe("29,9%");
  });
  it("returns no changes for equal text", () => {
    expect(diffWords("a b", "a b").every((p) => p.type === "same")).toBe(true);
  });
});

describe("badges", () => {
  it("render statuses and risks", () => {
    render(<><ResultBadge status="NEEDS_REVIEW" /><ClaimBadge status="OUTDATED_SOURCE" /><RiskBadge risk="CRITICAL" /></>);
    expect(screen.getByText("NEEDS REVIEW")).toBeInTheDocument();
    expect(screen.getByText("OUTDATED SOURCE")).toBeInTheDocument();
    expect(screen.getByText(/CRITICAL/)).toBeInTheDocument();
  });
});

describe("states", () => {
  it("empty and error states", async () => {
    let retried = false;
    render(<><EmptyState title="Пусто" /><ErrorState error={new ApiError(500, "X_CODE", "Сломалось")} onRetry={() => { retried = true; }} /></>);
    expect(screen.getByText("Пусто")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Сломалось");
    expect(screen.getByText("X_CODE")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Повторить/ }));
    expect(retried).toBe(true);
  });
});

describe("PipelineProgress", () => {
  it("shows pending stages before a run", () => {
    const { container } = render(<PipelineProgress />);
    expect(container.querySelectorAll('[data-status="pending"]')).toHaveLength(8);
  });
  it("never shows a failed run as completed", async () => {
    const { container } = render(<PipelineProgress stages={FAILED_RUN.stages} />);
    await screen.findByText("Все провайдеры вернули ошибку");
    expect(container.querySelector('[data-stage="generation"]')?.getAttribute("data-status")).toBe("failed");
    await new Promise((r) => setTimeout(r, 1200));
    expect(container.querySelectorAll('[data-status="completed"]')).toHaveLength(0);
    expect(container.querySelectorAll('[data-status="skipped"]')).toHaveLength(7);
  });
  it("reveals completed stages", async () => {
    const { container } = render(<PipelineProgress stages={stages()} />);
    await new Promise((r) => setTimeout(r, 1200));
    expect(container.querySelectorAll('[data-status="completed"]')).toHaveLength(8);
  });
});

describe("ResultView", () => {
  const wrap = (ui: React.ReactNode) => render(<MemoryRouter>{ui}</MemoryRouter>);
  it("shows final answer, demo label and comparison", () => {
    wrap(<ResultView run={RUN} />);
    expect(screen.getByTestId("final-answer")).toHaveTextContent("29,9%");
    expect(screen.getByTestId("status-banner")).toHaveAttribute("data-status", "READY");
    expect(screen.getAllByText("DEMO MODE").length).toBeGreaterThan(0);
    expect(screen.getByText("Сравнение версий")).toBeInTheDocument();
  });
  it("switches to detailed audit with all sections", async () => {
    wrap(<ResultView run={RUN} />);
    await userEvent.click(screen.getByRole("radio", { name: "Подробный аудит" }));
    const audit = await screen.findByTestId("audit-view");
    for (const t of ["Вопрос пользователя", "Исходный ответ", "Источники · 1", "Статусы и риски", "Юридически скорректированный ответ", "Проверка сохранения смысла", "Финальный ответ", "Модель и режим работы"])
      expect(audit).toHaveTextContent(t);
    expect(audit).toHaveTextContent("Заранее подготовленный демо-сценарий");
    expect(audit).toHaveTextContent("не использовались");
  });
  it("failed run shows error instead of a result", () => {
    wrap(<ResultView run={FAILED_RUN} />);
    expect(screen.getByTestId("status-banner")).toHaveAttribute("data-status", "FAILED");
    expect(screen.getByTestId("final-answer")).toHaveTextContent("не сформирован");
    expect(screen.getByRole("button", { name: /Копировать/ })).toBeDisabled();
  });
});
