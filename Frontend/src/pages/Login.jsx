import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { homeFor } from '../auth/RoleGate';
import ErrorBanner from '../components/ErrorBanner';

// Dev only, and worth the screen space: switching roles mid-demo is otherwise
// eight keystrokes and a typo waiting to happen.
const QUICK_LOGINS = [
  { username: 'guard', password: 'guard123', role: 'guard' },
  { username: 'faculty', password: 'faculty123', role: 'faculty' },
  { username: 'security', password: 'security123', role: 'security' },
  { username: 'admin', password: 'admin123', role: 'admin' },
];

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function attempt(user, pass) {
    setBusy(true);
    setError(null);
    try {
      const res = await login(user, pass);
      navigate(homeFor(res.role), { replace: true });
    } catch (err) {
      // The backend's own 401 message is already readable ("Username or
      // password is wrong.") and deliberately does not say which half failed,
      // so it is shown as-is rather than restated here.
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event) {
    event.preventDefault();
    attempt(username.trim(), password);
  }

  function onQuickLogin(entry) {
    setUsername(entry.username);
    setPassword(entry.password);
    attempt(entry.username, entry.password);
  }

  return (
    <div className="login-screen">
      <div className="panel login-panel">
        <h1>Smart Visitor Management System</h1>
        <p className="muted">Sign in to continue.</p>

        <ErrorBanner error={error} onDismiss={() => setError(null)} />

        <form onSubmit={onSubmit}>
          <label className="field" htmlFor="login-username">
            <span className="field-label">Username</span>
            <input
              id="login-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
            />
          </label>

          <label className="field" htmlFor="login-password">
            <span className="field-label">Password</span>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>

          <button type="submit" className="primary" disabled={busy || !username || !password}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div className="quick-logins">
          <span className="field-label">Quick login (dev)</span>
          <div className="quick-login-row">
            {QUICK_LOGINS.map((entry) => (
              <button
                key={entry.username}
                type="button"
                onClick={() => onQuickLogin(entry)}
                disabled={busy}
              >
                {entry.role}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
