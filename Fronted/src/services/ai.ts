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

export type ApproveAISuggestionResponse = {
  status: string;
  case_id: number;
  management_summary_created?: boolean;
};

export type ManagementSummaryApprovalPayload = {
  short_case_summary: string | null;
  latest_development: string | null;
  next_required_action: string | null;
  open_deadline: string | null;
  deadline_comment: string | null;

  // Needed by KITab.tsx
  risk: RiskLevel | null;
  risk_comment: string | null;

  relevant_document_ids: number[];
};

export type ManagementSummaryApprovalResponse = {
  status: string;
  case_id: number;
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
): Promise<ApproveAISuggestionResponse> {
  const { data } = await api.post<ApproveAISuggestionResponse>(
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
): Promise<ManagementSummaryApprovalResponse> {
  const { data } = await api.post<ManagementSummaryApprovalResponse>(
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

export type DocumentCaseDraft = {
  title: string;
  company: string | null;
  department: string | null;
  category:
    | "Customer"
    | "Contract"
    | "Supplier"
    | "Employee"
    | "Project"
    | "Other";
  external_contact: string | null;
  description: string | null;
  management_summary: string | null;
  next_action: string | null;
  primary_deadline: string | null;
  financial_amount: number | null;
};

export type DocumentCaseCandidate = {
  case_id: number;
  title: string;
  company: string | null;
  category: string | null;
  similarity: number | null;
};

export type DocumentCaseRouteSuggestion = {
  document_id: number;
  decision: "existing_case" | "new_case" | "uncertain";
  suggested_case_id: number | null;
  confidence: number;
  reason: string;
  new_case: DocumentCaseDraft | null;
  candidates: DocumentCaseCandidate[];
};

export type DocumentCaseRouteConfirmation = {
  action: "assign_existing" | "create_new";
  case_id?: number | null;
  new_case?: DocumentCaseDraft | null;
};

export type DocumentCaseRouteConfirmationResponse = {
  document_id: number;
  case_id: number;
  action: string;
  message: string;
};

export async function suggestDocumentCase(
  documentId: number,
): Promise<DocumentCaseRouteSuggestion> {
  const { data } = await api.post<DocumentCaseRouteSuggestion>(
    `/documents/${documentId}/suggest-case`,
    undefined,
    { timeout: AI_TIMEOUT_MS },
  );

  return data;
}

export async function confirmDocumentCaseRoute(
  documentId: number,
  payload: DocumentCaseRouteConfirmation,
): Promise<DocumentCaseRouteConfirmationResponse> {
  const { data } = await api.post<DocumentCaseRouteConfirmationResponse>(
    `/documents/${documentId}/confirm-case-route`,
    payload,
    { timeout: AI_TIMEOUT_MS },
  );

  return data;
}