# Manejo de Credenciales y el .env

## El problema del Redactor de Secretos
Hermes incluye una característica de seguridad (`security.redact_secrets`) que enmascara secretos (tokens, keys) en los outputs de herramientas. Esto afecta las variables de entorno inyectadas en `os.environ`. 
Si lees el token usando `os.environ.get("ASANA_ACCESS_TOKEN")`, corres el riesgo de recibir un token truncado o con el valor `***`, resultando en fallos de autenticación simulando que "no existe" el token.

## Solución Operativa
Los scripts en Python deben **siempre** evadir `os.environ` para los tokens, e implementar una función `load_env()` que abra explícitamente el archivo `.env` del sistema de archivos (generalmente en `$HOME/.hermes/profiles/<profile>/.env` o `$HERMES_PROFILE_DIR`) y parsee su contenido en un diccionario local.

## Nomenclatura Estándar
La variable autorizada para el Token de Acceso Personal (PAT) de Asana es `ASANA_ACCESS_TOKEN`. No inventes variaciones como `ASANA_PAT` o `ASANA_API_KEY`.
