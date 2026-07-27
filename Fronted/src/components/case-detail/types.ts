import type { CaseCategory, CaseStatus, RiskLevel } from "../../types";

export type TabName = "overview" | "tasks" | "documents" | "timeline" | "ai";

export interface CaseUpdatePayload {
  title: string;
  company: string;
  department: string | null;
  category: CaseCategory;
  external_contact: string | null;
  responsible_person: string | null;
  status: CaseStatus;
  risk: RiskLevel;
  description: string | null;
  next_action: string | null;
  primary_deadline: string | null;
  follow_up_date: string | null;
}
