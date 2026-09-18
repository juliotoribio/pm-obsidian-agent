#!/usr/bin/env python3
"""
generate_status_report.py

Genera un reporte de status estructurado en estados semánticos (Rojo, Gris, Verde).
Compara el historial de proyectos en `03 Log/` hasta <FECHA_HASTA>.

Uso:
  python generate_status_report.py <VAULT_PATH> <FECHA_DESDE> <FECHA_HASTA> [--umbral-estancamiento N]
"""

import os
import sys
import argparse
from asana_obsidian_sync import slugify

def parse_snapshot(path):
    """Parsea el archivo markdown de snapshot para extraer los proyectos.
    Devuelve un dict: gid -> { name, status, total, done, blocked, due_date, pct, replans, slip, blocker }
    """
    if not os.path.exists(path):
        return None
        
    out = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("|") and not line.startswith("| asana_gid") and not line.startswith("|---"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 9:
                    gid = parts[1]
                    if not gid:
                        continue
                    
                    name = parts[2].replace("\\|", "|")
                    status = parts[3]
                    
                    try: total = int(parts[4])
                    except ValueError: total = 0
                    
                    try: done = int(parts[5])
                    except ValueError: done = 0
                        
                    try: blocked = int(parts[6])
                    except ValueError: blocked = 0
                        
                    due_date = parts[7]
                    
                    try: pct = int(parts[8])
                    except ValueError: pct = 0
                        
                    replans = 0
                    slip = 0
                    blocker = "Ninguno listado"
                    
                    if len(parts) >= 12:
                        try: replans = int(parts[9])
                        except ValueError: replans = 0
                        try: slip = int(parts[10])
                        except ValueError: slip = 0
                        blocker = parts[11].replace("\\|", "|") or "Ninguno listado"
                        
                    filename = None
                    if len(parts) >= 14:
                        filename = parts[12].strip()
                        
                    milestones = 0
                    milestones_done = 0
                    next_milestone_date = ""
                    workspace = ""
                    if len(parts) >= 17:
                        try: milestones = int(parts[13])
                        except ValueError: milestones = 0
                        try: milestones_done = int(parts[14])
                        except ValueError: milestones_done = 0
                        next_milestone_date = parts[15].strip()
                    if len(parts) >= 18:
                        workspace = parts[16].strip()
                        
                    out[gid] = {
                        "name": name,
                        "status": status,
                        "total": total,
                        "done": done,
                        "blocked": blocked,
                        "due_date": due_date,
                        "pct": pct,
                        "replans": replans,
                        "slip": slip,
                        "blocker": blocker,
                        "filename": filename,
                        "milestones": milestones,
                        "milestones_done": milestones_done,
                        "next_milestone_date": next_milestone_date,
                        "workspace": workspace
                    }
                    
    return out

import re

def get_historical_snapshots(log_dir, fecha_hasta):
    """Devuelve un dict fecha -> snapshot parseado, ordenado cronológicamente hasta fecha_hasta."""
    hist = {}
    if not os.path.isdir(log_dir):
        return hist
    
    date_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
    for f in os.listdir(log_dir):
        match = date_pattern.match(f)
        if match:
            fecha_str = match.group(1)
            if fecha_str <= fecha_hasta:
                snap = parse_snapshot(os.path.join(log_dir, f))
                if snap is not None and len(snap) > 0:
                    hist[fecha_str] = snap
    return dict(sorted(hist.items()))

def generate_report(vault, d_desde, d_hasta, umbral_estancamiento):
    log_dir = os.path.join(vault, "03 Log")
    hist = get_historical_snapshots(log_dir, d_hasta)
    
    if d_desde not in hist:
        print(f"Error: Snapshot no encontrado (o vacío/corrupto) para la fecha desde ({d_desde})")
        sys.exit(1)
        
    if d_hasta not in hist:
        print(f"Error: Snapshot no encontrado (o vacío/corrupto) para la fecha hasta ({d_hasta})")
        sys.exit(1)
        
    snap_desde = hist[d_desde]
    snap_hasta = hist[d_hasta]
    
    sorted_dates = list(hist.keys())
    
    rojos = []
    grises = []
    verdes = []
    
    for gid, hasta in snap_hasta.items():
        desde = snap_desde.get(gid)
        
        estado = None
        razon = ""
        
        if not desde:
            estado = "gris"
            razon = "Nuevo desde el último corte"
        elif hasta["total"] == 0:
            estado = "gris"
            razon = "Sin tareas"
        else:
            if hasta["blocked"] > desde["blocked"]:
                estado = "rojo"
                razon = f"Aumentaron tareas bloqueadas ({desde['blocked']} -> {hasta['blocked']})"
            elif hasta["due_date"] != desde["due_date"]:
                estado = "rojo"
                razon = f"Fecha movida: {desde['due_date'] or 'Ninguna'} ➡️ {hasta['due_date'] or 'Ninguna'}"
            elif hasta["next_milestone_date"] != desde["next_milestone_date"] and desde["next_milestone_date"] and hasta["next_milestone_date"] > desde["next_milestone_date"]:
                estado = "rojo"
                razon = f"Hito demorado: {desde['next_milestone_date']} ➡️ {hasta['next_milestone_date']}"
            elif hasta["milestones_done"] < desde["milestones_done"]:
                estado = "rojo"
                razon = f"Hito reabierto ({desde['milestones_done']} -> {hasta['milestones_done']})"
            elif hasta["due_date"] and hasta["due_date"] < d_hasta and hasta["pct"] < 100:
                estado = "rojo"
                razon = f"Proyecto vencido ({hasta['due_date']})"
            elif hasta["next_milestone_date"] and hasta["next_milestone_date"] < d_hasta:
                estado = "rojo"
                razon = f"Próximo hito vencido ({hasta['next_milestone_date']})"
            else:
                if hasta["pct"] > desde["pct"]:
                    estado = "verde"
                    razon = f"Avanzó: {desde['pct']}% ➡️ {hasta['pct']}%"
                else:
                    if len(sorted_dates) >= umbral_estancamiento:
                        recent_dates = sorted_dates[-umbral_estancamiento:]
                        stalled = True
                        for d in recent_dates:
                            s = hist[d].get(gid)
                            if not s or s["pct"] != hasta["pct"]:
                                stalled = False
                                break
                        if stalled:
                            estado = "rojo"
                            razon = f"Estancado en {hasta['pct']}% por {umbral_estancamiento} cortes consecutivos"
                        else:
                            estado = "gris"
                            razon = "Sin movimiento reciente (menos del umbral crítico)"
                    else:
                        estado = "gris"
                        razon = "Sin movimiento reciente (menos del umbral crítico)"
                        
        filename = hasta.get("filename")
        slug = filename if filename else slugify(hasta["name"], fallback_gid=gid)
        
        item = {
            "gid": gid,
            "name": hasta["name"],
            "slug": slug,
            "razon": razon,
            "replan_count": hasta["replans"],
            "slip_days": hasta["slip"],
            "critical_blocker": hasta["blocker"]
        }
            
        if estado == "rojo":
            rojos.append(item)
        elif estado == "gris":
            grises.append(item)
        elif estado == "verde":
            verdes.append(item)
            
    for gid, desde in snap_desde.items():
        if gid not in snap_hasta:
            filename = desde.get("filename")
            slug = filename if filename else slugify(desde["name"], fallback_gid=gid)
            grises.append({
                "gid": gid,
                "name": desde["name"],
                "slug": slug,
                "razon": "Ya no aparece en Asana (archivado/borrado)",
                "critical_blocker": "-",
                "replan_count": 0,
                "slip_days": 0
            })
            
    rojos.sort(key=lambda x: x["name"])
    grises.sort(key=lambda x: x["name"])
    verdes.sort(key=lambda x: x["name"])

    lines = []
    lines.append(f"# Status Report: {d_desde} a {d_hasta}")
    lines.append("")
    
    lines.append("## 🔴 Alertas Rojas")
    if not rojos:
        lines.append("*Sin proyectos en riesgo detectados.*")
    else:
        for r in rojos:
            lines.append(f"- **[[{r['slug']}]]**: {r['razon']}")
            lines.append(f"  - **Bloqueador Crítico**: {r['critical_blocker']}")
            if r['replan_count'] or r['slip_days']:
                lines.append(f"  - **Replans**: {r['replan_count']} | **Slip Days**: {r['slip_days']}")
            
    lines.append("")
    lines.append("## ⚪️ Proyectos en Gris")
    if not grises:
        lines.append("*Sin proyectos en gris.*")
    else:
        for g in grises:
            lines.append(f"- **[[{g['slug']}]]**: {g['razon']}")
            
    lines.append("")
    lines.append("## 🟢 Avance")
    if not verdes:
        lines.append("*Sin progreso medible en este periodo.*")
    else:
        for v in verdes:
            lines.append(f"- **[[{v['slug']}]]**: {v['razon']}")

    lines.append("")
    lines.append("## Comité")
    necesitan_comite = [r for r in rojos if r['critical_blocker'] and r['critical_blocker'] not in ["Ninguno listado", "-"]]
    if necesitan_comite:
        lines.append("- Proyectos con bloqueadores críticos que requieren destrabe:")
        for r in necesitan_comite:
            lines.append(f"  - **[[{r['slug']}]]**: {r['critical_blocker']}")
    else:
        lines.append("- *(No se han detectado bloqueos críticos para escalar al comité)*")
    
    report_path = os.path.join(log_dir, f"Reporte {d_hasta}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
        
    print(f"Reporte generado en {report_path}")
    return report_path
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser("Generar Status Report comparando dos snapshots temporales.")
    parser.add_argument("vault", help="Ruta al vault de Obsidian")
    parser.add_argument("desde", help="Fecha inicial YYYY-MM-DD")
    parser.add_argument("hasta", help="Fecha final YYYY-MM-DD")
    parser.add_argument("--umbral-estancamiento", type=int, default=3, help="Cortes sin movimiento para clasificar como riesgo")
    args = parser.parse_args()
    
    generate_report(args.vault, args.desde, args.hasta, args.umbral_estancamiento)

