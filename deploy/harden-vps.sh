#!/usr/bin/env bash
# Endurece el SSH de la VPS e instala fail2ban. No toca Docker, Caddy, el cortafuegos ni ningún proyecto.
#   ssh root@IP 'bash /opt/kcalia/deploy/harden-vps.sh'
# Probado para Ubuntu 24.04. Se puede repetir sin problema. Después: abre una sesión SSH NUEVA para comprobar que
# entras antes de cerrar la que tienes.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Ejecútalo como root." >&2; exit 1; }

# 1. SSH. Un fichero propio que se lee el primero (en sshd manda el primer valor), sin editar sshd_config.
dropin=/etc/ssh/sshd_config.d/01-hardening.conf
cat > "$dropin" <<'CONF'
# Puesto por deploy/harden-vps.sh (Kcalia).
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
CONF
if ! sshd -t; then
  rm -f "$dropin"
  echo "La configuración de SSH no valida; no se ha cambiado nada." >&2
  exit 1
fi
systemctl try-reload-or-restart ssh.service  # recarga en caliente: las sesiones abiertas siguen
echo "SSH: $(sshd -T | grep -E '^(maxauthtries|x11forwarding|logingracetime|passwordauthentication) ' | tr '\n' ' ')"

# 2. fail2ban: tras 5 fallos en 10 min, 1 h de bloqueo, que se duplica si reincide (máximo una semana).
if ! command -v fail2ban-client >/dev/null; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q fail2ban >/dev/null
fi
cat > /etc/fail2ban/jail.d/kcalia.local <<'CONF'
# Puesto por deploy/harden-vps.sh (Kcalia).
[DEFAULT]
bantime = 1h
bantime.increment = true
bantime.maxtime = 1w
findtime = 10m
maxretry = 5
ignoreip = 127.0.0.1/8 ::1

[sshd]
enabled = true
CONF
systemctl enable -q fail2ban
systemctl restart fail2ban
sleep 2
fail2ban-client status sshd | grep -E "Currently banned|Total failed" || true

echo
echo "Hecho. Abre otra terminal y comprueba que entras por SSH antes de cerrar esta."
[ -f /var/run/reboot-required ] && echo "Hay un kernel nuevo pendiente: reinicia cuando te venga bien (los contenedores vuelven solos)."
exit 0
