import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { api } from "../src/api";
import Dashboard from "../src/pages/Dashboard";
import type { DashboardData } from "../src/types/dashboard";

vi.mock("../src/api", () => ({ api: { get: vi.fn() } }));

const summary: DashboardData = {
  open_cases: 8, completed_cases: 2, low_risk_cases: 3, medium_risk_cases: 3,
  high_risk_cases: 2, overdue_deadlines: 1, upcoming_deadlines: 4,
  cases_without_responsible: 1, cases_without_next_action: 1,
  pending_ai_suggestions: 2, pending_management_summaries: 1, documents_ready_for_ai: 5,
  next_due_actions: [], attention_items: [{
    case_id: 1, title: "Bestehender Fall", reason: "Hohes Risiko", risk: "High",
    next_action: null, has_pending_ai_action: true, responsible_person: "Anna",
    deadline: "2026-11-20",
  }],
};

beforeEach(() => { vi.mocked(api.get).mockReset(); });
afterEach(cleanup);

describe("dashboard with prioritized measures", () => {
  it("preserves KPI links and shows the renamed worklist", async () => {
    vi.mocked(api.get).mockImplementation(async url => {
      if (url === "/dashboard/summary") return { data: summary };
      if (url === "/dashboard/worklist") return { data: {
        today: "2026-11-17", through: "2026-11-24", timezone: "Europe/Berlin",
        preparation_lead_days: 3, today_items: [], next_seven_days_items: [],
      } };
      throw new Error(`Unexpected request: ${url}`);
    });
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Meine Übersicht" })).toBeTruthy();
    for (const [name, href] of [
      [/Kritisch/, "/cases?risk=High"],
      [/Überfällig/, "/cases?overdue=true"],
      [/Ohne Zuständigkeit/, "/cases?missing_owner=true"],
      [/Maßnahme fehlt/, "/cases?missing_next_action=true"],
      [/Fall anlegen/, "/cases/new"],
    ] as const) expect(screen.getByRole("link", { name }).getAttribute("href")).toBe(href);
    expect(await screen.findByRole("heading", { name: "Priorisierte Maßnahmen" })).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Kommende 7 Tage (0)" }));
    expect(screen.getByText(/Keine zusätzlichen Maßnahmen/)).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Handlungsbedarf" })).toBeNull();
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  it("keeps the existing KPIs usable when the worklist request fails", async () => {
    vi.mocked(api.get).mockImplementation(async url => {
      if (url === "/dashboard/summary") return { data: summary };
      throw new Error("Worklist unavailable");
    });
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    await screen.findByRole("alert");
    expect(screen.getByRole("heading", { name: "Meine Übersicht" })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Überfällig/ })).toBeTruthy();
  });
});
