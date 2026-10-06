# Resumen final · mejoras-v2

Trabajo autónomo del 6 de octubre de 2026 sobre la rama `mejoras-v2` (23 commits desde `6b1b693`). Diseño en
`docs/superpowers/specs/2026-10-06-mejoras-v2-design.md`, decisiones razonadas en `docs/DECISIONES.md` (25) y
avance tarea a tarea en `docs/PROGRESO.md`.

## Qué hay de nuevo

**Base y seguridad (se hizo primero, porque todo lo demás depende de ello)**

- Migraciones de esquema versionadas (`PRAGMA user_version`) con copia comprimida previa y reconstrucción segura de
  tablas. Probadas sobre una base de demostración con datos: tu cuenta, tus 3 comidas, 2 productos y tu peso pasan
  intactos y tu cuenta queda como administradora.
- **Multiusuario con aprobación manual**: la primera cuenta administra; las demás piden acceso y esperan. Aislamiento
  por `user_id` aplicado automáticamente a todas las consultas (si un código intentara saltárselo, falla en vez de
  mezclar datos). Límites de IA y voz por cuenta, global y propio del administrador. Registro protegido (espera
  creciente, límite por IP, campo trampa, máximo de pendientes, misma respuesta exista o no la cuenta).
- **Panel `/admin`**: solicitudes, cuentas (aprobar, rechazar, suspender, reactivar, límites), gasto de IA y voz con
  coste estimado, pausa de la IA, registro abierto o cerrado, estado de la copia externa y auditoría.

**Fase 1 · Registro diario**: ingrediente a mano con autocompletado; copiar una comida o un día; favoritos y recientes
ordenados por el momento del día; escáner de códigos de barras con Open Food Facts (con lector WebAssembly de respaldo
para iPhone).

**Fase 2 · Seguimiento**: agua con objetivo automático; fibra y alcohol por ingrediente, día y semana (bebidas con
alcohol en la hoja de añadir); medidas corporales con gráfica y fotos de progreso privadas comparables.

**Fase 3 · Entrenamiento**: días de entreno y descanso con objetivos propios (espejo Python/TypeScript probado con los
mismos casos); registro en `/entreno` con rutinas, temporizador de descanso, «Repetir», última marca, 1RM estimado y
progresión, también sin conexión; calorías del entreno estimadas (MET), informativas o sumadas al objetivo.

**Fase 4 · Constancia**: recordatorios Web Push propios (RFC 8291 + VAPID, sin dependencias externas) para comidas y
peso, solo si faltan; plan semanal con lista de la compra marcable e ideas opcionales de la IA; sugerencia para cerrar
el día sin pasarse; la semana como imagen para compartir.

**Fase 5 · Datos**: copia nocturna fuera del servidor a cualquier S3 compatible, verificada y opcionalmente cifrada
(`scripts/restore-backup.py` la restaura); importar desde MyFitnessPal, Yazio, CSV genérico o una exportación de
Kcalia, sin duplicar; atajos en el icono de la app y atajo de voz de Siri (`docs/ATAJO-IOS.md`).

**Navegación móvil**: Hoy · Historial (Diario / Plan) · Entreno · Progreso (Resumen / Cuerpo) · Ajustes.

## Pruebas

| | Antes | Ahora |
|---|---|---|
| pytest (API) | 205 | 431 |
| Vitest (frontend) | 111 | 182 |
| e2e (Playwright, móvil 390 px) | 10 | 25 |
| Voz | 5 | 5 |

Typecheck, ruff (también en `scripts/`) y build en verde. Ninguna prueba llama a servicios reales: IA, Open Food
Facts, servicios de push y S3 se simulan. Los vectores oficiales (RFC 8291 para push, ejemplo de AWS para SigV4)
fijan que la criptografía propia es correcta.

## Despliegue (6 de octubre de 2026, 19:05)

En `https://kcalia.roviradev.duckdns.org`, solo los contenedores de Kcalia en `/opt/kcalia`, con `./deploy/deploy.sh`.

| Paso | Resultado |
|---|---|
| Estado previo | commit `6b1b693`, `kcalia-app` y `kcalia-stt` sanos; clave de IA presente (no se ha mostrado) |
| Copia previa | `/opt/kcalia-predeploy/kcalia-20261006-190016-6b1b693.db` (copia consistente, integridad `ok`); imágenes anteriores guardadas como `kcalia-app:pre-6b1b693` y `kcalia-stt:pre-6b1b693` |
| Ensayo | la migración se ejecutó antes con la imagen nueva sobre una copia de esa base, sin red: mismos datos, cuenta administradora |
| Despliegue | commit `809247b`; 20 variables nuevas añadidas a `.env` con su valor por defecto (solo se mostraron los nombres); claves VAPID generadas en el contenedor sin mostrarse; Caddy sin cambios |
| Migración | 1, 2 y 3 aplicadas sin errores, con su copia `premigracion-kcalia-v0-20261006-190512.db.gz` |
| Datos | iguales que antes: 1 cuenta (aprobada y administradora), 3 comidas, 2 productos, 1 peso; integridad `ok` |
| Acceso | 14 comprobaciones con la imagen desplegada sobre una base temporal (pendiente sin acceso, aprobar, `/admin` solo para el administrador, aislamiento entre cuentas, suspender, push configurado) y comprobaciones públicas en producción (todas las rutas de datos dan 401 sin sesión, origen ajeno 403, cabeceras de seguridad, atajos del manifiesto) |
| Resto del servidor | los otros 10 contenedores, intactos (sin reinicios desde el 22-23 de septiembre); Caddy activo y sin copias nuevas del `Caddyfile` |
| CI de GitHub | en verde para `809247b` |

No he creado cuentas en producción ni he entrado con la tuya: el flujo con sesión se ha probado con la imagen
desplegada sobre una base temporal y vacía.

**Volver atrás** (no ha hecho falta), dentro de `/opt/kcalia`: parar la app, restaurar la copia previa en el volumen
y arrancar las imágenes `pre-6b1b693` con `git checkout 6b1b693`. Cuando estés contento con la versión nueva, esas
imágenes se pueden borrar para liberar unos 2 GB:

```bash
ssh root@161.97.67.178 'docker image rm kcalia-app:pre-6b1b693 kcalia-stt:pre-6b1b693'
```

## Lo que no he podido verificar yo

Todo lo que necesita tu móvil, tus cuentas o servicios reales:

- **Notificaciones reales** en tu iPhone (iOS 16.4+, con la app instalada en la pantalla de inicio) o Android: el
  cifrado está probado con el vector de la RFC, pero no contra Apple o Google de verdad. Actívalas en Ajustes →
  Recordatorios y pulsa «Enviar un aviso de prueba».
- **Escáner con la cámara** del iPhone sobre un envase real.
- **Copia externa** contra un almacenamiento real: necesita que crees un bucket (Cloudflare R2 tiene 10 GB gratis) y
  pongas sus credenciales en `/opt/kcalia/.env` (`BACKUP_REMOTE_*`, y `BACKUP_ENCRYPTION_KEY` si quieres cifrarla).
  El estado de cada subida aparece en `/admin`.
- **Importar** una exportación real de MyFitnessPal o Yazio: los formatos salen de su documentación y de ejemplos
  públicos; si alguna columna no se detecta, la vista previa deja elegirla a mano.
- **Atajo de Siri**: los nombres de las acciones de Atajos pueden variar un poco según la versión de iOS.

## Qué hacer ahora

1. Entra con tu cuenta de siempre: ya eres administrador (Ajustes → Administración).
2. Si quieres que otras personas lo usen, pásales la dirección: piden cuenta y las apruebas en `/admin`. Si no, cierra
   el registro desde ahí.
3. Activa los recordatorios en Ajustes y, si entrenas, los días de entreno y descanso.
4. Opcional: copia externa (arriba) y el atajo de Siri.
