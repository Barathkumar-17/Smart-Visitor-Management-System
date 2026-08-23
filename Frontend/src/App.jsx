import { Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom';
import { useAuth } from './auth/AuthContext';
import RoleGate, { homeFor, roleAllows } from './auth/RoleGate';
import Login from './pages/Login';
import GuardPage from './pages/GuardPage';
import FacultyPage from './pages/FacultyPage';
import VisitorPage from './pages/VisitorPage';

const NAV = [
  { to: '/visitor', label: 'Visitor', allow: 'any' },
  { to: '/faculty', label: 'Faculty', allow: 'faculty' },
  { to: '/guard', label: 'Guard', allow: 'guard' },
];

function TopBar() {
  const { auth, role, name, logout } = useAuth();
  const navigate = useNavigate();

  if (!auth) return null;

  async function onLogout() {
    await logout();
    navigate('/login', { replace: true });
  }

  return (
    <header className="topbar">
      <nav>
        {NAV.filter((item) => roleAllows(role, item.allow)).map((item) => (
          <NavLink key={item.to} to={item.to}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="topbar-identity">
        <span>
          {name} <span className="role-chip">{role}</span>
        </span>
        <button type="button" className="link-button" onClick={onLogout}>
          Sign out
        </button>
      </div>
    </header>
  );
}

function Landing() {
  const { auth, role } = useAuth();
  return <Navigate to={auth ? homeFor(role) : '/login'} replace />;
}

export default function App() {
  return (
    <>
      <TopBar />
      <main>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/visitor"
            element={
              <RoleGate allow="any">
                <VisitorPage />
              </RoleGate>
            }
          />
          <Route
            path="/faculty"
            element={
              <RoleGate allow="faculty">
                <FacultyPage />
              </RoleGate>
            }
          />
          <Route
            path="/guard"
            element={
              <RoleGate allow="guard">
                <GuardPage />
              </RoleGate>
            }
          />
          <Route path="*" element={<Landing />} />
        </Routes>
      </main>
    </>
  );
}
