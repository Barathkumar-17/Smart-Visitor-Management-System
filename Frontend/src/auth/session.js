/**
 * The token is the only global state in this app, so it lives outside React.
 * api/client.js reads it directly, which means a request fired from a child
 * effect can never run before a provider has finished wiring itself up.
 */
const KEY = 'svms.auth';

function readStored() {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const stored = JSON.parse(raw);
    if (!stored?.token) return null;
    // Tokens last 12 hours. An expired one is worth dropping now rather than
    // letting the first request of the session fail with a 401.
    if (stored.expires_at) {
      const expiry = Date.parse(stored.expires_at);
      if (!Number.isNaN(expiry) && expiry <= Date.now()) return null;
    }
    return stored;
  } catch {
    return null;
  }
}

let current = readStored();
const listeners = new Set();

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getSession() {
  return current;
}

export function setSession(session) {
  current = session;
  try {
    if (session) window.localStorage.setItem(KEY, JSON.stringify(session));
    else window.localStorage.removeItem(KEY);
  } catch {
    // A browser refusing storage is not a reason to fail the login.
  }
  listeners.forEach((listener) => listener());
}

export function clearSession() {
  setSession(null);
}
