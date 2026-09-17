# Runbook de Operaciones: Asana & Obsidian

## 1. 401 Unauthorized (Prueba de Conexión)
El "Personal Access Token" de Asana suele confundirse con credenciales de OAuth. Si la API de Asana falla, **NO inspecciones el token visualmente** (los tokens actuales de Asana y los OAuth se ven casi idénticos).
**Acción:** Ejecuta siempre `python3 scripts/asana_test_connection.py`. Este script validará la identidad y retornará el GID del Workspace.

## 2. 402/403 Portfolios Not Found
Si el Workspace configurado corresponde a un tier gratuito o básico de Asana, la funcionalidad de "Portafolios" no estará disponible. 
En lugar de fallar, el agente deberá utilizar el nombre del Workspace como "Programa" superior (agrupador base en Obsidian) o instruir a los PMs a inyectar el valor `programa_manual` en el frontmatter.

## 3. Fallas Silenciosas del Gateway / Cron
A menudo el reporte de `hermes gateway status` dirá que está vivo (cargado), pero los cronjobs no disparan la sincronización de Obsidian.
- **Diagnóstico Real:** Revisa si el proceso tiene un PID activo usando `launchctl list | grep hermes` o `systemctl --user status`.
- **Diagnóstico de Cron:** Para validar si un trabajo está realmente corriendo, busca `last_run_at`. Un `last_run_at: null` con estado `enabled: true` significa que la sincronización **nunca** ha corrido.

## 4. Colisión de Bot de Telegram (Restart Loops)
Si tienes múltiples perfiles de Hermes locales usando el mismo `TELEGRAM_BOT_TOKEN`, el gateway entrará en un ciclo infinito de reinicios compitiendo por los mensajes.
**Acción:** Usa `python3 scripts/check_telegram_conflicts.py` para buscar colisiones de huellas hash (SHA-256) entre perfiles y asignar tokens de bots independientes.
