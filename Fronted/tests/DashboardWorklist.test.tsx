import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
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
    expect(screen.getByText("17.11.2026")).toBeTruthy();
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
      ...item, responsible_person: null, deadline: null, preparation_date: null,
      next_action: "Nächste Maßnahme festlegen", reasons: ["Verantwortung offen"],
    }] } });
    show();
    expect(await screen.findByText("Keine Frist")).toBeTruthy();
    expect(screen.queryByText("Vorbereitungsbeginn:")).toBeNull();
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
});
