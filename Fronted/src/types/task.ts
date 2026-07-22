export type TaskPriority = "Low" | "Medium" | "High";

export type TaskStatus = "Open" | "Completed";

export interface TaskItem {
  id: number;
  case_id: number;
  title: string;
  description: string | null;
  responsible_person: string | null;
  due_date: string | null;
  priority: TaskPriority;
  status: TaskStatus;
  created_at: string;
}

// Backwards-compatible name if another file already imports CaseTask.
export type CaseTask = TaskItem;

export interface TaskCreatePayload {
  title: string;
  description: string | null;
  responsible_person: string | null;
  due_date: string | null;
  priority: TaskPriority;
  status: TaskStatus;
}
