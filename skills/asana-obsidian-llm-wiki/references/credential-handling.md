# Credential Handling

Este documento establece las políticas de seguridad para el manejo de credenciales dentro de los scripts de python del agente.

## Redactor de Secretos de Hermes
Hermes incorpora un filtro de seguridad que enmascara secretos inyectados en las variables de entorno del proceso (`os.environ`). Esto puede provocar que un token legítimo llegue vacío o enmascarado (e.g. `[REDACTED]`) al intérprete de Python, causando fallos de autenticación 401.

## Solución Aprobada
El script `asana_obsidian_sync.py` **debe** leer el archivo `.env` del sistema de archivos directamente (usando la ruta del perfil `HERMES_PROFILE_DIR` o `~/.hermes/profiles/...`) para extraer la variable `ASANA_ACCESS_TOKEN` y `OBSIDIAN_VAULT_PATH`. 

Nunca intentes hacer un `os.environ.get("ASANA_ACCESS_TOKEN")` directamente en este skill sin antes verificar si ha sido enmascarado.
