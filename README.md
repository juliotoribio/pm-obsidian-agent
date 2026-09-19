# PM Obsidian Agent

PM Obsidian Agent es una colección de herramientas para operar un portafolio de proyectos conectando Asana con Obsidian de forma unidireccional. Está diseñado para Project Managers y líderes de portafolio que necesitan gobernar múltiples proyectos a la vez, manteniendo la ejecución dura en Asana y el contexto, riesgos y decisiones a largo plazo en Obsidian. El sistema no solo refleja el estado, sino que automatiza la detección de discrepancias, bloqueos y alertas de salud para forzar decisiones a nivel gerencial.

## Qué produce

El agente materializa la estructura en Obsidian y genera de forma automática:

- **Dashboard de Portafolio**: Vista raíz que consolida todos los proyectos agrupados por programa, con métricas de avance y finanzas.
- **Detección de Watermelons (Discrepancia RAG)**: Cruza el estado declarado por el PM frente a la realidad de avance, identificando proyectos que dicen estar en verde pero matemáticamente están en rojo.
- **Mapas de Carga y Riesgos (Personas)**: Crea perfiles automáticos por integrante mostrando su volumen de tareas bloqueadas y alertas críticas de *bus factor*.
- **Alertas Financieras**: Cruza el consumo de presupuesto contra el avance real para detectar desviaciones tempranas, y audita proyectos que omitieron clasificación de CAPEX/OPEX.
- **Registro de Riesgos Abiertos**: Centraliza los riesgos de todos los proyectos (redactados por humanos) ordenados matemáticamente por su nivel de exposición (probabilidad × impacto).
- **Reportes de Estatus por Corte**: Guarda un snapshot temporal diario del portafolio, permitiendo generar reportes que comparan dos fechas para exponer con precisión matemática qué cambió, qué empeoró y qué se resolvió.
- **Digest Proactivo**: Emite un resumen inteligente y asíncrono con alertas nuevas (deltas) listo para integrarse y enviarse por Slack, Teams o Telegram.

## Requisitos

- **Obsidian** instalado, con un vault local (y el plugin *Bases* para renderizar las vistas `.base`).
- **Asana** con un Personal Access Token.
- **Python 3.10** o superior.

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/juliotoribio/pm-obsidian-agent.git
cd pm-obsidian-agent
```

### 2. Configurar credenciales

El script lee las siguientes variables de entorno. Puedes exportarlas en tu terminal o configurarlas en el archivo `.env` de tu perfil de agente:

```bash
export ASANA_ACCESS_TOKEN=<tu_personal_access_token>
export OBSIDIAN_VAULT_PATH=<ruta_absoluta_a_tu_vault_de_obsidian>
```
> **Seguridad**: Nunca subas el token a un repositorio.

### 3. Instalar dependencias

El motor de sincronización depende de utilidades para leer y escribir el frontmatter YAML sin corromper la estructura de los archivos.

```bash
pip install -r skills/asana-obsidian-llm-wiki/requirements.txt
```

### 4. Inicializar la Bóveda (Bootstrap)

Si es la primera vez que sincronizas, debes crear la taxonomía base (carpetas y archivos `.base`) que el agente necesita. Ejecuta el script de inicialización apuntando a tu bóveda:

```bash
python3 skills/asana-obsidian-llm-wiki/scripts/bootstrap_vault.py <ruta_del_vault> --apply
```

### 5. Primera Ejecución y Validación (Dry-Run)

Antes de conectar el agente a tu entorno real, realiza un **Dry-Run** para validar que el alcance, los filtros de Asana y la resolución de nombres sean correctos sin riesgo de corromper datos.

```bash
python3 skills/asana-obsidian-llm-wiki/scripts/asana_obsidian_sync.py --dry-run
```
Al correrlo, revisa que los proyectos coincidan con tu expectativa y que no haya colisiones de nombres o errores reportados por falta de permisos.

## Uso de los Scripts

- **`asana_obsidian_sync.py`**: El motor principal. Lee Asana y escribe/actualiza el vault de Obsidian. Por defecto corre en modo dry-run. Para aplicar los cambios reales, debes pasarle el flag `--apply`. Además, en cada escritura, guarda un snapshot diario en `03 Log/`. Soporta proyectos en múltiples workspaces.
- **`bootstrap_vault.py`**: Crea o repara la estructura de carpetas, plantillas y vistas `.base` (dashboard, discrepancias, bloqueados, finanzas) en el vault de Obsidian. 
- **`generate_status_report.py`**: Compara dos snapshots históricos de `03 Log/` (ej. `generate_status_report.py 2026-09-01 2026-09-15`) y produce un reporte Markdown humano explicando las variaciones del portafolio en esa quincena.
- **`generate_proactive_digest.py`**: Analiza el portafolio en tiempo real frente al último envío reportado y devuelve un string Markdown con alertas accionables (cambios de RAG, nuevas fechas vencidas) suprimiendo el ruido repetitivo.

## Estructura del Vault

El sistema asume (y el `bootstrap_vault.py` crea) la siguiente topología de conocimiento:

```text
00 Portafolio.base          # dashboard raíz — todos los proyectos
01 Programas/               # agrupadores de proyectos y sus vistas
02 Projects/                # una nota gestionada automáticamente por proyecto de Asana
03 Log/                     # snapshots diarios, historial temporal y reportes generados
04 Decisions/               # decisiones documentadas (manual)
05 Knowledge/               # conocimiento reutilizable (manual)
06 Risks/                   # registro formal de riesgos (manual, se vincula a proyectos)
07 Agents/                  # perfiles y prompts de agentes
08 People/                  # perfiles y carga de trabajo del equipo extraído de Asana
09 Vistas/                  # vistas transversales (Bloqueados, RAG, Hitos, Finanzas)
99 System/                  # plantillas de markdown y configuración interna
```

## Seguridad

- **GET-Only hacia Asana**: Los scripts de sincronización principal y generación de reportes nunca realizan operaciones de escritura, actualización o borrado sobre Asana.
- **Preservación Humana**: El agente solo reescribe el bloque demarcado por `<!-- HERMES:START -->` y actualiza propiedades específicas del frontmatter. El resto del archivo del proyecto (notas humanas, reflexiones) es intocable y se preserva íntegro.
- **Sin Secretos Locales**: Ningún token o secreto se inyecta o vive en el vault de Obsidian.
- **Falla en Cerrado**: Si la red falla o Asana devuelve error, el script aborta inmediatamente sin escribir nada en el vault, protegiendo la integridad de la base de conocimiento local.

## Licencia

Este proyecto está bajo la licencia MIT.
