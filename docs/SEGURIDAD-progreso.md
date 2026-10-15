# Seguridad — progreso (2026-10-15)

Encargo: reforzar la seguridad de Kcalia («prácticamente injaqueable»). El usuario delegó las decisiones. Rama
`seguridad`. No se tocan los ajustes del sistema de la VPS (SSH, ufw): se dan los comandos para que los aplique él.

## Pasos
- [x] 1. Auditoría de código: autenticación, sesiones, CSRF, autorización entre cuentas, subidas, SSRF (push, código de
      barras, copias S3), inyección CSV en exportaciones, rutas de ficheros estáticos, errores, límites de ritmo.
- [x] 2. Dependencias (pip-audit, npm audit) y análisis estático (bandit).
- [x] 3. Contenedores y Caddy: usuario no root, capacidades, cabeceras (CSP, HSTS, etc.), TLS.
- [x] 4. Pruebas no destructivas contra producción desde fuera.
- [ ] 5. Arreglos con TDD, despliegue, `SECURITY.md` y sección en el README.

## Ya estaba bien
Argon2, sesión con token aleatorio guardado como hash y cookie HttpOnly/Secure/SameSite=Lax, comprobación de Origin en
escrituras, freno de intentos de login y de solicitudes de cuenta, mismo mensaje exista o no el usuario, CSP sin
scripts en línea, X-Frame-Options, nosniff, HSTS en Caddy, documentación de la API apagada, contenedor sin root,
solo lectura, sin capacidades y no-new-privileges, puerto solo en loopback, TLS 1.2/1.3 (1.0 y 1.1 rechazados),
pip-audit y npm audit sin vulnerabilidades, aislamiento entre cuentas probado (test_isolation, test_access).
VPS: SSH solo con clave, ufw con 22/80/443, actualizaciones automáticas.

## Hallazgos y arreglo (app)
1. Bloqueo de cuenta provocado: el freno de login por nombre de usuario (hasta 1 h) lo puede disparar cualquiera.
   -> por IP y por IP+usuario estrictos; por usuario solo un freno suave y corto.
2. SSRF en push: se aceptaba cualquier endpoint https (127.0.0.1, IPs internas). -> lista de servicios de push reales.
3. Sin límite de tamaño de petición: un cuerpo enorme sin sesión agota la memoria. -> límite en Caddy y en la app.
4. Cabecera `server: uvicorn`. -> quitarla (uvicorn y Caddy).
5. Cabeceras extra: COOP, CORP, Permissions-Policy más cerrada, HSTS con includeSubDomains.
6. Imágenes: el tipo lo dice el cliente. -> comprobar los bytes (JPEG/PNG/WebP) y guardar el tipo detectado.
7. Inyección de fórmulas en los CSV exportados. -> neutralizar celdas que empiezan por = + - @.
8. bandit: SHA1/MD5 que no son de seguridad -> usedforsecurity=False. Migraciones (nombres del esquema) y XML de S3
   (endpoint del propio administrador): falsos positivos o riesgo bajo, se documentan.

## Recomendaciones para la VPS (las aplica el usuario)
fail2ban (2.259 intentos SSH fallidos en 24 h), `X11Forwarding no`, `MaxAuthTries 3`, reiniciar (kernel pendiente).

## Pendiente después (pedido el 2026-10-15)
Revisar el objetivo calórico: con 1,67 m, 65 kg y 19 años sale ≈ 2.630 kcal los días de entreno y al usuario le
parece alto. Comprobar si la fórmula, el factor de actividad y el ajuste de entreno se suman de más y darle una
respuesta con solución.
