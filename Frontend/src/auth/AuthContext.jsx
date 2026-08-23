import { createContext, useCallback, useContext, useMemo, useSyncExternalStore } from 'react';
import * as session from './session';
import * as authApi from '../api/auth';

function store(res) {
  session.setSession({
    token: res.token,
    role: res.role,
    name: res.name,
    username: res.username,
    expires_at: res.expires_at,
    // Only set for role "visitor" — the Visitor record this account speaks for.
    visitor_id: res.visitor_id ?? null,
  });
  return res;
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const auth = useSyncExternalStore(session.subscribe, session.getSession, session.getSession);

  const login = useCallback(async (username, password) => {
    return store(await authApi.login(username, password));
  }, []);

  const registerVisitor = useCallback(async (body) => {
    // Sign-up logs the new account straight in, so there is no second step.
    return store(await authApi.registerVisitor(body));
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // The token is gone from this browser either way.
    }
    session.clearSession();
  }, []);

  const value = useMemo(
    () => ({
      auth,
      isAuthenticated: Boolean(auth),
      role: auth?.role ?? null,
      name: auth?.name ?? null,
      visitorId: auth?.visitor_id ?? null,
      login,
      registerVisitor,
      logout,
    }),
    [auth, login, registerVisitor, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>');
  return value;
}
