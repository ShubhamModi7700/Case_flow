export type RiskLevel = "Low" | "Medium" | "High";

export type CaseStatus =
  | "New"
  | "Under Review"
  | "In Progress"
  | "Waiting"
  | "Completed"
  | "Critical";

export type CaseCategory =
  | "Customer"
  | "Contract"
  | "Supplier"
  | "Employee"
  | "Project"
  | "Other";

export interface CaseItem {
  id: number;
  title: string;
  category: CaseCategory;
  company_department: string | null;
  external_contact: string | null;
  responsible_person: string | null;
  status: CaseStatus;
  risk: RiskLevel;
  description: string | null;
  next_action: string | null;
  primary_deadline: string | null;
  follow_up_date: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export function formatCaseNumber(id: number): string {
  return `CF-${String(id).padStart(4, "0")}`;
}
