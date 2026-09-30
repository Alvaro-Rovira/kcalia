import hashlib
import secrets
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

SESSION_COOKIE = "kcalia_session"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def new_session_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LoginThrottle:
    """Bloqueo temporal por IP tras varios fallos seguidos. En memoria: basta para un usuario."""

    def __init__(self, max_failures: int = 5, window_seconds: int = 600):
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, ip: str) -> deque[float]:
        attempts = self._failures[ip]
        limit = time.monotonic() - self.window
        while attempts and attempts[0] < limit:
            attempts.popleft()
        return attempts

    def retry_after(self, ip: str) -> int:
        attempts = self._prune(ip)
        if len(attempts) < self.max_failures:
            return 0
        return max(1, int(attempts[0] + self.window - time.monotonic()))

    def fail(self, ip: str) -> None:
        self._prune(ip).append(time.monotonic())

    def reset(self, ip: str) -> None:
        self._failures.pop(ip, None)


login_throttle = LoginThrottle()
