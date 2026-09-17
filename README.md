# PM Obsidian Agent

Este repositorio es una colección de **Skills** de Antigravity/Hermes diseñados para operar un Portafolio de Gestión de Proyectos (PM) conectando **Asana** con **Obsidian**.

## Arquitectura

El paquete está diseñado para evitar la duplicación de estado, usando Obsidian como una base de conocimiento viva y Asana como la fuente de verdad operativa.

Se compone de los siguientes skills:

1. **`obsidian`**: Es la capa base. Enseña al agente la sintaxis correcta para escribir archivos de Obsidian (Markdown interactivo, archivos `.base` para consultas, y `.canvas` para mapas visuales). Evita errores comunes de formato.
2. **`obsidian-pm-context`**: La capa estructural. Provee el modelo mental de PM (Programa > Proyecto > Tarea). Determina qué propiedades y reglas se escriben en el *frontmatter* de las notas para que Obsidian pueda generar tableros y reportes automáticos mediante Bases.
3. **`asana-obsidian-llm-wiki`**: *(Requerido)* La capa de sincronización que conecta la API de Asana con la bóveda de Obsidian para materializar proyectos y actualizar los reportes.

## Requisitos

- **Obsidian**: Instalado localmente con un vault definido.
- **Asana**: Token de acceso personal (Personal Access Token).
- **Entorno Hermes**: Un agente configurado en el que se instalarán estos skills.

## Instalación

Este repositorio está estructurado para ser integrado en un perfil de **Hermes**. Para instalarlo:

1. Clona este repositorio y copia el contenido de la carpeta `skills/` en el directorio `$HOME/.hermes/skills/` de tu máquina local.
2. Hermes detectará automáticamente los skills.
3. Configura tus credenciales de Asana (`ASANA_ACCESS_TOKEN`) y la ruta a tu bóveda (`OBSIDIAN_VAULT_PATH`) en el archivo `.env` de tu perfil de Hermes (ej. `$HOME/.hermes/profiles/tu_perfil/.env`).

## Notas de Uso

- **Lógica de Programas**: Si un proyecto no pertenece a un Portfolio en Asana, los scripts utilizarán el nombre del Workspace como "Programa" por defecto para no dejar huérfanos los proyectos en el portafolio de Obsidian.
- **Modificación manual**: Puedes usar la propiedad `programa_manual` en el *frontmatter* de Obsidian para forzar una agrupación cuando Asana no disponga de Portfolios (ej. tiers gratuitos).
