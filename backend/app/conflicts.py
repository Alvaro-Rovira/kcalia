"""Escrituras simultáneas que chocan en SQLite.

Muchas escrituras comprueban si algo existe y, si no, lo crean (el plato conocido de una comida, las preferencias, el
uso diario de IA...). Si dos peticiones lo hacen a la vez, las dos ven que no existe y la segunda choca con el índice
UNIQUE: era un 500 y lo escrito se perdía. Este middleware repite la petición entera (hasta tres veces): el intento
fallido se deshizo completo con su transacción y el siguiente ya ve lo que creó la otra petición.

Solo se repiten escrituras que aún no han empezado a responder; las lecturas no chocan.
"""

import asyncio

from sqlalchemy.exc import IntegrityError

WRITES = {"POST", "PUT", "PATCH", "DELETE"}
ATTEMPTS = 3


class RetryOnConflict:
    def __init__(self, app, max_body: int = 16 * 1024 * 1024):
        self.app = app
        self.max_body = max_body

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in WRITES:
            await self.app(scope, receive, send)
            return
        # El cuerpo se guarda para poder repetir la petición (no se puede leer dos veces del cliente).
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return  # el cliente se ha ido antes de terminar de enviar
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_body:
                await _too_large(send)
                return
            chunks.append(chunk)
            if not message.get("more_body"):
                break
        body = b"".join(chunks)

        for attempt in range(1, ATTEMPTS + 1):
            delivered = False
            started = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            async def tracked_send(message):
                nonlocal started
                if message["type"] == "http.response.start":
                    started = True
                await send(message)

            try:
                await self.app(scope, replay, tracked_send)
                return
            except IntegrityError:
                if started or attempt == ATTEMPTS:
                    raise
                await asyncio.sleep(0.02 * attempt)


async def _too_large(send) -> None:
    body = b'{"detail":"Lo que intentas enviar es demasiado grande."}'
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    await send({"type": "http.response.start", "status": 413, "headers": headers})
    await send({"type": "http.response.body", "body": body})
