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

export type AuthUser = {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
};

export type LoginResponse = {
  message: string;
  user: AuthUser;
};

export type CaseItem = {
  id: number;
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
  is_archived: boolean;
  created_at: string;
  updated_at: string;
};

export type TaskPriority = "Low" | "Medium" | "High";

export type TaskStatus = "Open" | "Completed";

export type TaskItem = {
  id: number;
  case_id: number | null;
  title: string;
  description: string | null;
  responsible_person: string | null;
  due_date: string | null;
  priority: TaskPriority;
  status: TaskStatus;
  created_at: string;
};

export type HistoryItem = {
  id: number;
  case_id: number;
  change: string;
  note: string | null;
  responsible_person: string | null;
  created_at: string;
};

export type DocumentItem = {
  id: number;
  case_id: number | null;
  file_name: string;
  content_type: string;
  file_size: number;
  description: string | null;
  uploaded_by: string | null;
  uploaded_at: string;
  company?: string | null;
  department?: string | null;
};

export type DashboardAction = {
  case_id: number;
  title: string;
  next_action: string;
  deadline: string | null;
};

export type DashboardData = {
  open_cases: number;
  completed_cases: number;
  low_risk_cases: number;
  medium_risk_cases: number;
  high_risk_cases: number;
  overdue_deadlines: number;
  upcoming_deadlines: number;
  cases_without_responsible: number;
  cases_without_next_action: number;
  next_due_actions: DashboardAction[];
};

export type UserRole = "Admin" | "User";

export type UserItem = {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
};

export type UserCreatePayload = {
  email: string;
  full_name: string;
  password: string;
  role: UserRole;
  is_active: boolean;
};

export type TimelineEventType =
  | "Created"
  | "Completed"
  | "Document"
  | "Note"
  | "Milestone"
  | "Task deadline"
  | "Task"
  | "Archived"
  | "Update";

export type TimelineEvent = {
  id: string;
  case_id: number;
  event_type: TimelineEventType;
  title: string;
  description: string | null;
  occurred_at: string;
  person: string | null;
  is_future: boolean;
};

export type TimelineEventCreatePayload = {
  event_type: "Note" | "Update" | "Milestone";
  title: string;
  description?: string | null;
};

export function formatCaseNumber(id: number): string {
  return `CF-${String(id).padStart(4, "0")}`;
}