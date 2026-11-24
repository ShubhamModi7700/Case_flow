import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CaseAssistant from "../src/components/case-detail/assistant/CaseAssistant";
import { getCaseChat, type AssistantSource, type CaseAssistantResponse, type ChatMessage } from "../src/services/ai";

vi.mock("../src/services/ai", async (importOriginal) => {
  const original = await importOriginal<typeof import("../src/services/ai")>();
  return { ...original, getCaseChat: vi.fn() };
});

function source(id: string, filename: string): AssistantSource {
  return {
    source_id: id, chunk_id: 1, document_id: 1, filename,
    document_date: null, sender: null, page_number: 1,
    sheet_name: null, email_section: null, is_attachment: false,
    parent_filename: null, root_email_filename: null, attachment_depth: 0,
  };
}

function answer(id: number, filename: string): ChatMessage {
  return {
    id, role: "assistant", content: `Belegte Aussage [S6]`,
    response: { sources: [source("S6", filename)], claims: [] } as unknown as CaseAssistantResponse,
  };
}

beforeEach(() => {
  vi.mocked(getCaseChat).mockReset();
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(cleanup);

describe("KI-Chat citation navigation", () => {
  it("expands the source disclosure, scrolls to and highlights the clicked source", async () => {
    vi.mocked(getCaseChat).mockResolvedValue([answer(101, "Brief.pdf")]);
    const user = userEvent.setup();
    render(<CaseAssistant caseId={12} />);

    const citation = await screen.findByRole("button", { name: "Quelle S6 anzeigen: Brief.pdf" });
    const sourceEntry = document.getElementById("chat-101-source-S6");
    expect(sourceEntry).not.toBeNull();
    const disclosure = sourceEntry!.closest("details") as HTMLDetailsElement;
    if (disclosure.open) await user.click(within(disclosure).getByText("Quellen anzeigen (1)"));
    expect(disclosure.open).toBe(false);

    await user.click(citation);
    expect(disclosure.open).toBe(true);
    expect(sourceEntry!.className).toContain("bg-blue-100");
    expect(sourceEntry!.className).toContain("ring-blue-500");
    expect(sourceEntry!.getAttribute("tabindex")).toBe("-1");
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "nearest" });
    expect(document.activeElement).toBe(sourceEntry);
  });

  it("keeps reused source IDs scoped to their own chat answer", async () => {
    vi.mocked(getCaseChat).mockResolvedValue([answer(201, "First.pdf"), answer(202, "Second.pdf")]);
    const user = userEvent.setup();
    render(<CaseAssistant caseId={12} />);

    const firstCitation = await screen.findByRole("button", { name: "Quelle S6 anzeigen: First.pdf" });
    const secondCitation = screen.getByRole("button", { name: "Quelle S6 anzeigen: Second.pdf" });
    const firstEntry = document.getElementById("chat-201-source-S6")!;
    const secondEntry = document.getElementById("chat-202-source-S6")!;

    await user.click(firstCitation);
    expect(firstEntry.className).toContain("bg-blue-100");
    expect(secondEntry.className).not.toContain("bg-blue-100");

    await user.click(secondCitation);
    expect(secondEntry.className).toContain("bg-blue-100");
    expect(firstEntry.className).not.toContain("bg-blue-100");
  });
});
