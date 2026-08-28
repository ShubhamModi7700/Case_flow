import type { CaseAccessInput, CaseCategory, CaseStatus, RiskLevel } from "../../types";

export type TabName =
  | "overview"
  | "tasks"
  | "documents"
  | "timeline"
  | "KI";

/**
 * PATCH payload: every property is optional because Users and Managers are
 * allowed to submit different subsets of fields.
 */
export interface CaseUpdatePayload {
  title?: string;
  company?: string | null;
  department?: string | null;
  category?: CaseCategory;
  external_contact?: string | null;
  responsible_person?: string | null;
  status?: CaseStatus;

  risk?: RiskLevel;
  risk_reason?: string | null;
  risk_is_manual?: boolean;

  management_summary?: string | null;
  financial_amount?: number | null;
  description?: string | null;
  next_action?: string | null;
  primary_deadline?: string | null;
  follow_up_date?: string | null;
  access?: CaseAccessInput[];
}