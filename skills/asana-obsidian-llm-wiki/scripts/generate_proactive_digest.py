import json
import os
import re
import argparse
from datetime import datetime
import sys

from generate_status_report import parse_snapshot

def get_latest_snapshot(log_dir):
    if not os.path.isdir(log_dir):
        return None, None
    date_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
    files = []
    for f in os.listdir(log_dir):
        match = date_pattern.match(f)
        if match:
            files.append(match.group(1))
    if not files:
        return None, None
    latest = sorted(files)[-1]
    return latest, parse_snapshot(os.path.join(log_dir, f"{latest}.md"))

def evaluate_project(s_state, hasta, today_str, umbral_dias):
    desde = s_state.get("snapshot_metrics") if s_state else None
    s_date = s_state.get("last_notified_date") if s_state else today_str
    
    # 1. Absolute REDs
    if hasta.get("blocked", 0) > 0:
        return "rojo", f"Bloqueado ({hasta['blocked']} tareas)"
    if hasta.get("due_date") and hasta["due_date"] < today_str and hasta.get("pct", 0) < 100:
        return "rojo", f"Vencido ({hasta['due_date']})"
    if hasta.get("next_milestone_date") and hasta["next_milestone_date"] < today_str:
        return "rojo", f"Hito vencido ({hasta['next_milestone_date']})"
        
    # 2. Delta REDs (Worsened)
    if desde:
        if hasta.get("due_date") != desde.get("due_date"):
            return "rojo", f"Fecha movida ({desde.get('due_date')} -> {hasta.get('due_date')})"
        if hasta.get("next_milestone_date") != desde.get("next_milestone_date") and desde.get("next_milestone_date") and hasta.get("next_milestone_date") and hasta["next_milestone_date"] > desde["next_milestone_date"]:
            return "rojo", f"Hito demorado ({desde['next_milestone_date']} -> {hasta['next_milestone_date']})"
        if hasta.get("milestones_done", 0) < desde.get("milestones_done", 0):
            return "rojo", f"Hito reabierto"
            
        # Stalled
        if hasta.get("pct", 0) == desde.get("pct", 0) and hasta.get("pct", 0) < 100 and hasta.get("total", 0) > 0:
            d1 = datetime.strptime(today_str, "%Y-%m-%d")
            d2 = datetime.strptime(s_date, "%Y-%m-%d")
            days = (d1 - d2).days
            was_stalled = s_state.get("last_notified_state") == "rojo" and "Estancado" in s_state.get("last_notified_reason", "")
            if days >= umbral_dias or was_stalled:
                return "rojo", f"Estancado en {hasta['pct']}%"
                
    # 3. VERDEs (Recovered or progressed)
    if desde:
        if hasta.get("pct", 0) > desde.get("pct", 0):
            return "verde", f"Avanzó ({desde['pct']}% -> {hasta['pct']}%)"
        if desde.get("blocked", 0) > 0 and hasta.get("blocked", 0) == 0:
            return "verde", "Bloqueos resueltos"
            
    return "gris", "Sin cambios"

def generate_digest(vault, umbral_dias=7, max_items=10, dry_run=False):
    log_dir = os.path.join(vault, "03 Log")
    state_file = os.path.join(vault, "99 System", "digest-state.json")
    
    today_str, current_snap = get_latest_snapshot(log_dir)
    if not current_snap:
        print("No hay snapshots en 03 Log/")
        return 0
        
    state = {}
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            state = json.load(f)
            
    alerts = []
    new_state = dict(state)
    
    for gid, hasta in current_snap.items():
        s_state = state.get(gid)
        estado, razon = evaluate_project(s_state, hasta, today_str, umbral_dias)
        
        last_state = s_state.get("last_notified_state") if s_state else None
        last_reason = s_state.get("last_notified_reason") if s_state else None
        last_date = s_state.get("last_notified_date") if s_state else today_str
        
        name = hasta.get("name", "Unknown")
        
        emit = False
        prefix = ""
        
        if estado == "rojo":
            if last_state != "rojo":
                emit = True
                prefix = "🔴 NUEVO"
            elif razon != last_reason:
                emit = True
                prefix = "🔴 EMPEORÓ"
            else:
                d1 = datetime.strptime(today_str, "%Y-%m-%d")
                d2 = datetime.strptime(last_date, "%Y-%m-%d")
                if (d1 - d2).days >= umbral_dias:
                    emit = True
                    prefix = "🔴 RECORDATORIO"
                    
            if emit:
                alerts.append({"gid": gid, "name": name, "msg": f"{prefix}: {name} - {razon}"})
                new_state[gid] = {
                    "last_notified_date": today_str,
                    "last_notified_state": "rojo",
                    "last_notified_reason": razon,
                    "snapshot_metrics": hasta
                }
                
        elif estado in ["verde", "gris"]:
            if last_state == "rojo":
                emit = True
                prefix = "🟢 RECUPERADO"
                alerts.append({"gid": gid, "name": name, "msg": f"{prefix}: {name}"})
                new_state[gid] = {
                    "last_notified_date": today_str,
                    "last_notified_state": estado,
                    "last_notified_reason": razon,
                    "snapshot_metrics": hasta
                }
            else:
                # No emitimos nada si no estaba en rojo. No actualizamos el estado para no perder el baseline de "Estancado".
                # Excepto si es la primera vez que lo vemos, lo guardamos como gris/verde silenciosamente
                if not s_state:
                    new_state[gid] = {
                        "last_notified_date": today_str,
                        "last_notified_state": estado,
                        "last_notified_reason": razon,
                        "snapshot_metrics": hasta
                    }

    if alerts:
        print(f"## 📬 Digest Proactivo ({today_str})\n")
        count = len(alerts)
        for i, a in enumerate(alerts):
            if i < max_items:
                print(f"- {a['msg']}")
            else:
                print(f"\n... y {count - max_items} proyectos adicionales requieren tu atención.")
                break
                
        if not dry_run:
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            with open(state_file, "w") as f:
                json.dump(new_state, f, indent=2)
    else:
        print(f"## 📬 Digest Proactivo ({today_str})\n\n*Todo en orden. No hay alertas nuevas ni recordatorios hoy.*")

    return len(alerts)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("vault")
    parser.add_argument("--umbral", type=int, default=7)
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    generate_digest(args.vault, args.umbral, args.max_items, args.dry_run)
