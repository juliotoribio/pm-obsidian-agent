# Runbook de Operaciones

Guía de resolución de problemas y operación manual del Agente PM.

## 1. Error 401 Unauthorized
- **Causa**: El token de Asana está expirado, revocado o no se pudo cargar del perfil de Hermes (mira `credential-handling.md`).
- **Solución**: Genera un nuevo Personal Access Token en Asana, actualiza el archivo `.env` del perfil de Hermes correspondiente y corre `python scripts/healthcheck.py` para validar.

## 2. Error 402/403 (Portfolios no disponibles)
- **Causa**: La instancia de Asana configurada pertenece a un tier (ej. Basic, Premium) que no tiene acceso a Portafolios (Tier Advanced+ requerido).
- **Solución**: El script usará el nombre del Workspace como "Programa General". Si requieres separación, instruye a los Project Managers a usar la propiedad `programa_manual` en el YAML del archivo de proyecto de Obsidian.

## 3. Base falla en silencio o Obsidian da error de parseo (YAML)
- **Causa**: Posibles comillas mal escapadas en las fórmulas de los `.base`.
- **Solución**: Revisa que no haya comillas simples envolviendo comillas dobles internas en las propiedades. Asegúrate de que todas las variables opcionales tengan guardas `if()`.

## 4. Telegram Bot Conflicts
- **Causa**: Dos agentes (ej. local y servidor) corriendo con el mismo token de Telegram pueden "robarse" los mensajes.
- **Solución**: Ejecuta `python scripts/check_telegram_conflicts.py` para revisar si hay múltiples procesos de Hermes colisionando.
