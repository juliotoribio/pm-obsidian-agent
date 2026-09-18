#!/usr/bin/env python3
"""
generate_status_report.py

Compara dos snapshots en `03 Log/` y genera un reporte ejecutivo de estado.
Uso:
  python generate_status_report.py <VAULT_PATH> <FECHA_DESDE> <FECHA_HASTA>
"""

import os
import sys
import argparse
import re
from asana_obsidian_sync import scan_existing_notes

def parse_snapshot(path):
    """Parsea el archivo markdown de snapshot para extraer los proyectos.
    Devuelve un dict: gid -> { name, status, total, done, blocked, due_date, pct }
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
                    
                    try:
                        total = int(parts[4])
                    except:
                        total = 0
                    
                    try:
                        done = int(parts[5])
                    except:
                        done = 0
                        
                    try:
                        blocked = int(parts[6])
                    except:
                        blocked = 0
                        
                    due_date = parts[7]
                    
                    try:
                        pct = int(parts[8])
                    except:
                        pct = 0
                        
                    out[gid] = {
                        "name": name,
                        "status": status,
                        "total": total,
                        "done": done,
                        "blocked": blocked,
                        "due_date": due_date,
                        "pct": pct
                    }
    return out

def generate_report(vault, d_desde, d_hasta):
    log_dir = os.path.join(vault, "03 Log")
    path_desde = os.path.join(log_dir, f"{d_desde}.md")
    path_hasta = os.path.join(log_dir, f"{d_hasta}.md")
    
    snap_desde = parse_snapshot(path_desde)
    if snap_desde is None:
        print(f"Error: Snapshot no encontrado para la fecha desde ({path_desde})")
        sys.exit(1)
        
    snap_hasta = parse_snapshot(path_hasta)
    if snap_hasta is None:
        print(f"Error: Snapshot no encontrado para la fecha hasta ({path_hasta})")
        sys.exit(1)
        
    existing_notes = scan_existing_notes(vault)
    
    fechas_movidas = []
    alertas_rojas = []
    
    for gid, hasta in snap_hasta.items():
        desde = snap_desde.get(gid)
        if not desde:
            continue
            
        is_rojo = False
        # Riesgo: no avanzó el %, aumentaron los blockers, o tiene % bajo cerca a vencer (simplificado)
        if hasta["blocked"] > desde["blocked"]:
            is_rojo = True
            razon = f"Aumentaron tareas bloqueadas ({desde['blocked']} -> {hasta['blocked']})"
        elif hasta["pct"] == desde["pct"] and hasta["pct"] < 100 and hasta["total"] > 0:
            is_rojo = True
            razon = f"Estancado en {hasta['pct']}%"
            
        if is_rojo:
            alertas_rojas.append({
                "gid": gid,
                "name": hasta["name"],
                "razon": razon
            })
            
        # Fecha movida
        if hasta["due_date"] != desde["due_date"]:
            fechas_movidas.append({
                "gid": gid,
                "name": hasta["name"],
                "old_due": desde["due_date"],
                "new_due": hasta["due_date"]
            })
            
    # Enriquecer leyendo las notas
    for lst in [alertas_rojas, fechas_movidas]:
        for item in lst:
            note = existing_notes.get(item["gid"])
            if note:
                fm = note["fm"]
                item["critical_blocker"] = fm.get("critical_blocker") or "Ninguno listado"
                item["replan_count"] = fm.get("replan_count") or 0
                item["slip_days"] = fm.get("slip_days") or 0
            else:
                item["critical_blocker"] = "Desconocido (nota borrada)"
                item["replan_count"] = 0
                item["slip_days"] = 0
                
    # Build markdown
    lines = []
    lines.append(f"# Status Report: {d_desde} a {d_hasta}")
    lines.append("")
    
    lines.append("## 🚨 Alertas Rojas")
    if not alertas_rojas:
        lines.append("*Sin proyectos en riesgo detectados.*")
    else:
        for r in alertas_rojas:
            lines.append(f"- **[[{r['name']}]]**: {r['razon']}")
            lines.append(f"  - **Bloqueador Crítico**: {r['critical_blocker']}")
            
    lines.append("")
    lines.append("## 🗓️ Fechas Movidas")
    if not fechas_movidas:
        lines.append("*Sin cambios de fecha detectados.*")
    else:
        for f in fechas_movidas:
            old = f['old_due'] or 'Ninguna'
            new = f['new_due'] or 'Ninguna'
            lines.append(f"- **[[{f['name']}]]**: {old} ➡️ {new}")
            lines.append(f"  - **Replans**: {f['replan_count']} | **Slip Days**: {f['slip_days']}")
            
    lines.append("")
    lines.append("## Comité")
    lines.append("- *(Decisiones requeridas)*")
    
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
    args = parser.parse_args()
    
    generate_report(args.vault, args.desde, args.hasta)

