import { post, get } from './client';

export function login(username, password) {
  // A 401 here means a wrong username or password, not a dead session, so it
  // must not clear auth state on its way out.
  return post('/auth/login', { username, password }, { auth: false, handleUnauthorized: false });
}

export function logout() {
  return post('/auth/logout');
}

export function me() {
  return get('/auth/me');
}
