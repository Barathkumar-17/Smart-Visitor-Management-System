import { get, post } from './client';

export function getVisitor(id) {
  return get(`/visitors/${id}`);
}

export function createVisitor(body) {
  return post('/visitors', body);
}

export function sendOtp(id) {
  return post(`/visitors/${id}/otp/send`, {});
}

export function verifyOtp(id, code) {
  return post(`/visitors/${id}/otp/verify`, { code });
}

export function digilocker(id) {
  return post(`/visitors/${id}/digilocker`, {});
}
