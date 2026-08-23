import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { homeFor } from '../auth/RoleGate';
import ErrorBanner from '../components/ErrorBanner';
import { fileToBase64 } from '../lib/fileToBase64';

// Dev only, and worth the screen space: switching roles mid-demo is otherwise
// eight keystrokes and a typo waiting to happen.
const QUICK_LOGINS = [
  { username: 'guard', password: 'guard123', role: 'guard' },
  { username: 'faculty', password: 'faculty123', role: 'faculty' },
  { username: 'security', password: 'security123', role: 'security' },
  { username: 'admin', password: 'admin123', role: 'admin' },
];

/**
 * Two audiences, two doors.
 *
 * Staff have accounts handed to them — four seeded fixtures, no sign-up
 * anywhere in the system. A visitor is the opposite case: they arrive with no
 * credentials and nobody to ask, so they create their own account, and it owns
 * exactly one visitor record.
 */
export default function Login() {
  const { login, registerVisitor } = useAuth();
  const navigate = useNavigate();

  const [audience, setAudience] = useState('visitor');
  const [visitorMode, setVisitorMode] = useState('login');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  // staff
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // visitor
  const [phone, setPhone] = useState('');
  const [vPassword, setVPassword] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [photo, setPhoto] = useState(null);
  const [photoName, setPhotoName] = useState('');

  function land(res) {
    navigate(homeFor(res.role), { replace: true });
  }

  async function run(fn) {
    setBusy(true);
    setError(null);
    try {
      land(await fn());
    } catch (err) {
      // The backend's own 401 message is already readable and deliberately
      // does not say which half failed, so it is shown as-is.
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function pickPhoto(file) {
    setError(null);
    try {
      setPhoto(await fileToBase64(file));
      setPhotoName(file?.name ?? '');
    } catch (err) {
      setPhoto(null);
      setPhotoName('');
      setError(err);
    }
  }

  const staffSubmit = (e) => {
    e.preventDefault();
    run(() => login(username.trim(), password));
  };

  const visitorLogin = (e) => {
    e.preventDefault();
    run(() => login(phone.trim(), vPassword));
  };

  const visitorRegister = (e) => {
    e.preventDefault();
    run(() =>
      registerVisitor({
        name: name.trim(),
        phone: phone.trim(),
        password: vPassword,
        email: email.trim() || undefined,
        photo_b64: photo,
      }),
    );
  };

  return (
    <div className="login-screen">
      <div className="panel login-panel">
        <h1>Smart Visitor Management System</h1>

        <div className="tab-row">
          <button
            type="button"
            className={`tab${audience === 'visitor' ? ' selected' : ''}`}
            onClick={() => {
              setAudience('visitor');
              setError(null);
            }}
          >
            Visitor
          </button>
          <button
            type="button"
            className={`tab${audience === 'staff' ? ' selected' : ''}`}
            onClick={() => {
              setAudience('staff');
              setError(null);
            }}
          >
            Staff
          </button>
        </div>

        <ErrorBanner error={error} onDismiss={() => setError(null)} />

        {audience === 'staff' ? (
          <>
            <p className="muted">
              Guards, faculty, security and admin. These accounts are issued, not created.
            </p>
            <form onSubmit={staffSubmit}>
              <label className="field" htmlFor="login-username">
                <span className="field-label">Username</span>
                <input
                  id="login-username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
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
                    disabled={busy}
                    onClick={() => run(() => login(entry.username, entry.password))}
                  >
                    {entry.role}
                  </button>
                ))}
              </div>
            </div>
          </>
        ) : (
          <>
            <div className="mode-row">
              <button
                type="button"
                className={visitorMode === 'login' ? 'selected' : ''}
                onClick={() => {
                  setVisitorMode('login');
                  setError(null);
                }}
              >
                I have an account
              </button>
              <button
                type="button"
                className={visitorMode === 'register' ? 'selected' : ''}
                onClick={() => {
                  setVisitorMode('register');
                  setError(null);
                }}
              >
                Create one
              </button>
            </div>

            <form onSubmit={visitorMode === 'login' ? visitorLogin : visitorRegister}>
              {visitorMode === 'register' && (
                <label className="field" htmlFor="reg-name">
                  <span className="field-label">Full name</span>
                  <input id="reg-name" value={name} onChange={(e) => setName(e.target.value)} />
                </label>
              )}

              <label className="field" htmlFor="reg-phone">
                <span className="field-label">Phone</span>
                <input
                  id="reg-phone"
                  value={phone}
                  placeholder="+91-98111-22233"
                  onChange={(e) => setPhone(e.target.value)}
                  autoComplete="tel"
                />
                <span className="field-hint">This is your username.</span>
              </label>

              <label className="field" htmlFor="reg-password">
                <span className="field-label">Password</span>
                <input
                  id="reg-password"
                  type="password"
                  value={vPassword}
                  onChange={(e) => setVPassword(e.target.value)}
                  autoComplete={visitorMode === 'login' ? 'current-password' : 'new-password'}
                />
                {visitorMode === 'register' && (
                  <span className="field-hint">At least six characters.</span>
                )}
              </label>

              {visitorMode === 'register' && (
                <>
                  <label className="field" htmlFor="reg-email">
                    <span className="field-label">Email (optional)</span>
                    <input id="reg-email" value={email} onChange={(e) => setEmail(e.target.value)} />
                  </label>

                  <label className="field" htmlFor="reg-photo">
                    <span className="field-label">Photograph</span>
                    <input
                      id="reg-photo"
                      type="file"
                      accept="image/*"
                      onChange={(e) => pickPhoto(e.target.files?.[0])}
                    />
                    <span className="field-hint">
                      {photoName
                        ? `Selected: ${photoName}`
                        : 'The gate shows your face to the guard. Max 2 MB.'}
                    </span>
                  </label>
                </>
              )}

              <button
                type="submit"
                className="primary"
                disabled={
                  busy ||
                  !phone.trim() ||
                  !vPassword ||
                  (visitorMode === 'register' && (!name.trim() || !photo))
                }
              >
                {busy
                  ? 'Please wait…'
                  : visitorMode === 'login'
                    ? 'Sign in'
                    : 'Create account and continue'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
