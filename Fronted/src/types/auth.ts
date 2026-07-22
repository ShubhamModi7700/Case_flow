export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
}

export interface LoginResponse {
  message: string;
  user: AuthUser;
}
