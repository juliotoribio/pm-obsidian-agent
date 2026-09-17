#!/usr/bin/env python3
import os

def check():
    print("Iniciando chequeo de salud (Healthcheck)...")
    token = os.environ.get("ASANA_ACCESS_TOKEN")
    if not token:
        print("FAIL: ASANA_ACCESS_TOKEN no encontrado.")
    else:
        print("OK: Token encontrado.")
    
    vault = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault or not os.path.exists(vault):
        print(f"FAIL: Bóveda no encontrada en la ruta: {vault}")
    else:
        print("OK: Ruta de la bóveda validada.")

if __name__ == "__main__":
    check()
