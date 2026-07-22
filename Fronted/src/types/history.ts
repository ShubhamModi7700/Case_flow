export interface HistoryItem {
  id: number;
  case_id: number;
  change: string;
  note: string | null;
  responsible_person: string | null;
  created_at: string;
}
