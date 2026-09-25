#!/usr/bin/env python3
"""
squared.py - Sugerencia de tableros e interruptores Square D a partir del
unifilar, del calculo de cortocircuito y de los circuitos dimensionados.

Uso:
  python3 scripts/squared.py --unifilar unifilar.json --cortocircuito cortocircuito.json \
      --resultados resultados.json --salida squared.json --reporte squared.md

Reglas:
  - Familia por tension y capacidad: NQ hasta 240 V; NF en estrella con neutro y
    derivados de hasta 125 A; I-Line hasta 600 V y 1200 A; arriba, switchboard (consultar).
  - Capacidad interruptiva de cada interruptor >= Icc del tablero (ec.py cortocircuito),
    totalmente clasificado, sin combinaciones en serie.
  - Posiciones y fases de la cedula: arreglo de barras Square D (ec.py balanceo).
  - Los datos de catalogo salen de datos/catalogo_squared.json; lo marcado '_verificar'
    se confirma con el distribuidor antes de cotizar.
"""

import argparse
import json
import math
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(RAIZ, "datos", "catalogo_squared.json"), encoding="utf-8") as _fh:
    CAT = json.load(_fh)

TIPOS_DISTRIBUCION = {"tablero", "transformador", "bess", "fotovoltaico", "generador", "ups",
                      "transferencia", "barra", "interruptor_principal"}
PRINCIPALES = ["HD", "HG", "HJ", "HL", "JD", "JG", "JJ", "JL", "LG", "LJ"]


class DatoFaltante(Exception):
    """Dato ausente: preguntar al usuario, no suponerlo."""


def cargar(ruta):
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


def columna_kA(v):
    return "240" if v <= 240 else "480" if v <= 480 else "600"


def elegir_interruptor(familia, amperes, polos, v, icc):
    """Primer interruptor de la familia (marco menor, nivel menor) que cubre amperes, polos e Icc."""
    col = columna_kA(v)
    for tipo in CAT["tableros"][familia]["derivados"]:
        t = CAT["interruptores"][tipo]
        rango = t["amperes_por_polos"].get(str(polos))
        if not rango or not rango[0] <= amperes <= rango[1]:
            continue
        ka = t["kA"].get(col)
        if ka is None or ka < icc:
            continue
        notas = []
        if "sensores_A" in t:
            sensor = next(s for s in t["sensores_A"] if s >= amperes)
            catalogo = t["catalogo"].format(polos=polos, sensor=sensor)
            notas.append(f"sensor de {sensor} A con Ir ajustado a {amperes} A")
        else:
            catalogo = t["catalogo"].format(polos=polos, amperes=amperes)
            if "amperes" in t and amperes not in t["amperes"]:
                notas.append("amperaje fuera de la lista del catalogo: verificar")
        if t.get("_verificar"):
            notas.append("verificar rango de amperes con el distribuidor")
        return {"tipo": tipo, "familia": t["familia"], "kA": ka, "catalogo": catalogo, "nota": "; ".join(notas)}
    return None


def sistema_de(nodo):
    v = float(nodo.get("tension_V") or 0)
    tres = int(nodo.get("fases", 3)) == 3
    hilos = int(nodo.get("hilos", 4 if tres else 3))
    if tres:
        con_neutro = hilos >= 4
        nombre = f"{v:g}Y/{v / math.sqrt(3):.0f} V 3F-4H" if con_neutro else f"{v:g} V 3F-3H"
        return v, "3F-4H" if con_neutro else "3F-3H", nombre
    return v, "1F-3H", f"{v:g}/{v / 2:g} V 1F-3H"


def familia_para(v, sistema, principal, derivados, icc):
    """derivados: [(amperes, polos)]. Devuelve la primera familia que cubre todo, o None y el motivo."""
    motivos = []
    for fam in ("NQ", "NF", "I-Line"):
        f = CAT["tableros"][fam]
        if v > f["tension_max_V"]:
            continue
        if sistema not in f["sistemas"]:
            motivos.append(f"{fam}: no admite sistema {sistema}")
            continue
        pmax = f.get("principal_max_A") or max(f.get("principales_A", [0]))
        if principal and principal > pmax:
            motivos.append(f"{fam}: principal de {principal} A mayor que {pmax} A")
            continue
        faltan = [(a, p) for a, p in derivados if not elegir_interruptor(fam, a, p, v, icc)]
        if faltan:
            motivos.append(f"{fam}: sin interruptor para " + ", ".join(f"{a} A {p}P" for a, p in faltan))
            continue
        return fam, motivos
    return None, motivos


def principal_para(fam, im, v, icc):
    if not im:
        return {"descripcion": "Zapatas principales (sin interruptor principal)",
                "nota": "Protección en el alimentador aguas arriba."}
    f = CAT["tableros"][fam]
    if fam == "NQ":
        op = next((a for a in f["principales_A"] if a >= im), None)
        nota = "" if op == im else f"{im:g} A no es principal de catálogo NQ; verificar protección del alimentador."
        return {"descripcion": f"Interruptor principal NQ de {op} A", "amperes": op, "nota": nota}
    col = columna_kA(v)
    for tipo in PRINCIPALES:
        t = CAT["interruptores"][tipo]
        r = t["amperes_por_polos"].get("3")
        if r and r[0] <= im <= r[1] and t["kA"][col] >= icc:
            d = {"descripcion": f"{t['familia']}, {im:g} A, 3 polos, {t['kA'][col]} kA a {col} V",
                 "amperes": im, "tipo": tipo, "kA": t["kA"][col]}
            if fam == "I-Line":
                d["catalogo"] = elegir_interruptor("I-Line", im, 3, v, icc)["catalogo"]
            return d
    return {"descripcion": f"Principal de {im:g} A: marco M o P (consultar a Schneider Electric)", "amperes": im}


def sugerir(unifilar, cortocircuito, resultados=None, reserva_pct=25.0):
    nodos = unifilar.get("nodos", [])
    icc = {n["id"]: n.get("icc_total_kA") for n in cortocircuito.get("nodos", [])}
    circuitos = (resultados or {}).get("circuitos", [])
    cedulas = {t["tablero"]: {e["circuito"]: e for e in t["cedula"]}
               for t in (resultados or {}).get("balanceo", {}).get("tableros", [])}
    salida = []

    for nodo in nodos:
        if nodo.get("tipo") != "tablero":
            continue
        tid, avisos = nodo["id"], []
        v, sistema, nombre_sistema = sistema_de(nodo)
        i_cc = icc.get(tid)
        if not i_cc:
            raise DatoFaltante(f"{tid}: no hay Icc calculada. Correr primero `ec.py cortocircuito`.")

        propios = [c for c in circuitos if c.get("tablero") == tid]
        hijos = [h for h in nodos if h.get("padre") == tid]
        filas = []
        for c in propios:
            filas.append({"circuito": c["id"], "descripcion": c.get("nombre", ""),
                          "polos": int(c.get("polos") or c.get("fases") or 3),
                          "amperes": c["proteccion"]["capacidad_nominal_A"]})
        for h in hijos:
            if propios and h.get("tipo") not in TIPOS_DISTRIBUCION:
                continue
            amperes = h.get("proteccion_primario_A") if h.get("tipo") == "transformador" else h.get("interruptor_A")
            if not amperes:
                avisos.append(f"{h['id']}: alimentador sin capacidad de protección declarada.")
                continue
            filas.append({"circuito": h["id"], "descripcion": h.get("descripcion", ""),
                          "polos": int(h.get("fases", 3)), "amperes": amperes})
        if propios:
            avisos.append("Circuitos tomados del cuadro de cargas; del unifilar solo los alimentadores "
                          "a equipo de distribución (se omiten cargas repetidas).")

        derivados = [(f["amperes"], f["polos"]) for f in filas]
        fam, motivos = familia_para(v, sistema, nodo.get("interruptor_A"), derivados, i_cc)
        registro = {"id": tid, "descripcion": nodo.get("descripcion", ""), "sistema": nombre_sistema,
                    "icc_kA": i_cc, "familia": fam, "motivos_descarte": motivos}
        if fam is None:
            if any(p == 1 for _, p in derivados) and v <= 600:
                avisos.append("Los circuitos de 1 polo no caben en I-Line: alimentarlos desde un tablero NF o NQ derivado.")
            registro.update({"tablero_sugerido": "Ninguna familia cubre todos los circuitos (consultar)",
                             "interruptores": [], "avisos": avisos})
            salida.append(registro)
            continue

        ced = cedulas.get(tid, {})
        interruptores = []
        for f in filas:
            s = elegir_interruptor(fam, f["amperes"], f["polos"], v, i_cc)
            e = ced.get(f["circuito"], {})
            interruptores.append({**f, "posiciones": e.get("posiciones", []), "fases": e.get("fases", []), **s})
        principal = principal_para(fam, nodo.get("interruptor_A"), v, i_cc)
        f_cat = CAT["tableros"][fam]
        im = principal.get("amperes") or 0
        if "barras_A" in f_cat:
            barras = next((b for b in f_cat["barras_A"] if b >= im), None) if im else None
        else:
            barras = im if im and im <= f_cat["barras_max_A"] else None
        polos_usados = sum(f["polos"] for f in filas)
        espacios = None
        if fam in ("NQ", "NF"):
            espacios = math.ceil(polos_usados * (1 + reserva_pct / 100.0))
            espacios += espacios % 2
        niveles = [i["kA"] for i in interruptores] + ([principal["kA"]] if principal.get("kA") else [])
        sccr = min(niveles) if niveles else None
        declarado = nodo.get("sccr_kA")
        if declarado and sccr and declarado != sccr:
            avisos.append(f"El unifilar declara SCCR de {declarado} kA; con esta selección el tablero queda en "
                          f"{sccr} kA (Icc {i_cc} kA). Actualizar el unifilar o subir el nivel.")
        registro.update({
            "tablero_sugerido": f"Square D {fam}: {f_cat['descripcion']}",
            "barras_minimas_A": barras,
            "principal": principal,
            "polos_usados": polos_usados,
            "espacios_minimos": espacios,
            "reserva_pct": reserva_pct,
            "sccr_resultante_kA": sccr,
            "sccr_declarado_kA": declarado,
            "envolvente": "[COMPLETAR según ambiente: NEMA 1 interior seco, 3R intemperie, 4X lavado o corrosivo, 12 polvo]",
            "interruptores": sorted(interruptores, key=lambda x: (min(x["posiciones"]) if x["posiciones"] else 999)),
            "avisos": avisos,
        })
        salida.append(registro)

    return {
        "marca": CAT["_marca"],
        "advertencia": CAT["_ADVERTENCIA"],
        "criterios": {
            "capacidad_interruptiva": "Mayor o igual que la Icc del tablero (bus infinito, ec.py cortocircuito)",
            "reserva_espacios_pct": reserva_pct,
            "arreglo_barras": CAT["arreglo_barras"]["descripcion"],
        },
        "tableros": salida,
    }


def reporte(r):
    L = ["# Tableros e interruptores sugeridos — Square D\n",
         f"> {r['advertencia']}\n",
         f"Capacidad interruptiva: {r['criterios']['capacidad_interruptiva']}. "
         f"Reserva de espacios: {r['criterios']['reserva_espacios_pct']:g} %. "
         f"{r['criterios']['arreglo_barras']}\n"]
    for t in r["tableros"]:
        L.append(f"## {t['id']} — {t['descripcion']}\n")
        L.append(f"- Sistema: {t['sistema']} · Icc: {t['icc_kA']} kA")
        L.append(f"- Tablero: {t['tablero_sugerido']}")
        if t.get("familia"):
            L.append(f"- Barras mínimas: {t['barras_minimas_A'] or '[COMPLETAR]'} A · Principal: {t['principal']['descripcion']}"
                     + (f" ({t['principal']['catalogo']})" if t["principal"].get("catalogo") else ""))
            if t["espacios_minimos"]:
                L.append(f"- Espacios: {t['polos_usados']} polos usados; mínimo {t['espacios_minimos']} con reserva")
            L.append(f"- SCCR resultante: {t['sccr_resultante_kA']} kA · Envolvente: {t['envolvente']}\n")
            L.append("| Pos. | Circuito | Descripción | Polos | Fases | A | Interruptor | kA | Catálogo |")
            L.append("|---|---|---|---|---|---|---|---|---|")
            for i in t["interruptores"]:
                pos = "-".join(str(p) for p in i["posiciones"]) or "—"
                fases = "-".join(i["fases"]) or "—"
                cat = i["catalogo"] + (f" ({i['nota']})" if i["nota"] else "")
                L.append(f"| {pos} | {i['circuito']} | {i['descripcion']} | {i['polos']} | {fases} | "
                         f"{i['amperes']} | {i['tipo']} | {i['kA']} | {cat} |")
            L.append("")
        for a in t["avisos"] + [f"Descartado — {m}" for m in t.get("motivos_descarte", [])]:
            L.append(f"- {a}")
        L.append("")
    return "\n".join(L) + "\n"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Sugerencia de tableros e interruptores Square D")
    p.add_argument("--unifilar", required=True)
    p.add_argument("--cortocircuito", required=True, help="Salida de `ec.py cortocircuito`")
    p.add_argument("--resultados", help="Salida de `ec.py circuito` (circuitos y cedula)")
    p.add_argument("--reserva-pct", type=float, default=25.0)
    p.add_argument("--salida")
    p.add_argument("--reporte", help="Resumen en Markdown")
    a = p.parse_args()
    try:
        r = sugerir(cargar(a.unifilar), cargar(a.cortocircuito),
                    cargar(a.resultados) if a.resultados else None, a.reserva_pct)
    except DatoFaltante as exc:
        print(json.dumps({"error": "DATO_FALTANTE", "mensaje": str(exc),
                          "accion": "PREGUNTAR AL USUARIO. No estimar el valor."}, indent=2, ensure_ascii=False))
        sys.exit(2)
    if a.salida:
        with open(a.salida, "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=2, ensure_ascii=False)
    if a.reporte:
        with open(a.reporte, "w", encoding="utf-8") as fh:
            fh.write(reporte(r))
    print(json.dumps(r, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
