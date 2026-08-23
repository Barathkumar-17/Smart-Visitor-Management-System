import { get } from './client';

export function getPass(visitId) {
  return get(`/passes/${visitId}`);
}
