import { get } from './client';

export function getVisitor(id) {
  return get(`/visitors/${id}`);
}
