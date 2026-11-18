import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { api } from "../src/api";
import DashboardWorklist from "../src/components/DashboardWorklist";
import type { DashboardWorklistData, DashboardWorkItem } from "../src/types/dashboard";

vi.mock("../src/api", () => ({ api: { get: vi.fn() } }));

const item: DashboardWorkItem = {
  key: "task:1", kind: "task", case_id: 12, case_title: "Vertragsprüfung", task_id: 1,
  title: "Unterlagen sichten", responsible_person: "Anna", deadline: "2026-11-20",
  preparation_date: "2026-11-17", attention_date: "2026-11-17", priority: "normal",
  attention_reasons: ["Vorbereitungsbeginn erreicht"],
  reasons: ["Vorbereitung ab 17.11.2026"], next_action: "Unterlagen sichten",
};
const data: DashboardWorklistData = {
  today: "2026-11-17", through: "2026-11-24", timezone: "Europe/Berlin",
  preparation_lead_days: 3, today_items: [item], next_seven_days_items: [item, {
    ...item, key: "task:2", task_id: 2, title: "Antwort versenden", next_action: "Antwort versenden",
    deadline: "2026-11-27", preparation_date: "2026-11-24", attention_date: "2026-11-24",
  }],
};

function show() {
  return render(<MemoryRouter><DashboardWorklist /></MemoryRouter>);
}

beforeEach(() => { vi.mocked(api.get).mockReset(); });
afterEach(cleanup);

describe("dashboard worklist", () => {
  it("shows today's work, separate dates, reasons, and case navigation", async () => {
    vi.mocked(api.get).mockResolvedValue({ data });
    show();
    const link = await screen.findByRole("link", { name: /CF-0012 — Vertragsprüfung/ });
    expect(link.getAttribute("href")).toBe("/cases/12");
    expect(screen.getByText("Anna")).toBeTruthy();
    expect(screen.getByText("20.11.2026")).toBeTruthy();
    expect(screen.getAllByText("17.11.2026")).toHaveLength(2);
    expect(screen.getByText("Handlungsdatum:")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /Handlungsgrund/ }));
    expect(screen.getByText("Vorbereitung ab 17.11.2026")).toBeTruthy();
    expect(screen.getByText("Vorbereitungsbeginn:")).toBeTruthy();
    expect(screen.queryByText("Antwort versenden")).toBeNull();
    expect(api.get).toHaveBeenCalledExactlyOnceWith("/dashboard/worklist");
  });

  it("switches to next seven days and back without another request", async () => {
    vi.mocked(api.get).mockResolvedValue({ data });
    show();
    await screen.findByRole("link", { name: /CF-0012/ });
    await userEvent.click(screen.getByRole("button", { name: "Kommende 7 Tage (1)" }));
    expect(screen.getAllByText("Antwort versenden")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Kommende 7 Tage (1)" }).getAttribute("aria-pressed")).toBe("true");
    await userEvent.click(screen.getByRole("button", { name: /^Heute \(\d+\)$/ }));
    expect(screen.queryByText("Antwort versenden")).toBeNull();
    expect(api.get).toHaveBeenCalledTimes(1);
  });

  it("shows missing information without manufacturing dates", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { ...data, today_items: [{
      ...item, responsible_person: null, deadline: null, preparation_date: null, attention_date: null,
      next_action: "Nächste Maßnahme festlegen", reasons: ["Verantwortung offen"],
    }] } });
    show();
    expect(await screen.findByText("Keine Frist")).toBeTruthy();
    expect(screen.queryByText("Vorbereitungsbeginn:")).toBeNull();
    expect(screen.queryByText("Handlungsdatum:")).toBeNull();
    expect(screen.getByText("Nicht zugewiesen")).toBeTruthy();
    expect(screen.getByText("Nächste Maßnahme festlegen")).toBeTruthy();
  });

  it("shows loading and an empty state", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { ...data, today_items: [] } });
    show();
    expect(screen.getByRole("status").textContent).toContain("wird geladen");
    expect(await screen.findByText("Keine Maßnahmen mit Handlungsbedarf heute.")).toBeTruthy();
  });

  it("contains request failures in the worklist section", async () => {
    vi.mocked(api.get).mockRejectedValue(new Error("Unavailable"));
    show();
    expect((await screen.findByRole("alert")).textContent).toContain("konnte nicht geladen werden");
  });

  it("explains a due Wiedervorlage independently of the November 30 deadline", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: {
      ...data, today: "2026-11-18", through: "2026-11-25", today_items: [{
        ...item, deadline: "2026-11-30", preparation_date: "2026-11-27",
        attention_date: "2026-11-18", attention_reasons: ["Wiedervorlage am 18.11.2026"],
        reasons: ["Wiedervorlage fällig"],
      }], next_seven_days_items: [],
    } });
    show();
    const card = (await screen.findByRole("link", { name: /CF-0012/ })).closest("article")!;
    expect(within(card).getByText("Handlungsdatum:").parentElement?.textContent).toBe("Handlungsdatum: 18.11.2026");
    expect(within(card).getByText(/Wiedervorlage am 18.11.2026/)).toBeTruthy();
    expect(within(card).getByText("Frist:").parentElement?.textContent).toBe("Frist: 30.11.2026");
    expect(within(card).getByText("Vorbereitungsbeginn:").parentElement?.textContent).toBe("Vorbereitungsbeginn: 27.11.2026");
    await userEvent.click(screen.getByRole("button", { name: "Kommende 7 Tage (0)" }));
    expect(screen.queryByRole("link", { name: /CF-0012/ })).toBeNull();
  });

  it("never repeats today's cards in the upcoming view, including older inclusive API responses", async () => {
    vi.mocked(api.get).mockResolvedValue({ data });
    show();
    await screen.findByRole("link", { name: /CF-0012/ });
    await userEvent.click(screen.getByRole("button", { name: "Kommende 7 Tage (1)" }));
    expect(screen.queryByText("Unterlagen sichten")).toBeNull();
    expect(screen.getAllByText("Antwort versenden")).toHaveLength(2);
    expect(screen.getByText("Handlungsdatum:").parentElement?.textContent).toBe("Handlungsdatum: 24.11.2026");
  });

  it("shows a sentence preview and independently expands measures and Handlungsgrund per card", async () => {
    const firstSentence = "Die vorhandenen Unterlagen zunächst sorgfältig prüfen.";
    const fullAction = `${firstSentence}\n${"Weitere Unterlagen und Zuständigkeiten prüfen, ".repeat(12)}Originaltext vollständig erhalten.`;
    vi.mocked(api.get).mockResolvedValue({ data: { ...data, today_items: [
      { ...item, next_action: fullAction },
      { ...item, key: "task:3", case_id: 13, next_action: fullAction },
    ] } });
    show();
    const cards = await screen.findAllByRole("article");
    const first = within(cards[0]);
    const second = within(cards[1]);
    const firstButton = first.getByRole("button", { name: "Vollständige Maßnahme anzeigen" });
    const secondButton = second.getByRole("button", { name: "Vollständige Maßnahme anzeigen" });
    const actionElement = document.getElementById(firstButton.getAttribute("aria-controls")!)!;
    const secondElement = document.getElementById(secondButton.getAttribute("aria-controls")!)!;
    expect(actionElement.textContent).toBe(`${firstSentence}…`);
    expect(firstButton.getAttribute("aria-expanded")).toBe("false");
    await userEvent.click(firstButton);
    expect(actionElement.textContent).toBe(fullAction);
    expect(first.getByRole("button", { name: "Weniger anzeigen" }).getAttribute("aria-expanded")).toBe("true");
    expect(secondElement.textContent).toBe(`${firstSentence}…`);
    expect(secondButton.getAttribute("aria-expanded")).toBe("false");
    const reasonButton = first.getByRole("button", { name: /Handlungsgrund/ });
    await userEvent.click(reasonButton);
    expect(reasonButton.getAttribute("aria-expanded")).toBe("true");
    expect(actionElement.textContent).toBe(fullAction);
    await userEvent.click(first.getByRole("button", { name: "Weniger anzeigen" }));
    expect(actionElement.textContent).toBe(`${firstSentence}…`);
    expect(first.getByRole("button", { name: "Priorisierungsgründe ausblenden" }).getAttribute("aria-expanded")).toBe("true");
    expect(second.getByRole("button", { name: /Handlungsgrund/ }).getAttribute("aria-expanded")).toBe("false");
    await userEvent.click(secondButton);
    expect(secondElement.textContent).toBe(fullAction);
    expect(actionElement.textContent).toBe(`${firstSentence}…`);
  });

  it("does not show an expansion button for a short measure", async () => {
    vi.mocked(api.get).mockResolvedValue({ data });
    show();
    await screen.findByRole("article");
    expect(screen.queryByRole("button", { name: "Vollständige Maßnahme anzeigen" })).toBeNull();
  });

  it("can expand an unbroken long description without losing its original prefix", async () => {
    const fullAction = `KI-Vorschlag: ${"A".repeat(400)}`;
    vi.mocked(api.get).mockResolvedValue({ data: { ...data, today_items: [{ ...item, next_action: fullAction }] } });
    show();
    const button = await screen.findByRole("button", { name: "Vollständige Maßnahme anzeigen" });
    const text = document.getElementById(button.getAttribute("aria-controls")!)!;
    expect(text.textContent!.length).toBeLessThanOrEqual(281);
    await userEvent.click(button);
    expect(text.textContent).toBe(fullAction);
  });

  it("shows CF-0008's actual ISO year 0026 and warns without hiding the legacy record", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: {
      ...data, today: "2026-11-18", through: "2026-11-25", today_items: [{
        ...item, key: "case:8", kind: "case", case_id: 8, case_title: "Testfall",
        deadline: "2026-11-30", preparation_date: "2026-11-27", attention_date: "0026-12-31",
        attention_reasons: ["Wiedervorlage am 31.12.0026"],
      }], next_seven_days_items: [],
    } });
    show();
    const card = (await screen.findByRole("link", { name: /CF-0008/ })).closest("article")!;
    expect(within(card).getByText("Handlungsdatum:").parentElement?.textContent).toBe("Handlungsdatum: 31.12.0026");
    expect(within(card).getByText("Frist:").parentElement?.textContent).toBe("Frist: 30.11.2026");
    expect(within(card).getByText("Vorbereitungsbeginn:").parentElement?.textContent).toBe("Vorbereitungsbeginn: 27.11.2026");
    expect(within(card).getByRole("note").textContent).toContain("Datumsjahr prüfen");
  });

  it("renders a real 2026 date without shortening its year or flagging it", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { ...data, today_items: [{ ...item, attention_date: "2026-12-31" }] } });
    show();
    await screen.findByRole("article");
    expect(screen.getByText("Handlungsdatum:").parentElement?.textContent).toBe("Handlungsdatum: 31.12.2026");
    expect(screen.queryByRole("note")).toBeNull();
  });

  it.each(["31.12.26", "2026-02-30"])("marks invalid API date %s without guessing a replacement", async value => {
    vi.mocked(api.get).mockResolvedValue({ data: { ...data, today_items: [{ ...item, attention_date: value }] } });
    show();
    await screen.findByRole("article");
    expect(screen.getByText("Handlungsdatum:").parentElement?.textContent).toBe(`Handlungsdatum: ${value} (Datumsformat prüfen)`);
  });
});
