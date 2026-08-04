export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  role: "Manager" | "User" | "Viewer";
}

export interface LoginResponse {
  message: string;
  user: AuthUser;
}
