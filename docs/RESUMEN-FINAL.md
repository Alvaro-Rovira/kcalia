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

## Despliegue

Pendiente de completar al desplegar.

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
