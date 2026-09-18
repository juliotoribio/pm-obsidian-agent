# PM Obsidian Agent

Colección de **Agent Skills** para operar un portafolio de gestión de proyectos (PM) conectando **Asana** con **Obsidian**.

Asana es la fuente de verdad operativa (tareas, fechas, estados, responsables).
Obsidian es la base de conocimiento duradero (contexto, decisiones, riesgos, aprendizajes).
Los skills hacen que un agente sincronice una hacia la otra — **en una sola dirección**.

## Los tres skills

| Skill | Rol |
|---|---|
| **`obsidian`** | Capa base. Sintaxis correcta de Obsidian: Markdown con WikiLinks, archivos `.base` (vistas tipo base de datos) y `.canvas` (mapas visuales). |
| **`obsidian-pm-context`** | Capa estructural. El modelo de PM (Programa → Proyecto → Tarea) y las propiedades de *frontmatter* que permiten a Obsidian generar tableros automáticos con Bases. **Requiere `obsidian`.** |
| **`asana-obsidian-llm-wiki`** | Capa de sincronización. Conecta la API de Asana con el vault de Obsidian: materializa proyectos, reconcilia estados y mantiene los reportes al día. |

## Requisitos

- **Obsidian** instalado, con un vault existente.
- **Asana** con un Personal Access Token ([cómo generarlo](https://developers.asana.com/docs/personal-access-token)).
- **Hermes Agent** instalado y funcionando.

## Instalación

### 1. Clonar

```bash
git clone https://github.com/juliotoribio/pm-obsidian-agent.git
```

### 2. Copiar los skills a tu perfil de Hermes

Los skills van al directorio `skills/` de tu perfil. Sustituye `<PERFIL>` por el nombre de tu perfil:

```bash
cp -R pm-obsidian-agent/skills/* ~/.hermes/profiles/<PERFIL>/skills/
```

Verifica que se detectaron:

```bash
hermes skills list | grep -E "obsidian|asana"
```

Deberías ver los tres skills en estado `enabled`.

### 3. Configurar credenciales

En el archivo `.env` de tu perfil (`~/.hermes/profiles/<PERFIL>/.env`):

```
ASANA_ACCESS_TOKEN=<tu...PAT>
OBSIDIAN_VAULT_PATH=<ruta...vault>
```

> **Nunca** subas este archivo a un repositorio. Contiene secretos.

### 4. Instalar dependencias de Python

El motor de sincronización depende de PyYAML para leer y escribir el frontmatter de Obsidian sin corromperlo.
Dentro de la carpeta del skill, instala las dependencias:

```bash
pip3 install -r ~/.hermes/profiles/<PERFIL>/skills/asana-obsidian-llm-wiki/requirements.txt
```

### 5. Inicializar la Bóveda (Bootstrap)

Si es la primera vez que sincronizas, debes crear la taxonomía base (carpetas y archivos `.base`) que el agente usa.
Abre tu terminal y ejecuta el script de inicialización apuntando a tu bóveda:

```bash
python3 ~/.hermes/profiles/<PERFIL>/skills/asana-obsidian-llm-wiki/scripts/bootstrap_vault.py <ruta...vault> --apply
```

### 6. Verificar

```bash
python3 ~/.hermes/profiles/<PERFIL>/skills/asana-obsidian-llm-wiki/scripts/asana_obsidian_sync.py --dry-run
```

Debe listar el workspace detectado y los proyectos que se sincronizarían. Con `--dry-run` no escribe nada en el vault.

## Snapshot y Baseline
En cada ejecución con `--apply`, se genera un snapshot del estado en `03 Log/YYYY-MM-DD.md`. Además, la nota de cada proyecto recibe tres métricas inmutables/históricas en su frontmatter (`baseline_due_date`, `replan_count`, `slip_days`). Todo esto sienta las bases de un historial de PMO (Ver `ROADMAP.md`).

## Uso

El script principal sincroniza Asana → Obsidian:

```bash
python3 asana_obsidian_sync.py --dry-run    # reporte previo, no escribe nada
python3 asana_obsidian_sync.py --apply      # ejecuta
```

`--dry-run` es el modo por defecto. Ninguna escritura ocurre sin `--apply`.

Consulta un proyecto concreto (lado Asana + lado Obsidian):

```bash
python3 asana_obsidian_sync.py --query <PROJECT_GID>
```

## Pruebas Unitarias

El paquete incluye una suite de pruebas `unittest` que asegura las invariantes (ej. que el frontmatter se lea y escriba sin corromper yaml de listas, y que los hash sean estables):

```bash
python3 ~/.hermes/profiles/<PERFIL>/skills/asana-obsidian-llm-wiki/scripts/test_sync.py
```

## Cómo funciona

- **Identidad por ID.** Cada nota se identifica por su `asana_gid`, no por su nombre. Un proyecto renombrado en Asana no crea una nota duplicada.
- **Zonas separadas.** El agente escribe únicamente entre `<!-- HERMES:START -->` y `<!-- HERMES:END -->`. Todo lo demás — incluida la sección `## Notas humanas` — es intocable.
- **Sin embeddings.** Markdown, frontmatter, WikiLinks y búsqueda full-text. Sin base vectorial, sin graph database.
- **Falla en cerrado.** Si Asana no responde, el script aborta sin escribir nada en el vault.
- **Solo lectura por defecto.** La sincronización únicamente emite `GET`. Las escrituras hacia Asana se hacen mediante los scripts REST atómicos incluidos, nunca durante un sync.

## Agrupación en Programas

Los proyectos se agrupan por **Portfolio de Asana** cuando existe. Si tu plan de Asana no incluye Portfolios, todos los proyectos caen bajo el nombre del **Workspace** para que no queden huérfanos en el portafolio.

Para forzar una agrupación distinta, agrega `programa_manual` al frontmatter de la nota:

```yaml
programa_manual: "[[Infraestructura]]"
```

Asana manda: si existe un Portfolio, se usa ese, y `programa_manual` se ignora.

## Estructura del vault

```
00 Portafolio.base          # dashboard raíz — todos los proyectos
01 Programas/               # una nota por programa (+ su .base)
02 Projects/                # una nota por proyecto de Asana
03 Log/                   # snapshots diarios e historial temporal
04 Decisions/               # decisiones documentadas
05 Knowledge/               # conocimiento reutilizable
07 Agents/                  # agentes registrados
09 Vistas/                  # vistas transversales (bloqueados, en riesgo)
99 System/                  # protocolo y configuración
```

## Seguridad

- Ningún secreto vive en el vault.
- El agente nunca borra notas del vault.
- Las escrituras masivas requieren aprobación previa.
- El borrado en Asana se pide explícitamente, elemento por elemento, nunca en lote.

## Licencia

MIT
