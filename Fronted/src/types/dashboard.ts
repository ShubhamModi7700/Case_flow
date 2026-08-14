export interface DashboardAction {
  case_id: number;
  title: string;
  next_action: string;
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
}


