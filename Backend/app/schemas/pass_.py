"""Pass models. Underscored because `pass` is a keyword."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class QrPayload(BaseModel):
    """Exactly what a QR encodes.

    visit_id and nonce, nothing else. No visitor data, no zone list, and above
    all no time window - all of it is read fresh from the record at scan time.
    """

    visit_id: str
    nonce: str


class PassOut(BaseModel):
    """A pass ready for QR encoding, plus the fallback code.

    `qr` is the object to encode. `code6` is what a visitor reads out over the
    phone when their handset cannot show a QR at all.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    visit_id: str
    code6: str
    issued_at: datetime
    revoked_at: datetime | None = None
    is_revoked: bool

    qr: dict


class ScanCredentials(BaseModel):
    """Either half of the two ways to present a pass.

    Every scan endpoint accepts a signed payload OR the 6-digit code - the same
    service path, two lookups.
    """

    payload: QrPayload | None = None
    signature: str | None = None
    code6: str | None = None
