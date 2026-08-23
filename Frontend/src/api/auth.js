import { post, get } from './client';

export function login(username, password) {
  // A 401 here means a wrong username or password, not a dead session, so it
  // must not clear auth state on its way out.
  return post('/auth/login', { username, password }, { auth: false, handleUnauthorized: false });
}

// The only endpoint that works without a token. A member of the public has no
// credentials and nobody to ask for any, so this is the way in.
export function registerVisitor(body) {
  return post('/auth/visitor/register', body, { auth: false, handleUnauthorized: false });
}

export function logout() {
  return post('/auth/logout');
}

export function me() {
  return get('/auth/me');
}
