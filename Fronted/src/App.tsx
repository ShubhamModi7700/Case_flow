import {
  BrowserRouter,
  NavLink,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";

import {
  AuthProvider,
  useAuth,
} from "./AuthContext";
import ProtectedRoute from "./ProtectedRoute";

import CaseDetail from "./pages/CaseDetail";
import CaseList from "./pages/CaseList";
import CreateCase from "./pages/CreateCase";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Users from "./pages/Users";

function navClass({
  isActive,
}: {
  isActive: boolean;
}): string {
  return [
    "block rounded-xl px-4 py-3 text-sm font-medium transition",
    isActive
      ? "bg-slate-100 text-slate-950"
      : "text-slate-600 hover:bg-slate-50 hover:text-slate-950",
  ].join(" ");
}

function ApplicationLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout(): Promise<void> {
    await logout();

    navigate("/login", {
      replace: true,
    });
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 z-20 flex w-64 flex-col border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 p-5">
          <h1 className="font-bold text-slate-950">
            Case Flow
          </h1>
        </div>

        <nav className="flex-1 space-y-2 p-4">
          <NavLink
            to="/"
            end
            className={navClass}
          >
            Dashboard
          </NavLink>

          <NavLink
            to="/cases"
            className={navClass}
          >
            Cases
          </NavLink>

          <NavLink
            to="/cases/new"
            className={navClass}
          >
            Create Case
          </NavLink>

          {user?.role === "Admin" && (
            <NavLink
              to="/users"
              className={navClass}
            >
              Users
            </NavLink>
          )}
        </nav>

        <div className="border-t border-slate-200 p-4">
          <p className="truncate text-sm font-medium text-slate-800">
            {user?.full_name}
          </p>

          <p className="mt-1 truncate text-xs text-slate-400">
            {user?.email}
          </p>

          <p className="mt-1 text-xs text-slate-400">
            {user?.role}
          </p>

          <button
            type="button"
            onClick={() => {
              void handleLogout();
            }}
            className="mt-4 w-full rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="ml-64 min-h-screen">
        <Routes>
          <Route
            path="/"
            element={<Dashboard />}
          />

          <Route
            path="/cases"
            element={<CaseList />}
          />

          <Route
            path="/cases/new"
            element={<CreateCase />}
          />

          <Route
            path="/cases/:caseId"
            element={<CaseDetail />}
          />

          {user?.role === "Admin" && (
            <Route
              path="/users"
              element={<Users />}
            />
          )}
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route
            path="/login"
            element={<Login />}
          />

          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <ApplicationLayout />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}