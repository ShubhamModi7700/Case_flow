import { useState } from "react";
import {
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";

import { useAuth } from "../AuthContext";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");

  const [password, setPassword] =
    useState("");

  const [submitting, setSubmitting] =
    useState(false);

  const [error, setError] = useState("");

  if (user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    try {
      setSubmitting(true);
      setError("");

      await login(email, password);

      const state = location.state as {
        from?: string;
      } | null;

      navigate(state?.from ?? "/", {
        replace: true,
      });
    } catch {
      setError("Incorrect email or password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-6">
      <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 shadow-xl">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-950 font-bold text-white">
          CF
        </div>

        <h1 className="mt-6 text-3xl font-bold">
          Sign in
        </h1>

        <p className="mt-2 text-sm text-slate-500">
          Sign in to access Case Flow.
        </p>

        {error && (
          <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="mt-7 space-y-5"
        >
          <label className="block">
            <span className="mb-2 block text-sm font-medium">
              Email
            </span>

            <input
              type="email"
              required
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              className="input"
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-medium">
              Password
            </span>

            <input
              type="password"
              required
              value={password}
              onChange={(event) =>
                setPassword(event.target.value)
              }
              className="input"
            />
          </label>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-slate-950 px-5 py-3 font-semibold text-white disabled:opacity-50"
          >
            {submitting
              ? "Signing in..."
              : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}