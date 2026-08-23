import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

/**
 * Where each role lands after logging in.
 *
 * security has no screen in this build — the dashboards are out of scope — so
 * it lands on /visitor, the one route open to every role. admin satisfies every
 * role check, so it lands on the guard screen and can reach all three.
 */
const HOME_BY_ROLE = {
  guard: '/guard',
  faculty: '/faculty',
  admin: '/guard',
  security: '/visitor',
  visitor: '/visitor',
};

export function homeFor(role) {
  return HOME_BY_ROLE[role] ?? '/visitor';
}

export function roleAllows(role, allow) {
  if (!role) return false;
  if (allow === 'any') return true;
  // admin satisfies every STAFF role check. A visitor never does: that role is
  // an ownership boundary rather than a rung on a ladder.
  if (role === 'visitor') return false;
  if (role === 'admin') return true;
  return Array.isArray(allow) ? allow.includes(role) : role === allow;
}

export default function RoleGate({ allow = 'any', children }) {
  const { auth, role } = useAuth();
  const location = useLocation();

  if (!auth) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (roleAllows(role, allow)) return children;

  const home = homeFor(role);
  if (home === location.pathname) {
    // Only reachable if the table above ever points a role at a route it is not
    // allowed on. Say so rather than bouncing between two redirects forever.
    return (
      <div className="panel">
        <h2>No screen for this role</h2>
        <p>Signed in as {role}, which has no screen in this build.</p>
      </div>
    );
  }

  return <Navigate to={home} replace />;
}
