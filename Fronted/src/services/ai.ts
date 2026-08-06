import api from "../api";
import type {
  AISuggestion,
  CaseAISummary,
  RiskLevel,
} from "../types";

const AI_TIMEOUT_MS = 120_000;

export type AISuggestionApprovalPayload = {
  selected_case_id: number;
  summary: string | null;
  latest_development: string | null;
  deadline: string | null;
  next_action: string | null;
  risk: RiskLevel | null;
  risk_reason: string | null;
};

export type ManagementSummaryApprovalPayload = {
  short_case_summary: string | null;
  latest_development: string | null;
  next_required_action: string | null;
  open_deadline: string | null;
  deadline_comment: string | null;
  risk_comment: string | null;
  relevant_document_ids: number[];
};

export type DocumentProcessingResult = {
  document_id: number;
  processing_status: string;
  embedding_status: string;
  chunk_count: number;
  processing_error?: string | null;
};

export async function processDocument(
  documentId: number,
): Promise<DocumentProcessingResult> {
  const { data } = await api.post<DocumentProcessingResult>(
    `/documents/${documentId}/process`,
    undefined,
    { timeout: AI_TIMEOUT_MS },
  );
  return data;
}

export async function analyzeDocument(
  documentId: number,
): Promise<AISuggestion> {
  const { data } = await api.post<AISuggestion>(
    `/documents/${documentId}/analyze`,
    undefined,
    { timeout: AI_TIMEOUT_MS },
  );
  return data;
}

export async function getCaseAISuggestions(
  caseId: number,
): Promise<AISuggestion[]> {
  const { data } = await api.get<AISuggestion[]>(
    `/cases/${caseId}/ai-suggestions`,
  );
  return data;
}

export async function approveAISuggestion(
  suggestionId: number,
  payload: AISuggestionApprovalPayload,
): Promise<{ status: string; case_id: number }> {
  const { data } = await api.post<{ status: string; case_id: number }>(
    `/ai-suggestions/${suggestionId}/approve`,
    payload,
    { timeout: AI_TIMEOUT_MS },
  );
  return data;
}

export async function rejectAISuggestion(
  suggestionId: number,
): Promise<{ status: string }> {
  const { data } = await api.post<{ status: string }>(
    `/ai-suggestions/${suggestionId}/reject`,
  );
  return data;
}

export async function generateManagementSummary(
  caseId: number,
): Promise<CaseAISummary> {
  const { data } = await api.post<CaseAISummary>(
    `/cases/${caseId}/management-summary`,
    undefined,
    { timeout: AI_TIMEOUT_MS },
  );
  return data;
}

export async function getManagementSummaries(
  caseId: number,
): Promise<CaseAISummary[]> {
  const { data } = await api.get<CaseAISummary[]>(
    `/cases/${caseId}/management-summaries`,
  );
  return data;
}

export async function approveManagementSummary(
  summaryId: number,
  payload: ManagementSummaryApprovalPayload,
): Promise<{ status: string; case_id: number }> {
  const { data } = await api.post<{ status: string; case_id: number }>(
    `/case-ai-summaries/${summaryId}/approve`,
    payload,
    { timeout: AI_TIMEOUT_MS },
  );
  return data;
}

export async function rejectManagementSummary(
  summaryId: number,
): Promise<{ status: string }> {
  const { data } = await api.post<{ status: string }>(
    `/case-ai-summaries/${summaryId}/reject`,
  );
  return data;
}
