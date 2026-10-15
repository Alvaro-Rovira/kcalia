# Seguridad — progreso (2026-10-15)

Encargo: reforzar la seguridad de Kcalia («prácticamente injaqueable»). El usuario delegó las decisiones. Rama
`seguridad`. No se tocan los ajustes del sistema de la VPS (SSH, ufw): se dan los comandos para que los aplique él.

## Pasos
- [ ] 1. Auditoría de código: autenticación, sesiones, CSRF, autorización entre cuentas, subidas, SSRF (push, código de
      barras, copias S3), inyección CSV en exportaciones, rutas de ficheros estáticos, errores, límites de ritmo.
- [ ] 2. Dependencias (pip-audit, npm audit) y análisis estático (bandit).
- [ ] 3. Contenedores y Caddy: usuario no root, capacidades, cabeceras (CSP, HSTS, etc.), TLS.
- [ ] 4. Pruebas no destructivas contra producción desde fuera.
- [ ] 5. Arreglos con TDD, despliegue, `SECURITY.md` y sección en el README.

## Hallazgos
(se van anotando aquí)
