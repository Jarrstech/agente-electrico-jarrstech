#!/usr/bin/env python3
"""
ec.py - Motor de calculo electrico para el agente JARRSTECH.

Regla de oro: este script NO adivina. Si un dato no esta en datos/*.json,
lanza una excepcion con un mensaje que le dice al agente que pregunte al usuario.

Uso:
  python3 scripts/ec.py conductor --carga-va 45000 --tension 480 --fases 3 --continua
  python3 scripts/ec.py caida --calibre 2/0 --corriente 150 --longitud-m 85 --tension 480 --fases 3
  python3 scripts/ec.py proteccion --corriente 150 --continua
  python3 scripts/ec.py egc --ocpd 200 --material cobre
  python3 scripts/ec.py gec --fase 4/0 --material cobre
  python3 scripts/ec.py balanceo --archivo ejemplos/proyecto-demo/cargas.csv --unifilar ejemplos/proyecto-demo/unifilar.json
  python3 scripts/ec.py circuito --archivo ejemplos/proyecto-demo/cargas.csv \
      --unifilar ejemplos/proyecto-demo/unifilar.json --salida resultados.json
  python3 scripts/ec.py cortocircuito --json ejemplos/proyecto-demo/unifilar.json --salida cortocircuito.json
  python3 scripts/ec.py cortocircuito --kva 300 --z-pct 5.75 --tension 480

Fases de una carga (columna `fases` del CSV y argumento --fases):
  1 = monofasica fase-neutro, 1 polo (p. ej. 277 V en 480Y/277, 120 V en 208Y/120)
  2 = bifasica fase-fase, 2 polos (p. ej. 480 V en 480Y/277, 208 V en 208Y/120)
  3 = trifasica, 3 polos
"""

import argparse
import csv
import json
import math
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "datos")


class DatoFaltante(Exception):
    """El dato no existe en los archivos de referencia. El agente debe preguntar, no inventar."""


def _cargar(nombre):
    ruta = os.path.join(DATOS, nombre)
    if not os.path.exists(ruta):
        raise DatoFaltante(f"Falta el archivo de datos {ruta}.")
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


AMP = _cargar("ampacidad_310_16.json")
FAC = _cargar("factores_ajuste.json")
DIS = _cargar("dispositivos_240_6.json")
TIE = _cargar("tierras_250_66_250_122.json")
PRO = _cargar("propiedades_conductores.json")

ORDEN = PRO["orden_calibres"]
CONEXION = {1: "fase-neutro", 2: "fase-fase", 3: "trifasica"}


# ---------------------------------------------------------------- utilidades

def normaliza_calibre(c):
    c = str(c).strip().upper().replace("AWG", "").replace("KCMIL", "").replace("MCM", "").strip()
    c = {"0000": "4/0", "000": "3/0", "00": "2/0", "0": "1/0"}.get(c, c)
    if c not in ORDEN:
        raise DatoFaltante(
            f"Calibre '{c}' no esta en la tabla de referencia. "
            f"Calibres disponibles: {', '.join(ORDEN)}. "
            "Si el proyecto realmente requiere este calibre, pedir el dato de la norma vigente."
        )
    return c


def fases_de(valor, origen=""):
    """1 = fase-neutro, 2 = fase-fase (bifasica), 3 = trifasica."""
    try:
        f = int(float(str(valor).strip()))
    except ValueError:
        f = None
    if f not in CONEXION:
        raise DatoFaltante(
            f"{origen}fases='{valor}' no es valido. Usar 1 (fase-neutro), 2 (fase-fase, "
            "bifasica) o 3 (trifasica)."
        )
    return f


def _num(fila, clave, defecto=None, requerido=False):
    """Lee un numero de una fila del CSV. Una celda vacia vale lo mismo que la columna ausente."""
    v = fila.get(clave)
    if v is None or str(v).strip() == "":
        if requerido:
            raise DatoFaltante(f"Circuito {fila.get('id') or '?'}: falta '{clave}'. Pedirlo; no estimarlo.")
        return defecto
    try:
        return float(v)
    except ValueError:
        raise DatoFaltante(f"Circuito {fila.get('id') or '?'}: '{clave}'='{v}' no es un numero.")


def corriente_de_carga(va, tension, fases):
    if fases == 3:
        return va / (math.sqrt(3) * tension)
    if fases in (1, 2):
        return va / tension
    raise ValueError("fases debe ser 1, 2 o 3")


def factor_temperatura(ambiente_c, temp_aislamiento):
    col = f"f{temp_aislamiento}"
    for fila in FAC["correccion_temperatura_base_30C"]:
        if fila["amb_min"] <= ambiente_c <= fila["amb_max"]:
            f = fila.get(col)
            if f is None:
                raise DatoFaltante(
                    f"Un aislamiento de {temp_aislamiento} C no es utilizable a {ambiente_c} C ambiente. "
                    "Subir la clase de aislamiento o reducir la temperatura ambiente."
                )
            return f
    raise DatoFaltante(f"Temperatura ambiente {ambiente_c} C fuera del rango de la tabla.")


def factor_agrupamiento(n_conductores):
    for fila in FAC["ajuste_numero_conductores"]:
        if fila["min"] <= n_conductores <= fila["max"]:
            return fila["factor"]
    raise DatoFaltante("Numero de conductores fuera de rango.")


def ampacidad_tabla(calibre, material, temp):
    tabla = AMP.get(material)
    if tabla is None:
        raise DatoFaltante("material debe ser 'cobre' o 'aluminio'")
    fila = tabla.get(calibre)
    if fila is None:
        raise DatoFaltante(f"Calibre {calibre} no disponible en {material}.")
    return fila[str(temp)]


def limite_240_4_D(calibre, material):
    clave = "limite_240_4_D_cobre" if material == "cobre" else "limite_240_4_D_aluminio"
    return AMP[clave].get(calibre)


# ------------------------------------------------------- seleccion conductor

def seleccionar_conductor(corriente_diseno, material="cobre", temp_aislamiento=90,
                          temp_terminal=75, ambiente_c=30, n_conductores=3,
                          conductores_por_fase=1):
    """
    Devuelve el calibre mas pequeño que cumple simultaneamente:
      1) ampacidad de tabla al aislamiento, corregida por temperatura y agrupamiento >= I diseño
      2) ampacidad de tabla a la temperatura del TERMINAL (110.14(C)) >= I diseño  [sin correcciones]
    """
    ft = factor_temperatura(ambiente_c, temp_aislamiento)
    fa = factor_agrupamiento(n_conductores)
    objetivo = corriente_diseno / conductores_por_fase

    for calibre in ORDEN:
        try:
            base = ampacidad_tabla(calibre, material, temp_aislamiento)
            terminal = ampacidad_tabla(calibre, material, temp_terminal)
        except (DatoFaltante, KeyError):
            continue
        corregida = base * ft * fa
        lim = limite_240_4_D(calibre, material)
        if lim is not None:
            terminal = min(terminal, lim)
        if corregida >= objetivo and terminal >= objetivo:
            return {
                "calibre": calibre,
                "material": material,
                "conductores_por_fase": conductores_por_fase,
                "ampacidad_tabla_A": base,
                "temp_aislamiento_C": temp_aislamiento,
                "factor_temperatura": ft,
                "factor_agrupamiento": fa,
                "ampacidad_corregida_A": round(corregida, 1),
                "ampacidad_limitada_terminal_A": terminal,
                "temp_terminal_C": temp_terminal,
                "ampacidad_utilizable_A": round(min(corregida, terminal) * conductores_por_fase, 1),
                "corriente_diseno_A": round(corriente_diseno, 1),
                "regla_gobernante": "110.14(C) terminal" if terminal <= corregida else "310.15 corregida",
            }
    raise DatoFaltante(
        f"Ningun calibre de la tabla cubre {objetivo:.1f} A por conductor. "
        "Considerar conductores en paralelo (310.10(G), minimo 1/0) o subir la tension del sistema."
    )


# ------------------------------------------------------------ caida tension

def caida_de_tension(calibre, corriente, longitud_m, tension, fases=3,
                     material="cobre", conductores_por_fase=1, fp=1.0, limite_pct=None):
    if limite_pct is None:
        limite_pct = PRO["limites_caida_tension"]["circuito_derivado_recomendado_pct"]
    calibre = normaliza_calibre(calibre)
    r_km = PRO["resistencia_ohm_por_km_75C"][material].get(calibre)
    if r_km is None:
        raise DatoFaltante(f"No hay resistencia para {calibre} en {material}.")
    r = (r_km / 1000.0) * longitud_m / conductores_por_fase
    k = math.sqrt(3) if fases == 3 else 2.0
    dv = k * corriente * r * fp
    return {
        "calibre": calibre,
        "material": material,
        "longitud_m": longitud_m,
        "corriente_A": corriente,
        "resistencia_ohm": round(r, 5),
        "caida_V": round(dv, 2),
        "caida_pct": round(dv / tension * 100, 2),
        "limite_recomendado_pct": limite_pct,
    }


def calibre_por_caida(corriente, longitud_m, tension, fases=3, material="cobre",
                      limite_pct=3.0, calibre_minimo="14", conductores_por_fase=1):
    inicio = ORDEN.index(normaliza_calibre(calibre_minimo))
    for calibre in ORDEN[inicio:]:
        r = caida_de_tension(calibre, corriente, longitud_m, tension, fases,
                             material, conductores_por_fase, limite_pct=limite_pct)
        if r["caida_pct"] <= limite_pct:
            return r
    raise DatoFaltante(
        f"Ningun calibre de la tabla logra <= {limite_pct}% en {longitud_m} m. "
        "Usar conductores en paralelo, subir tension o reubicar el tablero."
    )


# --------------------------------------------------------------- proteccion

def proteccion(corriente_diseno, continua=False, siguiente_superior=True):
    i = corriente_diseno * (1.25 if continua else 1.0)
    estandar = DIS["capacidades_estandar_A"]
    escogido = None
    for cap in estandar:
        if cap >= i:
            escogido = cap
            break
    if escogido is None:
        raise DatoFaltante(f"{i:.1f} A excede la mayor capacidad estandar de la tabla.")
    return {
        "corriente_carga_A": round(corriente_diseno, 1),
        "carga_continua": continua,
        "corriente_minima_dispositivo_A": round(i, 1),
        "capacidad_nominal_A": escogido,
        "nota_240_4_B": ("Si esta capacidad excede la ampacidad del conductor, verificar "
                         "que aplique la regla del siguiente tamano superior (240.4(B)) "
                         "y que no sea un circuito derivado multisalida."),
    }


# --------------------------------------------------------------- tierras

def egc(ocpd_A, material="cobre"):
    clave = "egc_cu" if material == "cobre" else "egc_al"
    for fila in TIE["tabla_250_122_EGC"]:
        if ocpd_A <= fila["ocpd_A"]:
            return {
                "ocpd_A": ocpd_A,
                "fila_tabla_A": fila["ocpd_A"],
                "egc_calibre": fila[clave],
                "material": material,
                "nota_250_122_B": ("Si los conductores de fase se aumentaron de calibre (p.ej. por "
                                   "caida de tension), el EGC debe aumentarse proporcionalmente al "
                                   "area de la seccion transversal."),
            }
    raise DatoFaltante(f"OCPD de {ocpd_A} A fuera del rango de la Tabla 250.122.")


def gec(calibre_fase, material="cobre"):
    calibre_fase = normaliza_calibre(calibre_fase)
    idx = ORDEN.index(calibre_fase)
    clave_fase = "fase_cu_hasta" if material == "cobre" else "fase_al_hasta"
    clave_gec = "gec_cu" if material == "cobre" else "gec_al"
    for fila in TIE["tabla_250_66_GEC"]:
        tope = fila[clave_fase]
        if tope == "MAYOR":
            return {"fase": calibre_fase, "gec_calibre": fila[clave_gec], "material": material}
        if idx <= ORDEN.index(tope):
            return {
                "fase": calibre_fase,
                "fila_tabla": tope,
                "gec_calibre": fila[clave_gec],
                "material": material,
                "nota": "Aplica a conductores del electrodo de puesta a tierra. Puente de union "
                        "principal y conductores del lado de suministro: usar 250.102(C).",
            }
    raise DatoFaltante("No se ubico la fila en Tabla 250.66.")


# ------------------------------------------------------------- balanceo
#
# Arreglo de barras de los tableros Square D NQ y NF (y de todo tablero de
# alumbrado y distribucion): circuitos nones a la izquierda y pares a la
# derecha; cada renglon (1-2, 3-4, 5-6, ...) toma una fase en secuencia A, B, C
# (NEC 408.3(E)). En un tablero monofasico de 3 hilos la secuencia es A, B.
# Un interruptor de 2 polos ocupa dos renglones seguidos del mismo lado
# (fases A-B, B-C o C-A) y recibe la mitad de la carga en cada fase; uno de
# 3 polos ocupa tres renglones y recibe un tercio en cada fase.

ARREGLO = ("Barras Square D: nones a la izquierda, pares a la derecha; renglones 1-2 fase A, "
           "3-4 fase B, 5-6 fase C y se repite (NEC 408.3(E)). 1 polo: toda la carga en su fase; "
           "2 polos: mitad en cada fase; 3 polos: un tercio en cada fase.")


def balancear_tablero(cargas, n_fases=3):
    """cargas: dicts con id, nombre, va, polos (1-3) y fase pedida opcional ('A', 'AB', ...)."""
    fases = ("A", "B", "C") if n_fases == 3 else ("A", "B")
    carga = {f: 0.0 for f in fases}
    ocupado = {"izq": set(), "der": set()}
    cedula, avisos = [], []

    def fase_de(renglon):
        return fases[(renglon - 1) % len(fases)]

    def grupo_desde(f0, polos):
        i = fases.index(f0)
        return [fases[(i + k) % len(fases)] for k in range(polos)]

    def buscar(polos, primera):
        renglon = 1
        while True:
            for lado in ("izq", "der"):
                if primera and fase_de(renglon) != primera:
                    continue
                if all(renglon + k not in ocupado[lado] for k in range(polos)):
                    return lado, renglon
            renglon += 1

    # primero las cargas con fase pedida (quedan fijas), luego las demas de mayor a menor
    for c in sorted(cargas, key=lambda x: (not x.get("fase"), -x["polos"], -x["va"])):
        polos, va = c["polos"], c["va"]
        if polos > len(fases):
            avisos.append(f"{c['id']}: carga de {polos} polos en un tablero de {len(fases)} fases.")
            continue
        primera = None
        if polos < len(fases):
            pedida = set(c.get("fase") or "")
            validas = {f0: grupo_desde(f0, polos) for f0 in fases}
            elegida = [f0 for f0, g in validas.items() if set(g) == pedida]
            if pedida and elegida:
                primera = elegida[0]
            else:
                if pedida:
                    avisos.append(f"{c['id']}: fase '{c.get('fase')}' no valida para {polos} polo(s); "
                                  "se asigna por balanceo.")
                opciones = []
                for f0, g in validas.items():
                    prueba = dict(carga)
                    for f in g:
                        prueba[f] += va / polos
                    opciones.append((max(prueba.values()) - min(prueba.values()),
                                     sum(carga[f] for f in g), fases.index(f0), f0))
                primera = min(opciones)[3]
        lado, renglon = buscar(polos, primera)
        grupo = [fase_de(renglon + k) for k in range(polos)]
        for k in range(polos):
            ocupado[lado].add(renglon + k)
        for f in grupo:
            carga[f] += va / polos
        posiciones = [2 * (renglon + k) - 1 if lado == "izq" else 2 * (renglon + k) for k in range(polos)]
        cedula.append({
            "circuito": c["id"],
            "nombre": c.get("nombre", ""),
            "polos": polos,
            "conexion": CONEXION[polos],
            "posiciones": posiciones,
            "fases": grupo,
            "va": round(va, 1),
            "va_por_fase": {f: round(va / polos, 1) for f in grupo},
        })

    total = sum(carga.values())
    prom = total / len(fases) if total else 0
    desbal = (max(carga.values()) - min(carga.values())) / prom * 100 if prom else 0
    return {
        "fases_tablero": len(fases),
        "va_por_fase": {k: round(v, 1) for k, v in carga.items()},
        "va_total": round(total, 1),
        "desbalance_pct": round(desbal, 2),
        "espacios_usados": max((max(e["posiciones"]) for e in cedula), default=0),
        "cedula": sorted(cedula, key=lambda e: min(e["posiciones"])),
        "avisos": avisos,
    }


def balanceo(cargas, tableros=None):
    """Balanceo por tablero. cargas: filas del CSV; tableros: nodos del unifilar por id."""
    grupos = {}
    for c in cargas:
        fila = {
            "id": c.get("id") or "?",
            "nombre": c.get("nombre", ""),
            "va": _num(c, "va", requerido=True),
            "polos": fases_de(c.get("fases", 3), f"Circuito {c.get('id') or '?'}: "),
            "fase": "".join(ch for ch in str(c.get("fase") or "").upper() if ch in "ABC"),
        }
        grupos.setdefault((c.get("tablero") or "").strip(), []).append(fila)
    resultado = []
    for tid in sorted(grupos):
        nodo = (tableros or {}).get(tid, {})
        r = balancear_tablero(grupos[tid], int(nodo.get("fases", 3)) if nodo else 3)
        resultado.append({"tablero": tid or "(sin tablero)", **r})
    return {
        "arreglo": ARREGLO,
        "criterio": "Objetivo de proyecto: desbalance <= 5% por tablero. Por encima de 10%, redistribuir.",
        "tableros": resultado,
    }


# ------------------------------------------------------- circuito completo

def verificar_tension(res, nodo):
    """Compara la tension del circuito con la del tablero segun su conexion."""
    v_ll = float(nodo.get("tension_V") or 0)
    if not v_ll:
        return None
    tres_fases = int(nodo.get("fases", 3)) == 3
    hilos = int(nodo.get("hilos", 4 if tres_fases else 3))
    v_fn = v_ll / math.sqrt(3) if tres_fases else v_ll / 2
    f, v, tid = res["fases"], res["tension_V"], nodo["id"]
    sistema = f"{v_ll:g} V entre fases, {v_fn:.0f} V fase-neutro"
    if f == 3 and not tres_fases:
        return f"Carga trifasica en el tablero monofasico {tid}."
    if f == 1 and hilos < (4 if tres_fases else 3):
        return f"Carga fase-neutro en el tablero {tid}, que no tiene neutro."
    esperada = v_fn if f == 1 else v_ll
    if abs(v - esperada) / esperada > 0.05:
        return (f"{v:g} V no corresponde a una carga {CONEXION[f]} del tablero {tid} ({sistema}). "
                "Revisar la tension o la columna fases.")
    return None


def dimensionar_circuito(carga, cfg, tableros=None):
    cid = carga.get("id") or ""
    va = _num(carga, "va", requerido=True)
    tension = _num(carga, "tension", cfg.get("tension", 480))
    fases = fases_de(carga.get("fases", 3), f"Circuito {cid}: ")
    continua = str(carga.get("continua", "")).strip().lower() in ("1", "si", "sí", "true", "x", "yes")
    longitud = _num(carga, "longitud_m", 0)
    material = (carga.get("material") or "").strip() or cfg.get("material", "cobre")
    ambiente = _num(carga, "ambiente_c", cfg.get("ambiente_c", 30))
    n_cond = int(_num(carga, "n_conductores", 3))
    temp_ais = int(_num(carga, "temp_aislamiento", cfg.get("temp_aislamiento", 90)))
    temp_term = int(_num(carga, "temp_terminal", cfg.get("temp_terminal", 75)))
    limite_dv = _num(carga, "limite_dv_pct", cfg.get("limite_dv_pct", 3.0))
    tablero = (carga.get("tablero") or "").strip()

    i_carga = corriente_de_carga(va, tension, fases)
    i_diseno = i_carga * (1.25 if continua else 1.0)

    cond = seleccionar_conductor(i_diseno, material, temp_ais, temp_term, ambiente, n_cond)
    prot = proteccion(i_carga, continua)

    resultado = {
        "id": cid,
        "nombre": carga.get("nombre", ""),
        "tablero": tablero,
        "va": va,
        "tension_V": tension,
        "fases": fases,
        "polos": fases,
        "conexion": CONEXION[fases],
        "continua": continua,
        "corriente_carga_A": round(i_carga, 1),
        "corriente_diseno_A": round(i_diseno, 1),
        "conductor": cond,
        "proteccion": prot,
        "egc": egc(prot["capacidad_nominal_A"], material),
    }

    if tableros is not None and tablero:
        if tablero not in tableros:
            resultado["alerta_tension"] = f"El tablero {tablero} no esta en el unifilar."
        else:
            aviso = verificar_tension(resultado, tableros[tablero])
            if aviso:
                resultado["alerta_tension"] = aviso

    if longitud > 0:
        dv = caida_de_tension(cond["calibre"], i_carga, longitud, tension, fases, material,
                              limite_pct=limite_dv)
        resultado["caida_tension"] = dv
        if dv["caida_pct"] > limite_dv:
            mejor = calibre_por_caida(i_carga, longitud, tension, fases, material,
                                      limite_dv, cond["calibre"])
            resultado["caida_tension"]["excede_limite"] = True
            resultado["calibre_por_caida"] = mejor
            resultado["calibre_final"] = mejor["calibre"]
            resultado["alerta"] = (
                f"Caida {dv['caida_pct']}% > {limite_dv}%. Se aumenta a {mejor['calibre']} "
                f"({mejor['caida_pct']}%). Aplicar 250.122(B): aumentar el EGC proporcionalmente."
            )
        else:
            resultado["calibre_final"] = cond["calibre"]
    else:
        resultado["calibre_final"] = cond["calibre"]
        resultado["alerta_longitud"] = "Sin longitud declarada: NO se verifico caida de tension."

    return resultado


def leer_cargas_csv(ruta):
    with open(ruta, newline="", encoding="utf-8-sig") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def tableros_de_unifilar(ruta):
    if not ruta:
        return None
    with open(ruta, encoding="utf-8") as fh:
        doc = json.load(fh)
    return {n["id"]: n for n in doc.get("nodos", []) if n.get("tipo") in ("tablero", "barra")}


# ------------------------------------------------------------ cortocircuito
#
# Metodo del bus infinito: la red del suministrador se modela con impedancia
# cero en el primario de cada transformador. En el secundario,
# Icc = kVA x 1000 / (raiz(3) x V x Z%/100). Aguas abajo se suma la impedancia
# de los conductores (resistencia a 25 C) hasta cada nodo del unifilar.

TIPOS_FUENTE = ("bess", "fotovoltaico", "generador", "ups")


def icc_bus_infinito(kva, z_pct, tension):
    """Icc trifasica simetrica en bornes del secundario con fuente de potencia infinita."""
    if not kva or not z_pct or not tension:
        raise DatoFaltante("Se requieren kVA, Z% de placa y tension del secundario. Pedirlos; no suponerlos.")
    i_n = kva * 1000.0 / (math.sqrt(3) * tension)
    return {
        "metodo": "Bus infinito",
        "kva": kva,
        "z_pct": z_pct,
        "tension_V": tension,
        "corriente_nominal_A": round(i_n, 1),
        "icc_kA": round(i_n * 100.0 / z_pct / 1000.0, 2),
        "formula": "Icc = kVA x 1000 / (raiz(3) x V x Z%/100)",
    }


def _capacidad_estandar(icc_ka):
    for cap in DIS["sccr_comunes_kA_simetricos"]:
        if cap >= icc_ka:
            return cap
    return None


def cortocircuito(doc, factor_motores=None):
    CC = _cargar("cortocircuito.json")
    k_t = CC["constante_temperatura_resistencia_C"]
    t_cc = CC["temperatura_conductor_C"]
    tol = CC["tolerancia_tension_pct"] / 100.0
    if factor_motores is None:
        factor_motores = CC["aporte_motores_factor"]

    nodos = doc.get("nodos", [])
    idx = {n["id"]: n for n in nodos}
    hijos = {}
    for n in nodos:
        padre = n.get("padre") if n.get("padre") in idx else None
        hijos.setdefault(padre, []).append(n)
    filas, avisos = {}, []
    if doc.get("icc_disponible_kA"):
        avisos.append("icc_disponible_kA del diagrama no se usa: el metodo de bus infinito supone "
                      "impedancia cero del suministrador.")

    def z_conductor(n):
        calibre, lon = n.get("calibre"), float(n.get("longitud_m") or 0)
        if not calibre or lon <= 0:
            return 0j
        mat = n.get("material", "cobre")
        cal = normaliza_calibre(calibre)
        r75 = PRO["resistencia_ohm_por_km_75C"].get(mat, {}).get(cal)
        if r75 is None:
            raise DatoFaltante(f"{n['id']}: no hay resistencia para {cal} {mat}.")
        r = r75 * (k_t[mat] + t_cc) / (k_t[mat] + 75.0)
        x = float(n.get("reactancia_ohm_km") or 0)
        cpf = int(n.get("conductores_por_fase") or 1)
        return complex(r, x) * lon / 1000.0 / cpf

    def z_transformador(n, v2):
        kva, zp = n.get("kva"), n.get("z_pct")
        if not kva or not zp:
            raise DatoFaltante(f"{n['id']}: faltan 'kva' y 'z_pct' de placa. Pedirlos; no suponerlos.")
        zt = zp / 100.0 * v2 ** 2 / (kva * 1000.0)
        xr = n.get("x_r")
        if xr:
            r = zt / math.sqrt(1 + xr ** 2)
            return complex(r, r * xr)
        return complex(0, zt)

    def visitar(n, z_up, v_up, sistema):
        tipo = n.get("tipo")
        zc = z_conductor(n)
        if tipo == "transformador":
            v2 = float(n.get("tension_V") or 0)
            if not v2:
                raise DatoFaltante(f"{n['id']}: falta la tension del secundario (tension_V).")
            if z_up is None:
                z = z_transformador(n, v2)
            else:
                if not v_up:
                    raise DatoFaltante(f"{n['id']}: el nodo padre no declara la tension del primario.")
                z = (z_up + zc) * (v2 / v_up) ** 2 + z_transformador(n, v2)
            v, sistema = v2, n["id"]
        elif z_up is None:
            v = float(n.get("tension_V") or 0)
            if n.get("kva") and n.get("z_pct"):
                z = z_transformador(n, v) + zc
            elif n.get("icc_kA"):
                z = complex(0, v / (math.sqrt(3) * float(n["icc_kA"]) * 1000.0)) + zc
            elif v > 1000:
                z = zc
            else:
                raise DatoFaltante(
                    f"{n['id']}: acometida en baja tension sin transformador. Con bus infinito la "
                    "corriente seria ilimitada: dar kva y z_pct del transformador del suministrador "
                    "o icc_kA en el punto de entrega.")
            sistema = n["id"]
        else:
            z, v = z_up + zc, v_up

        tn = n.get("tension_V")
        if tn and v and tipo != "transformador" and z_up is not None:
            f = int(n.get("fases", 3))
            esperada = v / math.sqrt(3) if f == 1 else v
            if abs(float(tn) - esperada) / esperada > tol:
                detalle = f"{v:g} V entre fases" + (f", {v / math.sqrt(3):.0f} V fase-neutro" if f == 1 else "")
                avisos.append(f"{n['id']}: tension declarada {tn} V distinta de la del sistema ({detalle}).")

        icc = v / (math.sqrt(3) * abs(z)) / 1000.0 if v and abs(z) > 0 else None
        filas[n["id"]] = {
            "id": n["id"],
            "tipo": tipo,
            "sistema": sistema,
            "tension_sistema_V": v,
            "r_ohm": round(z.real, 6),
            "x_ohm": round(z.imag, 6),
            "z_ohm": round(abs(z), 6),
            "icc_simetrica_kA": round(icc, 2) if icc else None,
        }
        for h in hijos.get(n["id"], []):
            visitar(h, z, v, sistema)

    for raiz in hijos.get(None, []):
        visitar(raiz, None, None, None)

    aporte = {}
    for n in nodos:
        f = filas.get(n["id"])
        if not f:
            continue
        if n.get("tipo") == "motor":
            va = n.get("carga_va")
            if not va:
                avisos.append(f"{n['id']}: motor sin carga_va; no se incluye su aporte.")
                continue
            nf, v = int(n.get("fases", 3)), f["tension_sistema_V"]
            i_n = float(va) / (math.sqrt(3) * v) if nf == 3 else float(va) / (v / math.sqrt(3) if nf == 1 else v)
            aporte[f["sistema"]] = aporte.get(f["sistema"], 0.0) + factor_motores * i_n / 1000.0
        elif n.get("tipo") in TIPOS_FUENTE:
            a = n.get("aporte_icc_kA")
            if a is None:
                avisos.append(f"{n['id']} ({n['tipo']}): falta 'aporte_icc_kA', la corriente de falla que "
                              "aporta segun el fabricante. La Icc de su sistema no la incluye.")
            else:
                aporte[f["sistema"]] = aporte.get(f["sistema"], 0.0) + float(a)

    for f in filas.values():
        n = idx[f["id"]]
        a = aporte.get(f["sistema"], 0.0)
        f["aporte_kA"] = round(a, 2)
        f["icc_total_kA"] = round(f["icc_simetrica_kA"] + a, 2) if f["icc_simetrica_kA"] else None
        f["capacidad_minima_estandar_kA"] = _capacidad_estandar(f["icc_total_kA"]) if f["icc_total_kA"] else None
        cap = n.get("sccr_kA")
        if f["icc_total_kA"] is None:
            f["verificacion"] = "BUS INFINITO (sin impedancia aguas arriba)"
        elif cap:
            f["sccr_kA"] = cap
            if cap < f["icc_total_kA"]:
                f["verificacion"] = "NO CUMPLE"
            elif f["icc_total_kA"] > 0.9 * cap:
                f["verificacion"] = "AL LIMITE"
            else:
                f["verificacion"] = "CUMPLE"
        elif n.get("tipo") in ("tablero", "barra", "interruptor_principal"):
            f["verificacion"] = "SIN SCCR DECLARADO"

    return {
        "metodo": "Bus infinito: red del suministrador con impedancia cero en el primario de cada transformador",
        "formula": "Icc secundario = kVA x 1000 / (raiz(3) x V x Z%/100); aguas abajo Icc = V / (raiz(3) x |Z acumulada|)",
        "supuestos": [
            "La red del suministrador tiene potencia de cortocircuito infinita (impedancia cero).",
            f"Resistencia de conductores a {t_cc} C y reactancia cero, salvo 'reactancia_ohm_km' "
            "declarada en el nodo (resultado conservador).",
            "Transformador sin 'x_r' declarado: impedancia puramente reactiva (resultado conservador).",
            f"Aporte de motores: {factor_motores} x corriente nominal, sumado a todo su sistema "
            "(Eaton Bussmann, metodo punto a punto).",
            "BESS, fotovoltaico, generador y UPS aportan lo que declare 'aporte_icc_kA' (dato del fabricante).",
            "Falla trifasica franca y simetrica; la falla fase-fase es 0.866 veces la trifasica.",
        ],
        "nodos": [filas[n["id"]] for n in nodos if n["id"] in filas],
        "avisos": avisos,
    }


# ------------------------------------------------------------------- CLI

def _escribir(ruta, out):
    with open(ruta, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Motor de calculo electrico NEC / NOM-001-SEDE")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("conductor")
    c.add_argument("--carga-va", type=float)
    c.add_argument("--corriente", type=float)
    c.add_argument("--tension", type=float, default=480)
    c.add_argument("--fases", type=int, default=3, choices=(1, 2, 3),
                   help="1 fase-neutro, 2 fase-fase, 3 trifasica")
    c.add_argument("--material", default="cobre")
    c.add_argument("--ambiente-c", type=float, default=30)
    c.add_argument("--n-conductores", type=int, default=3)
    c.add_argument("--temp-aislamiento", type=int, default=90)
    c.add_argument("--temp-terminal", type=int, default=75)
    c.add_argument("--continua", action="store_true")

    d = sub.add_parser("caida")
    d.add_argument("--calibre", required=True)
    d.add_argument("--corriente", type=float, required=True)
    d.add_argument("--longitud-m", type=float, required=True)
    d.add_argument("--tension", type=float, required=True)
    d.add_argument("--fases", type=int, default=3, choices=(1, 2, 3))
    d.add_argument("--material", default="cobre")
    d.add_argument("--paralelo", type=int, default=1)

    pr = sub.add_parser("proteccion")
    pr.add_argument("--corriente", type=float, required=True)
    pr.add_argument("--continua", action="store_true")

    e = sub.add_parser("egc")
    e.add_argument("--ocpd", type=float, required=True)
    e.add_argument("--material", default="cobre")

    g = sub.add_parser("gec")
    g.add_argument("--fase", required=True)
    g.add_argument("--material", default="cobre")

    b = sub.add_parser("balanceo")
    b.add_argument("--archivo", required=True)
    b.add_argument("--unifilar", help="Unifilar JSON: tension y fases de cada tablero")

    ci = sub.add_parser("circuito")
    ci.add_argument("--archivo", required=True)
    ci.add_argument("--unifilar", help="Unifilar JSON: verifica la tension de cada circuito contra su tablero")
    ci.add_argument("--salida")
    ci.add_argument("--tension", type=float, default=480)
    ci.add_argument("--material", default="cobre")
    ci.add_argument("--ambiente-c", type=float, default=30)
    ci.add_argument("--temp-terminal", type=int, default=75,
                    help="Temperatura de terminales del equipo (C) para filas sin temp_terminal")
    ci.add_argument("--temp-aislamiento", type=int, default=90,
                    help="Clase de aislamiento (C) para filas sin temp_aislamiento")
    ci.add_argument("--limite-dv", type=float, default=3.0,
                    help="Limite de caida de tension del derivado (%%) para filas sin limite_dv_pct")

    cc = sub.add_parser("cortocircuito")
    cc.add_argument("--json", help="Unifilar JSON: Icc en cada nodo")
    cc.add_argument("--kva", type=float)
    cc.add_argument("--z-pct", type=float)
    cc.add_argument("--tension", type=float)
    cc.add_argument("--aporte-motores", type=float,
                    help="Factor x corriente nominal de motores (0 = sin aporte). Por omision, datos/cortocircuito.json")
    cc.add_argument("--salida")

    a = p.parse_args()

    try:
        if a.cmd == "conductor":
            if a.corriente is not None:
                i = a.corriente
            elif a.carga_va is not None:
                i = corriente_de_carga(a.carga_va, a.tension, a.fases)
            else:
                raise SystemExit("Se requiere --carga-va o --corriente")
            i_d = i * (1.25 if a.continua else 1.0)
            out = seleccionar_conductor(i_d, a.material, a.temp_aislamiento,
                                        a.temp_terminal, a.ambiente_c, a.n_conductores)
            out["corriente_carga_A"] = round(i, 1)
            out["carga_continua"] = a.continua
            out["conexion"] = CONEXION[a.fases]
        elif a.cmd == "caida":
            out = caida_de_tension(a.calibre, a.corriente, a.longitud_m, a.tension,
                                   a.fases, a.material, a.paralelo)
        elif a.cmd == "proteccion":
            out = proteccion(a.corriente, a.continua)
        elif a.cmd == "egc":
            out = egc(a.ocpd, a.material)
        elif a.cmd == "gec":
            out = gec(a.fase, a.material)
        elif a.cmd == "balanceo":
            out = balanceo(leer_cargas_csv(a.archivo), tableros_de_unifilar(a.unifilar))
        elif a.cmd == "circuito":
            cfg = {"tension": a.tension, "material": a.material, "ambiente_c": a.ambiente_c,
                   "temp_terminal": a.temp_terminal, "temp_aislamiento": a.temp_aislamiento,
                   "limite_dv_pct": a.limite_dv}
            cargas = leer_cargas_csv(a.archivo)
            tableros = tableros_de_unifilar(a.unifilar)
            res = [dimensionar_circuito(c, cfg, tableros) for c in cargas]
            out = {"circuitos": res, "balanceo": balanceo(cargas, tableros)}
            if a.salida:
                _escribir(a.salida, out)
        elif a.cmd == "cortocircuito":
            if a.json:
                with open(a.json, encoding="utf-8") as fh:
                    out = cortocircuito(json.load(fh), a.aporte_motores)
            else:
                out = icc_bus_infinito(a.kva, a.z_pct, a.tension)
            if a.salida:
                _escribir(a.salida, out)
    except DatoFaltante as exc:
        print(json.dumps({"error": "DATO_FALTANTE", "mensaje": str(exc),
                          "accion": "PREGUNTAR AL USUARIO. No estimar el valor."},
                         indent=2, ensure_ascii=False))
        sys.exit(2)

    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
