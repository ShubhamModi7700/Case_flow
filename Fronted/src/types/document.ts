export interface DocumentItem {
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
}
