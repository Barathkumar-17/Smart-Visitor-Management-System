import { get, post } from './client';

// GET /visits (the list) is faculty-only and 403s a guard. Fetching one visit
// by id is open to any role, which is what the guard picker relies on.
export function getVisit(id) {
  return get(`/visits/${id}`);
}

export function listVisits(params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
  ).toString();
  return get(`/visits${query ? `?${query}` : ''}`);
}

export function createVisit(body) {
  return post('/visits', body);
}

export function approveVisit(id, body) {
  return post(`/visits/${id}/approve`, body);
}

export function rejectVisit(id, reason) {
  return post(`/visits/${id}/reject`, { reason });
}

export function arrivalAck(id, body = {}) {
  return post(`/visits/${id}/arrival-ack`, body);
}
