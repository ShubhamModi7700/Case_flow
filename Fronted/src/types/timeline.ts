export interface TimelineEvent {
  id: string;
  case_id: number;
  event_type: string;
  title: string;
  description: string | null;
  person: string | null;
  occurred_at: string;
  is_future: boolean;
}

export interface TimelineEventCreatePayload {
  title: string;
  description: string | null;
  event_type: "Note" | "Update" | "Milestone";
}
