#!/usr/bin/env python3
"""
unifilar.py - Lectura, edicion, validacion y render de diagramas unifilares.

El diagrama vive como JSON (fuente de verdad, editable y versionable en git).
El SVG es solo una vista generada. Nunca editar el SVG a mano.

Uso:
  python3 scripts/unifilar.py validar  --json ejemplos/proyecto-demo/unifilar.json
  python3 scripts/unifilar.py render   --json ejemplos/proyecto-demo/unifilar.json --svg salida.svg
  python3 scripts/unifilar.py describir --json ejemplos/proyecto-demo/unifilar.json
  python3 scripts/unifilar.py agregar  --json u.json --padre TG-1 --id TD-3 --tipo tablero \
        --descripcion "Tablero oficinas" --tension 208 --fases 3 --interruptor 100 --calibre 3

Modelo (ver referencias/esquema-unifilar.md):
  nodo = {id, tipo, descripcion, tension_V, fases, hilos, interruptor_A, sccr_kA,
          calibre, material, egc, longitud_m, carga_va, padre, notas[]}
  tipo in: acometida, medidor, transformador, interruptor_principal, tablero,
           barra, carga, motor, generador, ups, bess, fotovoltaico, cargador_ve,
           transferencia, capacitor
"""

import argparse
import json
import sys
from xml.sax.saxutils import escape as _esc

TIPOS = {
    "acometida", "medidor", "transformador", "interruptor_principal", "tablero",
    "barra", "carga", "motor", "generador", "ups", "bess", "fotovoltaico",
    "cargador_ve", "transferencia", "capacitor",
}

SIMBOLO = {
    "acometida": "ACOM", "medidor": "kWh", "transformador": "TR",
    "interruptor_principal": "IP", "tablero": "TAB", "barra": "BUS",
    "carga": "CG", "motor": "M", "generador": "G", "ups": "UPS",
    "bess": "BESS", "fotovoltaico": "PV", "cargador_ve": "EVSE",
    "transferencia": "ATS", "capacitor": "CAP",
}


def cargar(ruta):
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


def guardar(ruta, doc):
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)


def indexar(doc):
    return {n["id"]: n for n in doc["nodos"]}


def hijos_de(doc, pid):
    return [n for n in doc["nodos"] if n.get("padre") == pid]


def raices(doc):
    ids = {n["id"] for n in doc["nodos"]}
    return [n for n in doc["nodos"] if not n.get("padre") or n.get("padre") not in ids]


# ----------------------------------------------------------------- validar

def validar(doc, icc_por_nodo=None):
    """icc_por_nodo: {id: kA} de `ec.py cortocircuito`. Sin el, el SCCR se compara contra
    la icc_disponible_kA unica del diagrama."""
    hallazgos = []
    idx = indexar(doc)
    icc_por_nodo = icc_por_nodo or {}

    def add(sev, nid, msg, ref=""):
        hallazgos.append({"severidad": sev, "nodo": nid, "hallazgo": msg, "referencia": ref})

    vistos = set()
    for n in doc["nodos"]:
        nid = n.get("id", "?")
        if nid in vistos:
            add("ERROR", nid, "ID duplicado.", "")
        vistos.add(nid)
        if n.get("tipo") not in TIPOS:
            add("ERROR", nid, f"Tipo '{n.get('tipo')}' no reconocido.", "")
        if n.get("padre") and n["padre"] not in idx:
            add("ERROR", nid, f"El padre '{n['padre']}' no existe en el diagrama.", "")
        if n.get("tipo") in ("tablero", "barra", "carga", "motor") and not n.get("tension_V"):
            add("ADVERTENCIA", nid, "Sin tension declarada.", "")

    # ciclos
    for n in doc["nodos"]:
        visto, cur = set(), n
        while cur and cur.get("padre"):
            if cur["id"] in visto:
                add("ERROR", n["id"], "Ciclo detectado en la jerarquia.", "")
                break
            visto.add(cur["id"])
            cur = idx.get(cur["padre"])

    # coordinacion aguas arriba / aguas abajo
    for n in doc["nodos"]:
        padre = idx.get(n.get("padre", ""))
        if padre and n.get("interruptor_A") and padre.get("interruptor_A"):
            if n["interruptor_A"] > padre["interruptor_A"]:
                add("ERROR", n["id"],
                    f"Interruptor de {n['interruptor_A']} A mayor que el de aguas arriba "
                    f"({padre['id']}: {padre['interruptor_A']} A). Coordinacion invertida.",
                    "NEC 240.4 / 240.21")

    # SCCR
    for n in doc["nodos"]:
        if n.get("tipo") in ("tablero", "barra", "interruptor_principal"):
            icc = icc_por_nodo.get(n["id"]) or doc.get("icc_disponible_kA")
            origen = "Icc calculada en el nodo" if icc_por_nodo.get(n["id"]) else "Icc disponible"
            if not n.get("sccr_kA"):
                add("ADVERTENCIA", n["id"],
                    "Sin SCCR declarado. Debe verificarse contra la corriente de "
                    "cortocircuito disponible.", "NEC 110.9, 110.10, 409.110")
            elif icc and n["sccr_kA"] < icc:
                add("ERROR", n["id"],
                    f"SCCR {n['sccr_kA']} kA < {origen} {icc} kA.",
                    "NEC 110.9")

    # tierras
    for n in doc["nodos"]:
        if n.get("interruptor_A") and not n.get("egc") and n.get("tipo") != "acometida":
            add("ADVERTENCIA", n["id"], "Sin conductor de puesta a tierra de equipos declarado.",
                "NEC 250.122")

    # carga vs capacidad del tablero
    for n in doc["nodos"]:
        if n.get("tipo") in ("tablero", "barra"):
            suma = sum(float(h.get("carga_va") or 0) for h in hijos_de(doc, n["id"]))
            if suma and n.get("tension_V") and n.get("interruptor_A"):
                mult = 1.732 if int(n.get("fases", 3)) == 3 else 1.0
                cap = n["interruptor_A"] * n["tension_V"] * mult
                if suma > cap:
                    add("ERROR", n["id"],
                        f"Carga conectada {suma:,.0f} VA excede la capacidad del "
                        f"interruptor principal ({cap:,.0f} VA).", "NEC 220 / 408.36")
                elif suma > 0.8 * cap:
                    add("ADVERTENCIA", n["id"],
                        f"Carga conectada al {suma / cap * 100:.0f}% de la capacidad. "
                        "Sin margen para crecimiento.", "")

    # transformadores
    for n in doc["nodos"]:
        if n.get("tipo") == "transformador":
            if not n.get("proteccion_primario_A") or not n.get("proteccion_secundario_A"):
                add("ADVERTENCIA", n["id"],
                    "Proteccion de primario/secundario incompleta.", "NEC 450.3")
            if not n.get("conexion"):
                add("ADVERTENCIA", n["id"],
                    "Sin grupo de conexion (p.ej. Dyn11). Afecta puesta a tierra del "
                    "sistema derivado separadamente.", "NEC 250.30")

    return hallazgos


# ---------------------------------------------------------------- describir

def describir(doc, nid=None, nivel=0, salida=None):
    salida = salida if salida is not None else []
    nodos = raices(doc) if nid is None else hijos_de(doc, nid)
    for n in nodos:
        pref = "  " * nivel + ("└─ " if nivel else "")
        partes = [f"[{n['id']}] {n.get('descripcion', n.get('tipo'))}"]
        if n.get("tension_V"):
            partes.append(f"{n['tension_V']}V/{n.get('fases', 3)}F-{n.get('hilos', 4)}H")
        if n.get("interruptor_A"):
            partes.append(f"ITM {n['interruptor_A']}A")
        if n.get("calibre"):
            partes.append(f"{n.get('conductores_por_fase', 1)}x{n['calibre']} {n.get('material', 'Cu')}")
        if n.get("egc"):
            partes.append(f"PT {n['egc']}")
        if n.get("carga_va"):
            partes.append(f"{float(n['carga_va']):,.0f} VA")
        salida.append(pref + "  ".join(partes))
        describir(doc, n["id"], nivel + 1, salida)
    return salida


# ------------------------------------------------------------------ render

def _posiciones(doc):
    """Layout jerarquico simple: profundidad -> y, orden -> x."""
    pos, y_por_nivel = {}, {}
    ANCHO, ALTO = 230, 120

    def recorrer(nid, nivel):
        hs = hijos_de(doc, nid) if nid else raices(doc)
        for n in hs:
            y = y_por_nivel.get(nivel, 0)
            y_por_nivel[nivel] = y + 1
            pos[n["id"]] = (60 + nivel * ANCHO, 60 + y * ALTO)
            recorrer(n["id"], nivel + 1)

    recorrer(None, 0)
    # centrar padres respecto a sus hijos
    for n in reversed(doc["nodos"]):
        hs = hijos_de(doc, n["id"])
        if hs and n["id"] in pos:
            ys = [pos[h["id"]][1] for h in hs if h["id"] in pos]
            if ys:
                pos[n["id"]] = (pos[n["id"]][0], sum(ys) / len(ys))
    return pos


def render_svg(doc, ruta):
    pos = _posiciones(doc)
    idx = indexar(doc)
    if not pos:
        raise SystemExit("Diagrama vacio.")
    maxx = max(p[0] for p in pos.values()) + 260
    maxy = max(p[1] for p in pos.values()) + 120
    W, H = 190, 62

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {maxx:.0f} {maxy:.0f}" '
         f'width="{maxx:.0f}" height="{maxy:.0f}" font-family="Helvetica,Arial,sans-serif">']
    s.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    s.append(f'<text x="30" y="34" font-size="17" font-weight="bold">'
             f'{_esc(str(doc.get("proyecto", "Diagrama unifilar")))}</text>')
    s.append(f'<text x="30" y="52" font-size="11" fill="#555">'
             f'{_esc(str(doc.get("norma", "")))} | Icc disp: {_esc(str(doc.get("icc_disponible_kA", "n/d")))} kA | '
             f'Rev {_esc(str(doc.get("revision", "0")))}</text>')

    # conexiones
    for n in doc["nodos"]:
        if n.get("padre") in pos and n["id"] in pos:
            x1, y1 = pos[n["padre"]]
            x2, y2 = pos[n["id"]]
            mx = x1 + W + (x2 - x1 - W) / 2
            s.append(f'<path d="M{x1 + W:.0f},{y1 + H / 2:.0f} H{mx:.0f} V{y2 + H / 2:.0f} '
                     f'H{x2:.0f}" stroke="#222" stroke-width="1.6" fill="none"/>')
            etq = []
            if n.get("interruptor_A"):
                etq.append(f"{n['interruptor_A']}A")
            if n.get("calibre"):
                cpf = n.get("conductores_por_fase", 1)
                pref = f"{cpf}x" if cpf > 1 else ""
                etq.append(f"{pref}{n['calibre']}")
            if n.get("egc"):
                etq.append(f"PT {n['egc']}")
            if etq:
                s.append(f'<text x="{mx + 5:.0f}" y="{y2 + H / 2 - 6:.0f}" font-size="10" '
                         f'fill="#0b5">{_esc(" / ".join(etq))}</text>')

    # nodos
    for n in doc["nodos"]:
        if n["id"] not in pos:
            continue
        x, y = pos[n["id"]]
        tipo = n.get("tipo", "carga")
        relleno = {"acometida": "#eef4ff", "transformador": "#fff4e6", "tablero": "#eefaf1",
                   "bess": "#f3eeff", "fotovoltaico": "#fffbe6", "cargador_ve": "#e6fbff",
                   "generador": "#ffeef0"}.get(tipo, "#f7f7f7")
        s.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{W}" height="{H}" rx="5" '
                 f'fill="{relleno}" stroke="#333" stroke-width="1.4"/>')
        s.append(f'<text x="{x + 8:.0f}" y="{y + 17:.0f}" font-size="11" font-weight="bold">'
                 f'{SIMBOLO.get(tipo, "?")} {_esc(str(n["id"]))}</text>')
        desc = _esc(str(n.get("descripcion", "") or "")[:30])
        s.append(f'<text x="{x + 8:.0f}" y="{y + 32:.0f}" font-size="9.5" fill="#333">{desc}</text>')
        l3 = []
        if n.get("tension_V"):
            l3.append(f"{n['tension_V']}V {n.get('fases', 3)}F-{n.get('hilos', 4)}H")
        if n.get("carga_va"):
            l3.append(f"{float(n['carga_va']):,.0f}VA")
        s.append(f'<text x="{x + 8:.0f}" y="{y + 46:.0f}" font-size="9" fill="#555">'
                 f'{_esc("  ".join(l3))}</text>')
        if n.get("sccr_kA"):
            s.append(f'<text x="{x + 8:.0f}" y="{y + 58:.0f}" font-size="8.5" fill="#777">'
                     f'SCCR {_esc(str(n["sccr_kA"]))}kA</text>')

    s.append('</svg>')
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(s))
    return ruta


# --------------------------------------------------------------------- CLI

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Diagramas unifilares como datos")
    sub = p.add_subparsers(dest="cmd", required=True)

    for c in ("validar", "describir"):
        q = sub.add_parser(c)
        q.add_argument("--json", required=True)
        if c == "validar":
            q.add_argument("--cortocircuito",
                           help="Salida de `ec.py cortocircuito`: compara el SCCR contra la Icc de cada nodo")

    r = sub.add_parser("render")
    r.add_argument("--json", required=True)
    r.add_argument("--svg", required=True)

    a_ = sub.add_parser("agregar")
    a_.add_argument("--json", required=True)
    a_.add_argument("--id", required=True)
    a_.add_argument("--padre")
    a_.add_argument("--tipo", required=True)
    a_.add_argument("--descripcion", default="")
    a_.add_argument("--tension", type=float)
    a_.add_argument("--fases", type=int, default=3)
    a_.add_argument("--hilos", type=int, default=4)
    a_.add_argument("--interruptor", type=float)
    a_.add_argument("--calibre")
    a_.add_argument("--egc")
    a_.add_argument("--carga-va", type=float)
    a_.add_argument("--sccr", type=float)
    a_.add_argument("--kva", type=float, help="Transformadores: potencia de placa")
    a_.add_argument("--z-pct", type=float, help="Transformadores: impedancia de placa en %%")

    a = p.parse_args()
    doc = cargar(a.json)

    if a.cmd == "validar":
        icc = None
        if a.cortocircuito:
            icc = {n["id"]: n.get("icc_total_kA") for n in cargar(a.cortocircuito).get("nodos", [])}
        h = validar(doc, icc)
        errores = sum(1 for x in h if x["severidad"] == "ERROR")
        print(json.dumps({"total": len(h), "errores": errores,
                          "advertencias": len(h) - errores, "hallazgos": h},
                         indent=2, ensure_ascii=False))
        sys.exit(1 if errores else 0)

    if a.cmd == "describir":
        print("\n".join(describir(doc)))
        return

    if a.cmd == "render":
        print(render_svg(doc, a.svg))
        return

    if a.cmd == "agregar":
        if a.id in indexar(doc):
            raise SystemExit(f"El nodo {a.id} ya existe.")
        nuevo = {"id": a.id, "tipo": a.tipo, "descripcion": a.descripcion}
        for k, v in (("padre", a.padre), ("tension_V", a.tension), ("fases", a.fases),
                     ("hilos", a.hilos), ("interruptor_A", a.interruptor),
                     ("calibre", a.calibre), ("egc", a.egc), ("carga_va", a.carga_va),
                     ("sccr_kA", a.sccr), ("kva", a.kva), ("z_pct", a.z_pct)):
            if v is not None:
                nuevo[k] = v
        doc["nodos"].append(nuevo)
        guardar(a.json, doc)
        h = validar(doc)
        print(json.dumps({"agregado": a.id, "hallazgos_tras_edicion": h},
                         indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
