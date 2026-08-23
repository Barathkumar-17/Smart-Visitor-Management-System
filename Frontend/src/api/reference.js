import { get } from './client';

export function getZones() {
  return get('/zones');
}

export function getHosts() {
  return get('/hosts');
}
