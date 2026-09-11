import api from "../api";
import type {
  AISuggestion,
  CaseAISummary,
  CaseStatus,
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
  document_facts: string[];
  interpretation: string | null;
  responsible_role: string | null;
  action_justification: string | null;
  uncertainty_notes: string[];
  latest_development: string | null;
  next_required_action: string | null;
  open_deadline: string | null;
  deadline_comment: string | null;

  // Needed by KITab.tsx
  risk: RiskLevel | null;
  risk_comment: string | null;
  status: CaseStatus | null;
  status_reason: string | null;

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

export async function getLatestApprovedManagementSummary(
  caseId: number,
): Promise<CaseAISummary | null> {
  const { data } = await api.get<CaseAISummary | null>(
    `/cases/${caseId}/management-summaries/latest-approved`,
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
export type AssistantTaskType = "question" | "chronology" | "evidence" | "entities" | "brief_evidence";

export type AssistantBriefContext = {
  client: string;
  role: string | null;
  recipient: string | null;
  document_type: string;
  objective: string;
  additional_instructions: string | null;
};

export type AssistantEvidenceStatement = {
  text: string;
  source_ids: string[];
};

export type AssistantChronologyEvent = {
  date: string | null;
  event: string;
  source_ids: string[];
};

export type AssistantEvidenceLink = {
  claim: string;
  relevance: string | null;
  source_ids: string[];
};

export type AssistantEntity = {
  name: string;
  entity_type: "Person" | "Unternehmen" | "Organisation" | "Unbekannt";
  role: string | null;
  role_is_explicit: boolean;
  source_ids: string[];
};

export type AssistantBriefEvidencePackage = {
  task_summary: string | null;
  established_facts: AssistantEvidenceStatement[];
  key_evidence: AssistantEvidenceLink[];
  relevant_events: AssistantChronologyEvent[];
  relevant_entities: AssistantEntity[];
  open_issues: string[];
};

export type AssistantSource = {
  source_id: string;
  chunk_id: number;
  document_id: number;
  filename: string;
  document_date: string | null;
  sender: string | null;
  page_number: number | null;
  sheet_name: string | null;
  email_section: string | null;
  is_attachment: boolean;
  parent_filename: string | null;
  root_email_filename: string | null;
  attachment_depth: number;
};

export type CaseAssistantResponse = {
  task_type: AssistantTaskType;
  answer: string;
  claims: AssistantEvidenceStatement[];
  contradictions: AssistantEvidenceStatement[];
  missing_information: string[];
  unsupported_statements: string[];
  chronology: AssistantChronologyEvent[];
  evidence: AssistantEvidenceLink[];
  entities: AssistantEntity[];
  brief_evidence_package: AssistantBriefEvidencePackage | null;
  sources: AssistantSource[];
};

export async function queryCaseAssistant(
  caseId: number,
  question: string,
  taskType: AssistantTaskType = "question",
  briefContext?: AssistantBriefContext,
): Promise<CaseAssistantResponse> {
  const { data } = await api.post<CaseAssistantResponse>(
    `/cases/${caseId}/assistant/query`,
    { question, task_type: taskType, brief_context: briefContext ?? null },
    { timeout: AI_TIMEOUT_MS },
  );

  return data;
}
