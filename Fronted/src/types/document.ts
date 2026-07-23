export interface DocumentItem {
  id: number;
  case_id: number;
  file_name: string;
  content_type: string;
  file_size: number;
  description: string | null;
  uploaded_by: string | null;
  uploaded_at: string;
}
