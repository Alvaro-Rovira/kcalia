# Seguridad

## Avisar de un fallo

No abras una issue pública. Usa **Security → Report a vulnerability** en este repositorio (aviso privado de GitHub)
con los pasos para reproducirlo. Se responde en unos días y se avisa cuando esté arreglado.

Las pruebas deben hacerse sobre una instalación propia (`docker compose up`), no sobre kcalia.space ni sobre las
cuentas de otras personas.

## Qué protege la app

| Riesgo | Defensa |
| --- | --- |
| Robo de contraseñas | Argon2, mínimo 10 caracteres, lista de contraseñas comunes |
| Fuerza bruta | Espera creciente por IP y por IP+usuario (bloqueo tras 5 fallos); freno suave por usuario que no afecta a conexiones ya usadas |
| Robo de sesión | Token aleatorio guardado solo como hash; cookie `HttpOnly`, `Secure`, `SameSite=Lax` |
| CSRF | `SameSite` y comprobación de `Origin` en toda petición que cambia datos |
| XSS | CSP sin scripts en línea (solo un hash), React escapa el contenido, imágenes servidas con el tipo detectado y `nosniff` |
| Clickjacking | `X-Frame-Options: DENY` y `frame-ancestors 'none'` |
| Datos de otra cuenta | Todas las consultas filtradas por `user_id` en la sesión de base de datos; pruebas que recorren todas las rutas con dos cuentas |
| SSRF | Push solo a FCM, Mozilla, Apple y Windows por https; el código de barras solo consulta Open Food Facts |
| Peticiones enormes | 1 MiB en JSON y 16 MiB en total, en Caddy y en la app |
| Ficheros falsos | Solo JPEG, PNG y WebP comprobados por sus bytes |
| Fórmulas en CSV | Celdas que empiezan por `=`, `+`, `-`, `@`, tabulador o retorno van precedidas de `'` |
| Gasto de IA | Topes diarios por cuenta y globales e interruptor de pausa |
| Escalada en el servidor | Contenedor sin root, solo lectura, sin capacidades, `no-new-privileges`, memoria limitada, puerto solo en loopback |

## Revisión del 2026-10-15

Auditoría del código (autenticación, sesiones, autorización, subidas, SSRF, exportaciones, errores, límites),
`pip-audit` y `npm audit` sin vulnerabilidades, `bandit` revisado (los avisos que quedan son falsos positivos:
nombres de tablas fijos en las migraciones y el XML de la copia S3 del propio administrador) y pruebas no
destructivas contra producción (TLS 1.0/1.1 rechazados, cabeceras, rutas ocultas). Los arreglos llevan pruebas en
`backend/tests/test_hardening.py`.

## Si la instalas en tu VPS

- `deploy/harden-vps.sh` (Ubuntu 24.04): SSH solo con clave, `MaxAuthTries 3`, `LoginGraceTime 30`,
  `X11Forwarding no` en un fichero propio que se valida con `sshd -t` antes de recargar, y `fail2ban` para SSH
  (1 h de bloqueo tras 5 fallos, que crece si reincide). No toca Docker, Caddy, el cortafuegos ni otros proyectos.
  Antes de cerrar la sesión, comprueba en otra terminal que entras.
- Cortafuegos con solo 22, 80 y 443 abiertos; el contenedor publica su puerto en `127.0.0.1`.
- Actualizaciones automáticas (`unattended-upgrades`) y reiniciar cuando lo pida el kernel: los contenedores
  vuelven solos (`restart: unless-stopped`).
- Copias fuera del servidor cifradas con frase (ver README).
