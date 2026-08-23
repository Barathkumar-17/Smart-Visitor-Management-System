import { useEffect, useState } from 'react';
import { createVisitor, getVisitor, sendOtp, verifyOtp, digilocker } from '../api/visitors';
import { useAuth } from '../auth/AuthContext';
import { createVisit, getVisit } from '../api/visits';
import { getPass } from '../api/passes';
import { getHosts } from '../api/reference';
import { fileToBase64 } from '../lib/fileToBase64';
import { toApiDateTime, localInputValue } from '../lib/datetime';
import PeopleInput from '../components/PeopleInput';
import QrDisplay from '../components/QrDisplay';
import ErrorBanner from '../components/ErrorBanner';

/**
 * Register, verify, request a pass, see the QR.
 *
 * The photo is treated as required here even though the backend only demands a
 * name and a phone — the gate screen is the demo and it needs a face.
 */
export default function VisitorPage() {
  // A visitor who signed up already HAS a record — their account owns exactly
  // one. Staff opening this screen do not, so they still see the form.
  const { role, visitorId } = useAuth();
  const isVisitorAccount = role === 'visitor';

  const [visitor, setVisitor] = useState(null);
  const [loadingSelf, setLoadingSelf] = useState(isVisitorAccount);
  const [hosts, setHosts] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  // registration
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [address, setAddress] = useState('');
  const [photo, setPhoto] = useState(null);
  const [photoName, setPhotoName] = useState('');

  // verification
  const [otp, setOtp] = useState(null);
  const [otpEntry, setOtpEntry] = useState('');

  // pass request
  const [hostId, setHostId] = useState('');
  const [purpose, setPurpose] = useState('');
  const [scheduledAt, setScheduledAt] = useState(localInputValue(30));
  const [plate, setPlate] = useState('');
  const [mode, setMode] = useState('named');
  const [companions, setCompanions] = useState([]);
  const [count, setCount] = useState('');

  const [visit, setVisit] = useState(null);
  const [pass, setPass] = useState(null);

  useEffect(() => {
    getHosts()
      .then((rows) => {
        setHosts(rows);
        if (rows.length) setHostId(rows[0].id);
      })
      .catch(setError);
  }, []);

  useEffect(() => {
    if (!isVisitorAccount || !visitorId) return;
    getVisitor(visitorId)
      .then(setVisitor)
      .catch(setError)
      .finally(() => setLoadingSelf(false));
  }, [isVisitorAccount, visitorId]);

  async function pickPhoto(file) {
    setError(null);
    try {
      setPhoto(await fileToBase64(file));
      setPhotoName(file?.name ?? '');
    } catch (err) {
      setPhoto(null);
      setPhotoName('');
      setError(err);
    }
  }

  async function run(fn) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const register = () =>
    run(async () => {
      const created = await createVisitor({
        name: name.trim(),
        phone: phone.trim(),
        email: email.trim() || undefined,
        address: address.trim() || undefined,
        photo_b64: photo,
      });
      setVisitor(created);
    });

  const requestPass = () =>
    run(async () => {
      // companions[] and person_count are mutually exclusive — sending both
      // is a 400, so exactly one is built here.
      const people =
        mode === 'named'
          ? { companions: companions.filter((c) => c.name.trim()).map((c) => ({ name: c.name.trim(), photo_b64: c.photo_b64 })) }
          : { person_count: Number.parseInt(count, 10) || undefined };

      const created = await createVisit({
        visitor_id: visitor.id,
        host_id: hostId,
        purpose: purpose.trim(),
        scheduled_at: toApiDateTime(scheduledAt),
        vehicle_plate: plate.trim() || undefined,
        ...people,
      });
      // The create response omits companions; re-fetch to see them.
      setVisit(await getVisit(created.id).catch(() => created));
    });

  const loadPass = () =>
    run(async () => {
      setPass(await getPass(visit.id));
    });

  if (loadingSelf) {
    return (
      <div className="guard-screen">
        <p className="muted">Loading your details…</p>
      </div>
    );
  }

  /* ---------------- 1. register ---------------- */
  if (!visitor) {
    return (
      <div className="guard-screen">
        <p className="step-label">Step 1 of 3</p>
        <h2 className="step-question">Register a visitor</h2>
        <p className="muted">
          You are signed in as {role}. This registers someone else — a visitor signing up for
          themselves does it from the login screen and never reaches this form.
        </p>
        <ErrorBanner error={error} onDismiss={() => setError(null)} />

        <section className="panel">
          <label className="field" htmlFor="v-name">
            <span className="field-label">Full name</span>
            <input id="v-name" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field" htmlFor="v-phone">
            <span className="field-label">Phone</span>
            <input
              id="v-phone"
              value={phone}
              placeholder="+91-90000-00000"
              onChange={(e) => setPhone(e.target.value)}
            />
          </label>
          <label className="field" htmlFor="v-email">
            <span className="field-label">Email (optional)</span>
            <input id="v-email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field" htmlFor="v-address">
            <span className="field-label">Address (optional)</span>
            <input id="v-address" value={address} onChange={(e) => setAddress(e.target.value)} />
          </label>
          <label className="field" htmlFor="v-photo">
            <span className="field-label">Photograph</span>
            <input
              id="v-photo"
              type="file"
              accept="image/*"
              onChange={(e) => pickPhoto(e.target.files?.[0])}
            />
            <span className="field-hint">
              {photoName ? `Selected: ${photoName}` : 'Required here — the gate screen needs a face. Max 2 MB.'}
            </span>
          </label>

          <button
            type="button"
            className="primary"
            disabled={busy || !name.trim() || !phone.trim() || !photo}
            onClick={register}
          >
            {busy ? 'Registering…' : 'Register'}
          </button>
        </section>
      </div>
    );
  }

  /* ---------------- 3. the pass ---------------- */
  if (pass) {
    return (
      <div className="guard-screen">
        <p className="step-label">Done</p>
        <h2 className="step-question">Your pass</h2>
        <section className="panel">
          <QrDisplay qr={pass.qr} code6={pass.code6} />
          <p className="field-hint">
            Show this at the gate. The code underneath works if the QR will not scan.
          </p>
        </section>
      </div>
    );
  }

  /* ---------------- 2. verify + request ---------------- */
  return (
    <div className="guard-screen">
      <p className="step-label">Step 2 of 3</p>
      <h2 className="step-question">Verify and request a pass</h2>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />

      <section className="panel">
        <h3>
          {visitor.name} <span className={`tier tier-${visitor.tier}`}>{visitor.tier}</span>
        </h3>
        <dl className="detail-grid">
          <dt>Phone</dt>
          <dd>
            {visitor.phone} {visitor.phone_verified ? '✓ confirmed' : '— not confirmed'}
          </dd>
          <dt>Permanent</dt>
          <dd>{visitor.is_permanent ? 'yes' : 'no'}</dd>
        </dl>

        <div className="verify-row">
          <div className="verify-path">
            <h4>DigiLocker</h4>
            <p className="field-hint">Government ID. Returns permanently verified.</p>
            <button
              type="button"
              disabled={busy}
              onClick={() => run(async () => setVisitor(await digilocker(visitor.id)))}
            >
              Verify with DigiLocker
            </button>
          </div>

          <div className="verify-path">
            <h4>Phone OTP</h4>
            <p className="field-hint">There is no SMS gateway, so the code comes back in the response.</p>
            <button
              type="button"
              disabled={busy}
              onClick={() => run(async () => setOtp(await sendOtp(visitor.id)))}
            >
              Send code
            </button>
            {otp && (
              <>
                <p className="otp-code">
                  Code: <strong>{otp.code}</strong>
                </p>
                <div className="gate-form">
                  <label className="field" htmlFor="otp-entry">
                    <span className="field-label">Enter it</span>
                    <input
                      id="otp-entry"
                      inputMode="numeric"
                      maxLength={6}
                      value={otpEntry}
                      onChange={(e) => setOtpEntry(e.target.value.replace(/\D/g, ''))}
                    />
                  </label>
                  <button
                    type="button"
                    disabled={busy || otpEntry.length === 0}
                    onClick={() => run(async () => setVisitor(await verifyOtp(visitor.id, otpEntry)))}
                  >
                    Confirm
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </section>

      {visit ? (
        <section className="panel">
          <div className="verdict verdict-green" role="status">
            <strong className="verdict-headline">Request sent</strong>
            <span className="verdict-reason">
              {visit.id} is {visit.status}. A host has to approve it before a pass exists.
            </span>
          </div>
          <button type="button" className="primary next-button" disabled={busy} onClick={loadPass}>
            {busy ? 'Checking…' : 'Show my pass'}
          </button>
          <p className="field-hint">
            This will fail with a 404 until the host approves — that is the correct answer, not a bug.
          </p>
        </section>
      ) : (
        <section className="panel">
          <h3>Request a pass</h3>
          <label className="field" htmlFor="v-host">
            <span className="field-label">Host</span>
            <select id="v-host" value={hostId} onChange={(e) => setHostId(e.target.value)}>
              {hosts.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name} — {h.department}
                </option>
              ))}
            </select>
          </label>
          <label className="field" htmlFor="v-purpose">
            <span className="field-label">Purpose</span>
            <input id="v-purpose" value={purpose} onChange={(e) => setPurpose(e.target.value)} />
          </label>
          <div className="gate-form">
            <label className="field" htmlFor="v-when">
              <span className="field-label">When</span>
              <input
                id="v-when"
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
              />
            </label>
            <label className="field" htmlFor="v-plate">
              <span className="field-label">Vehicle plate</span>
              <input
                id="v-plate"
                value={plate}
                placeholder="none"
                onChange={(e) => setPlate(e.target.value.toUpperCase())}
              />
            </label>
          </div>

          <div className="field">
            <span className="field-label">Who is coming</span>
            <PeopleInput
              mode={mode}
              onModeChange={setMode}
              companions={companions}
              onCompanions={setCompanions}
              count={count}
              onCount={setCount}
              onError={setError}
            />
          </div>

          <button
            type="button"
            className="primary"
            disabled={busy || !purpose.trim() || !hostId}
            onClick={requestPass}
          >
            {busy ? 'Requesting…' : 'Request the pass'}
          </button>
        </section>
      )}
    </div>
  );
}
