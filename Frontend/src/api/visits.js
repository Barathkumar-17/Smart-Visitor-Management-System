import { get } from './client';

// GET /visits (the list) is faculty-only and 403s a guard. Fetching one visit
// by id is open to any role, which is what the gate picker relies on.
export function getVisit(id) {
  return get(`/visits/${id}`);
}
