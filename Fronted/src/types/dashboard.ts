export interface DashboardAction {
  case_id: number;
  title: string;
  next_action: string;
  deadline: string | null;
}

export interface DashboardWorkItem {
  key: string;
  kind: "task" | "case";
  case_id: number;
  case_title: string;
  task_id: number | null;
  title: string;
  responsible_person: string | null;
  deadline: string | null;
  preparation_date: string | null;
  attention_date: string | null;
  priority: "overdue" | "urgent" | "normal";
  reasons: string[];
  next_action: string;
}

export interface DashboardWorklistData {
  today: string;
  through: string;
  timezone: string;
  preparation_lead_days: number;
  today_items: DashboardWorkItem[];
  next_seven_days_items: DashboardWorkItem[];
}

export interface DashboardAttentionItem {
  case_id: number;
  title: string;
  reason: string;
  risk: string;
  next_action: string | null;
  has_pending_ai_action?: boolean;
  responsible_person: string | null;
  deadline: string | null;
}

export interface DashboardData {
  open_cases: number;
  completed_cases: number;
  low_risk_cases: number;
  medium_risk_cases: number;
  high_risk_cases: number;
  overdue_deadlines: number;
  upcoming_deadlines: number;
  cases_without_responsible: number;
  cases_without_next_action: number;
  pending_ai_suggestions: number;
  pending_management_summaries: number;
  documents_ready_for_ai: number;
  next_due_actions: DashboardAction[];
  attention_items: DashboardAttentionItem[];
}


