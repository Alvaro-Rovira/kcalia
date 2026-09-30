import os
import tempfile

# La configuración se lee al importar la app, así que el entorno va antes.
_TMP = tempfile.mkdtemp(prefix="kcalia-test-")
os.environ.update(
    DATA_DIR=_TMP,
    BACKUP_DIR=os.path.join(_TMP, "backups"),
    STATIC_DIR=os.path.join(_TMP, "static"),
    COOKIE_SECURE="false",
    AI_API_KEY="test-key",
    AI_DAILY_LIMIT="5",
)
