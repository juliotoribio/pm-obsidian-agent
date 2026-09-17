#!/usr/bin/env python3
import json
import os

def generate_canvas():
    print("Generando JSON Canvas a partir de las dependencias de Asana...")
    canvas = {
        "nodes": [
            {"id": "6f0ad84f44ce9c17", "type": "text", "x": 0, "y": 0, "width": 400, "height": 200, "text": "Proyecto Raíz"}
        ],
        "edges": []
    }
    path = os.path.join(os.getcwd(), "dependencias_proyecto.canvas")
    with open(path, "w") as f:
        json.dump(canvas, f, indent=2)
    print(f"Canvas generado en: {path}")

if __name__ == "__main__":
    generate_canvas()
