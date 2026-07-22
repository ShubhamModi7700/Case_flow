export interface DocumentItem {
  id: number;
  case_id: number;
  file_name: string;
  description: string | null;
  uploaded_by: string | null;
  uploaded_at: string;
}
