import { getSession, clearSession } from '../auth/session';

const BASE = '/api';

/**
 * Every failure that leaves this module is an ApiError with a `code` and a
 * `message`, whichever shape the backend used. Nothing downstream branches on
 * whether it was a domain error or a FastAPI validation error.
 */
export class ApiError extends Error {
  constructor({ code, message, detail = null, status = 0 }) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.detail = detail;
    this.status = status;
  }
}

const DEFAULT_MESSAGE = {
  400: 'That request broke a rule.',
  401: 'Your session has ended. Please log in again.',
  403: 'Your role cannot do this.',
  404: 'No such record.',
  409: 'Right request, wrong moment.',
  422: 'The request body was malformed.',
};

function normaliseError(status, body) {
  // Domain errors: {error: {code, message, detail}}
  if (body && typeof body.error === 'object' && body.error !== null) {
    return {
      code: body.error.code || 'Error',
      message: body.error.message || DEFAULT_MESSAGE[status] || `Request failed (${status}).`,
      detail: body.error.detail ?? null,
    };
  }

  // FastAPI validation errors: {detail: [{loc, msg, type}, ...]}
  if (Array.isArray(body?.detail)) {
    const parts = body.detail.map((d) => {
      const field = Array.isArray(d.loc) ? d.loc.slice(1).join('.') : '';
      return field ? `${field}: ${d.msg}` : d.msg;
    });
    return {
      code: 'ValidationError',
      message: parts.join('; ') || DEFAULT_MESSAGE[422],
      detail: body.detail,
    };
  }

  if (typeof body?.detail === 'string') {
    return { code: 'HttpError', message: body.detail, detail: null };
  }

  return {
    code: 'HttpError',
    message: DEFAULT_MESSAGE[status] || `Request failed (${status}).`,
    detail: null,
  };
}

async function readBody(res) {
  if (res.status === 204) return null;
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text.slice(0, 300) };
  }
}

/**
 * @param {string} path       path after /api, e.g. '/auth/login'
 * @param {object} options
 *   method            default GET
 *   body              serialised as JSON when present
 *   auth              default true; false omits the Authorization header
 *   handleUnauthorized  default true; false leaves a 401 to the caller.
 *                     The login screen sets this so a wrong password does not
 *                     look like an expired session.
 */
export async function request(path, { method = 'GET', body, auth = true, handleUnauthorized = true } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  if (auth) {
    const session = getSession();
    if (session?.token) headers.Authorization = `Bearer ${session.token}`;
  }

  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError({
      code: 'NetworkError',
      message: 'Cannot reach the server. Is the backend running on port 8000?',
      status: 0,
    });
  }

  const parsed = await readBody(res);

  if (!res.ok) {
    // 401 is a login problem and 403 is a permissions problem. Only the first
    // one drops the session; a 403 leaves the user exactly where they are.
    if (res.status === 401 && handleUnauthorized) clearSession();
    throw new ApiError({ ...normaliseError(res.status, parsed), status: res.status });
  }

  return parsed;
}

export const get = (path, options) => request(path, { ...options, method: 'GET' });
export const post = (path, body, options) => request(path, { ...options, method: 'POST', body });
export const patch = (path, body, options) => request(path, { ...options, method: 'PATCH', body });
