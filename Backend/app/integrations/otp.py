"""OTP send/verify stub.

Signature correct, implementation fake. send_otp logs a code and returns it;
verify_otp accepts ANY six digits, whatever was sent. Real deployment swaps the
body of these two functions for an SMS gateway call and changes nothing else.
"""

import logging
import random

log = logging.getLogger(__name__)

OTP_LENGTH = 6


def send_otp(phone: str) -> str:
    """Pretend to text a code, and return it.

    Returning the code is what makes the prototype demoable - there is no phone
    to read it off. A real gateway would return a delivery receipt, not the
    code, and the endpoint would stop echoing it.
    """
    code = f"{random.randint(0, 10 ** OTP_LENGTH - 1):0{OTP_LENGTH}d}"
    log.info("OTP for %s is %s (stub - not actually sent)", phone, code)
    return code


def verify_otp(phone: str, code: str) -> bool:
    """Accept any six digits.

    Nothing is stored between send and verify, so any correctly shaped code
    passes. That is the documented stub behaviour, not an oversight.
    """
    ok = len(code) == OTP_LENGTH and code.isdigit()
    log.info("OTP check for %s: %s -> %s", phone, code, "accepted" if ok else "rejected")
    return ok
