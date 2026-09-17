# Runbook: Conectar Asana + Obsidian a un agente Hermes

> Extraído del montaje real del 2026-09-17 sobre el perfil `maha_pm_agent`.
> Cada paso incluye la verificación que confirma que funcionó.
> Los errores marcados con ⚠️ son fallos reales que ocurrieron y cómo se resolvieron.

---

## Antes de empezar: el mensaje de arranque

Si es la primera vez, dale esto al agente:

```
Quiero conectar Asana y Obsidian con Hermes para un segundo cerebro
y una wiki persistente.

Antes de proponer nada:

1. PROBAR primero, deducir después. No me digas que algo está roto
   o que no existe sin haberlo ejecutado.
2. Antes de escribir en cualquier lugar, muéstrame el reporte previo
   y espera mi aprobación.
3. Dime qué partes de mi contexto ya tienes y cuáles te faltan.
   No asumas.

Arquitectura:
- Asana = fuente operativa (tareas, fechas, estados, responsables)
- Obsidian = conocimiento duradero (decisiones, riesgos, contexto)
- Flujo unidireccional: Asana → Obsidian. Nunca al revés.
- Sin embeddings ni bases vectoriales. Markdown, frontmatter, WikiLinks.

Empieza verificando qué tienes instalado y dime qué encuentras
antes de tocar nada.
```

---

## Paso 0 — Diagnóstico

```bash
# El binario de Hermes puede no estar en PATH
export PATH="$HOME/.hermes/hermes-agent/venv/bin:$PATH"

hermes --version
hermes doctor
```

**Verificar:** versión reportada + doctor sin errores críticos.

⚠️ **En sesión de Hermes, `$HOME` apunta al perfil**, no a tu home real.
Usar rutas absolutas (`/Users/<user>/...`). El binario está en
`~/.hermes/hermes-agent/venv/bin/hermes`.

---

## Paso 1 — Asana

### 1.1 Verificar si está en el catálogo MCP

```bash
hermes mcp catalog
```

⚠️ **Asana NO está en el catálogo** (solo `linear` y `n8n`).
`hermes mcp install asana` falla. Hay que configurarlo manual.

### 1.2 Crear el Personal Access Token

```
app.asana.com/0/developer-console
```

⚠️ **Hay DOS paneles y se confunden:**
- **"MCP de Asana"** → Client ID + Secret → para OAuth. NO sirve aquí.
- **"Tokens de acceso personal"** → el PAT. **Este es.**

⚠️ **Los PAT modernos empiezan con `2/`** — igual que un token OAuth.
Asana dice que los formatos cambian sin aviso. **No validar por forma.** Probar.

### 1.3 Guardar el token

En el `.env` del perfil:

```
ASANA_ACCESS_TOKEN=<valor>
```

⚠️ **Nunca pegar el token en el chat.** Editarlo directamente en el archivo.
Un secreto que pasa por el chat queda comprometido y hay que rotarlo.

### 1.4 Probar el token ANTES de seguir

```bash
python3 scripts/asana_test_connection.py
```

**Debe devolver** usuario + workspaces. Si da 401, el token está mal.

⚠️ **El redactor de secretos de Hermes enmascara valores en la salida.**
Un token válido puede verse vacío o como `***`. Leer el `.env` con Python
y verificar `len()` dentro del intérprete, no en el eco de la terminal.

⚠️ **Comandos inline con el nombre de la variable fallan** con
`SyntaxError: expression cannot contain assignment`. Usar un archivo `.py`.

### 1.5 Configurar el MCP

⚠️ **NO** editar `config.yaml` con patch/write_file — está bloqueado por seguridad.
⚠️ **NO** usar `hermes mcp add --args` — argparse se traga el `-y` y falla.

Usar la misma vía que el CLI:

```python
import sys; sys.path.insert(0, '/ruta/a/hermes-agent')
from hermes_cli.config import load_config, save_config
cfg = load_config()
cfg.setdefault('mcp_servers', {})['asana'] = {
    'command': 'npx',
    'args': ['-y', '@roychri/mcp-server-asana@1.8.0'],
    'env': {
        'ASANA_ACCESS_TOKEN': '${ASANA_ACCESS_TOKEN}',
        'READ_ONLY_MODE': 'true',     # empezar en solo lectura
    },
    'timeout': 120,
    'connect_timeout': 90,
}
save_config(cfg)
```

**Verificar:**

```bash
hermes mcp test asana
```

⚠️ **PROBAR antes de concluir.** Con `READ_ONLY_MODE=true` deben aparecer
**18 herramientas, todas de lectura**. Si dice que no conecta, revisar
`hermes mcp test` — la resolución de `${VAR}` sí funciona porque Hermes
carga el `.env` antes de spawnear el MCP.

### 1.6 Nota sobre escritura

⚠️ **El servidor es todo-o-nada:** o 18 herramientas de lectura, o las 41
completas (incluye borrar). **No hay permisos granulares.**

Para habilitar escritura: `READ_ONLY_MODE: 'false'` + reiniciar Hermes.
Verificado: aparecen 41 herramientas.

**El borrado se gobierna por proceso, no por permisos.** Escribir la política
en el protocolo del vault (ver Paso 3).

---

## Paso 2 — Obsidian

### 2.1 Encontrar el vault

⚠️ Puede haber **varios vaults registrados**. No adivinar cuál.

```bash
# macOS: lista todos los vaults registrados
cat "~/Library/Application Support/obsidian/obsidian.json"
```

**Si hay más de uno, PARAR y preguntar al dueño cuál usar.**

⚠️ Verificar si está en iCloud/Google Drive. **Sync en la nube + escrituras
concurrentes = conflictos.** Mencionarlo al dueño.

### 2.2 Crear la estructura

```bash
V="/ruta/al/vault"
mkdir -p "$V/02 Projects" "$V/04 Decisions" "$V/05 Knowledge" \
         "$V/07 Agents" "$V/99 System"
```

⚠️ **Solo crear. Nunca reorganizar ni renombrar notas existentes.**

### 2.3 Registrar la ruta

En el `.env` del perfil:

```
OBSIDIAN_VAULT_PATH="/ruta/al/vault"
```

---

## Paso 3 — Escribir el protocolo

Crear `99 System/Hermes Knowledge Protocol.md` con estas secciones:

| # | Sección | Contenido |
|---|---|---|
| 1 | Arquitectura | Quién es fuente de verdad de qué |
| 2 | Identidad de notas | `asana_gid` permanente, nunca por nombre |
| 3 | Reglas de consulta | Buscar → leer → consultar Asana → diferenciar capas |
| 4 | Reglas de actualización | Cuándo escribir (decisión, riesgo, cambio material...) |
| 5 | Qué NO guardar | Conversaciones, logs, secretos, ruido |
| 6 | Zonas administradas | Marcadores `HERMES:START/END`, `## Notas humanas` intocable |
| 7 | Contradicciones | Asana gana en estado, Obsidian en decisión; registrar sin sobrescribir |
| 8 | Trazabilidad | Frontmatter obligatorio con fuente y fecha |
| 9 | Seguridad y control | Política de borrado con confirmación explícita |
| 10 | Estructura de carpetas | |
| 11 | Sincronización | Frecuencia, dedup, qué hacer si Asana cae |
| 12 | Cómo la wiki refleja un borrado | Quitar de la lista + constancia en Cambios recientes |

**Las tres capas que siempre hay que diferenciar:**
- **[Hecho — Asana]** dato operativo de la API
- **Documentado (Obsidian)** conocimiento registrado
- **[Inferencia — Hermes]** deducción propia, siempre marcada

---

## Paso 4 — Script de sincronización

Crear `scripts/asana_obsidian_sync.py` con estos invariantes:

- **Solo GET** contra Asana. Las escrituras van por el MCP, no por el script.
- Escribe **solo entre** `<!-- HERMES:START -->` y `<!-- HERMES:END -->`.
- `## Notas humanas` **nunca** se toca (preservar byte a byte).
- **Nunca borra** notas del vault.
- Si Asana no responde: **aborta sin escribir nada**.
- `--dry-run` por defecto; `--apply` para ejecutar.
- Dedup por `asana_gid` + `source_hash`.
- `os.replace()` para escritura atómica.

**Frontmatter obligatorio:**

```yaml
---
type: project
source: asana
asana_gid:            # identidad permanente
asana_url:
workspace:
owner:
status:
start_date:
due_date:
last_synced_at:
source_hash:
---
```

⚠️ **Bugs ya encontrados y corregidos** (no repetirlos):
- `load_env()` debe leer el `.env` directo, no vía `os.environ` (el redactor enmascara)
- No persistir campos internos (`_title`) en el frontmatter
- `write_index` debe tolerar items de tipo `skip` sin lista de tareas
- Normalizar guiones bajos de nombres de Asana para el título y el archivo

---

## Paso 5 — Sincronización inicial

```bash
# 1. Reporte previo (NO escribe)
python3 scripts/asana_obsidian_sync.py --dry-run

# 2. Mostrar el reporte y ESPERAR APROBACIÓN

# 3. Ejecutar
python3 scripts/asana_obsidian_sync.py --apply
```

⚠️ **Nunca hacer la primera escritura masiva sin aprobación explícita.**

---

## Paso 6 — Gateway y cron

### 6.1 El gateway (el fallo silencioso #1)

⚠️ **Los cron jobs SOLO disparan si el gateway del perfil corre.**

```bash
launchctl list | grep hermes      # macOS: la verdad real (PID + status)
hermes cron status                # "Gateway is running — cron jobs will fire"
```

⚠️ **`hermes gateway status` puede reportar "loaded" con el proceso MUERTO.**
No confiar solo en ese comando. Confirmar con `launchctl` o `cron status`.

**Síntoma de gateway muerto:** `Next run` congelado en el pasado en
`hermes cron list`, y nada dispara. Sin error visible.

### 6.2 Token de Telegram único (el fallo silencioso #2)

⚠️ **Cada perfil necesita su PROPIO `TELEGRAM_BOT_TOKEN`.**
Dos perfiles con el mismo token entran en loop infinito:

```
ERROR gateway.run: Gateway hit a non-retryable startup conflict:
telegram: Telegram bot token already in use (PID NNNN).
```

**Detectar duplicados** (nunca imprimir los tokens, comparar huellas):

```bash
python3 scripts/check_telegram_conflicts.py
```

**Qué se comparte y qué no:**

| Variable | ¿Único por perfil? |
|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ **Sí** — compartido = loop |
| `TELEGRAM_HOME_CHANNEL` | ❌ No — es tu chat destino |
| `TELEGRAM_ALLOWED_USERS` | ❌ No — eres tú |
| `ASANA_ACCESS_TOKEN` | ❌ No — mismo workspace |

⚠️ **No cambiar `TELEGRAM_HOME_CHANNEL` al crear un bot nuevo.** Es a dónde
llegan los mensajes, no quién los manda.

### 6.3 Instalar y arrancar

```bash
hermes gateway install
hermes gateway start
sleep 10

# VERIFICACIÓN REAL
launchctl list | grep hermes        # debe mostrar PID con status 0
hermes cron status                  # "cron jobs will fire automatically"
```

⚠️ **Los errores viejos del `gateway.error.log` no se borran.** Comparar
timestamps con el arranque antes de concluir que sigue roto.

### 6.4 Programar el sync horario

Cron cada 60 minutos, con el script como `script` y un prompt de análisis.

⚠️ El parámetro `script` espera un **nombre relativo** a `~/.hermes/scripts/`,
no una ruta absoluta.

---

## Paso 7 — Verificación final

```bash
# 1. Diagnóstico
export PATH="$HOME/.hermes/hermes-agent/venv/bin:$PATH"
hermes doctor

# 2. MCP
hermes mcp test asana                      # N herramientas descubiertas

# 3. Gateway (el dato duro)
launchctl list | grep hermes               # PID real
hermes cron status                         # cron disparará

# 4. Sync sin cambios (dedup funciona)
python3 scripts/asana_obsidian_sync.py --dry-run

# 5. Integridad de marcadores
grep -c "HERMES:START" "$OBSIDIAN_VAULT_PATH/02 Projects"/*.md
```

**Prueba crítica — contenido humano:**

1. Escribir una nota a mano en una sección `## Notas humanas`
2. Forzar una re-sincronización
3. **Confirmar que la nota sobrevivió y el bloque Hermes se regeneró**

---

## Checklist de seguridad

- [ ] Ningún secreto en el chat, solo en `.env`
- [ ] Ningún secreto en el vault
- [ ] Borrado con confirmación explícita, nunca en lote
- [ ] Reporte previo antes de la primera escritura
- [ ] `READ_ONLY_MODE=true` al empezar
- [ ] El sync solo emite GET
- [ ] `## Notas humanas` nunca sobrescrita
- [ ] Nunca borrar notas del vault
- [ ] Si Asana cae: no escribir nada
- [ ] Registrar una acción ≠ autorización para ejecutarla

---

## Errores reales cometidos (para no repetirlos)

| Error | Lección |
|---|---|
| Dije que el PAT estaba mal por su prefijo `2/` | **Probar, no deducir.** Los formatos cambian. |
| Dije que el MCP no conectaba sin correr `hermes mcp test` | **Probar, no deducir.** |
| Dije que el gateway corría (decía "loaded") | **`launchctl`, no `gateway status`.** |
| Mezclé Linear con Asana sin que se pidiera | **Leer la config actual, no la memoria.** |
| El gateway en loop por token compartido | **Un bot por perfil, verificar huella.** |
