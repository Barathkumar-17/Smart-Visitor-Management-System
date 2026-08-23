import { createContext, useCallback, useContext, useMemo, useSyncExternalStore } from 'react';
import * as session from './session';
import * as authApi from '../api/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const auth = useSyncExternalStore(session.subscribe, session.getSession, session.getSession);

  const login = useCallback(async (username, password) => {
    const res = await authApi.login(username, password);
    session.setSession({
      token: res.token,
      role: res.role,
      name: res.name,
      username: res.username,
      expires_at: res.expires_at,
    });
    return res;
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
      login,
      logout,
    }),
    [auth, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>');
  return value;
}
