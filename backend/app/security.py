import hashlib
import math
import re
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


class Throttle:
    """Espera creciente tras fallos seguidos, por clave (IP o usuario). En memoria: hay un solo proceso.

    Los primeros `free` fallos no esperan; después, `base` segundos, el doble, el doble... hasta `cap`.
    Un acierto lo pone a cero; los fallos de hace más de `window` segundos se olvidan.
    """

    def __init__(self, free: int = 5, base: int = 30, cap: int = 3600, window: int = 86400, clock=time.monotonic):
        self.free, self.base, self.cap, self.window = free, base, cap, window
        self._clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        attempts = self._failures[key]
        limit = self._clock() - self.window
        while attempts and attempts[0] < limit:
            attempts.popleft()
        return attempts

    def retry_after(self, key: str) -> int:
        attempts = self._prune(key)
        if len(attempts) < self.free:
            return 0
        wait = min(self.cap, self.base * 2 ** (len(attempts) - self.free))
        return max(0, math.ceil(attempts[-1] + wait - self._clock()))

    def fail(self, key: str) -> None:
        attempts = self._prune(key)
        attempts.append(self._clock())
        while len(attempts) > 64:
            attempts.popleft()
        if len(self._failures) > 20000:
            # Muchas claves distintas (alguien probando usuarios al azar): se olvidan las que ya no cuentan.
            for stale in [k for k, v in self._failures.items() if not v or v[-1] < self._clock() - self.cap]:
                self._failures.pop(stale, None)

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


class RateLimit:
    """Como mucho `limit` eventos por clave en `window` segundos (p. ej. solicitudes de cuenta por IP)."""

    def __init__(self, limit: int, window: int, clock=time.monotonic):
        self.limit, self.window = limit, window
        self._clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        events = self._events[key]
        limit = self._clock() - self.window
        while events and events[0] < limit:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(self._clock())
        return True


login_throttle = Throttle()
register_limit = RateLimit(limit=5, window=3600)

USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$")
MIN_PASSWORD = 10
COMMON_PASSWORDS = frozenset(
    {
        "1234567890",
        "12345678910",
        "123456789012",
        "0123456789",
        "1111111111",
        "contraseña",
        "contrasena",
        "contraseña1",
        "password123",
        "password1234",
        "qwertyuiop",
        "qwerty12345",
        "asdfghjkl1",
        "iloveyou12",
        "kcalia1234",
        "abcdefghij",
        "abc1234567",
    }
)


def username_problem(username: str) -> str | None:
    if not USERNAME_RE.fullmatch(username):
        return "El usuario debe tener de 3 a 32 caracteres: letras sin tildes, números, punto, guion o guion bajo."
    return None


def password_problem(username: str, password: str) -> str | None:
    if len(password) < MIN_PASSWORD:
        return f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres."
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS or len(set(password)) < 4:
        return "Esa contraseña es demasiado fácil de adivinar. Prueba con una frase o mezcla palabras y números."
    if username and username.lower() in lowered:
        return "La contraseña no puede contener tu nombre de usuario."
    return None


# Hash de una contraseña cualquiera: se verifica contra él cuando el usuario no existe, para que la respuesta
# tarde lo mismo exista o no (sin pistas por el tiempo de respuesta).
DUMMY_HASH = _hasher.hash("kcalia-usuario-inexistente")
