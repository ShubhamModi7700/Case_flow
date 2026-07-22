import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

import { api } from "./api";
import type {
  AuthUser,
  LoginResponse,
} from "./types";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  login: (
    email: string,
    password: string,
  ) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext =
  createContext<AuthContextValue | undefined>(
    undefined,
  );

export function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [user, setUser] =
    useState<AuthUser | null>(null);

  const [loading, setLoading] =
    useState(true);

  useEffect(() => {
    async function loadCurrentUser() {
      try {
        const response =
          await api.get<AuthUser>("/auth/me");

        setUser(response.data);
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    }

    void loadCurrentUser();
  }, []);

  async function login(
    email: string,
    password: string,
  ): Promise<void> {
    const response =
      await api.post<LoginResponse>(
        "/auth/login",
        {
          email,
          password,
        },
      );

    setUser(response.data.user);
  }

  async function logout(): Promise<void> {
    try {
      await api.post("/auth/logout");
    } finally {
      setUser(null);
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider",
    );
  }

  return context;
}