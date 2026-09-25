#!/usr/bin/env python3
"""
Interfaz local del agente electrico: captura los datos de un proyecto, escribe
los archivos que usan los scripts y corre el flujo completo.

  python scripts/interfaz.py                    # abre http://127.0.0.1:8765
  python scripts/interfaz.py --puerto 8800 --sin-navegador

Cada proyecto vive en proyectos/<id>/ con los mismos archivos que leen los
scripts: proyecto.yaml, jurisdiccion.yaml, cargas.csv, unifilar.json y, si hay
subestacion propia, red-de-tierras.yaml. La interfaz no calcula: escribe esos
archivos, corre los scripts y muestra lo que devuelven. Los comandos quedan en
proyectos/<id>/bitacora.json para reproducirlos a mano o desde Claude.

Solo biblioteca estandar. Escucha unicamente en 127.0.0.1.
"""

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import unicodedata
import webbrowser
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROYECTOS = os.environ.get("AGENTE_PROYECTOS") or os.path.join(RAIZ, "proyectos")
WEB = os.path.join(RAIZ, "interfaz")
DEMO = os.path.join(RAIZ, "ejemplos", "proyecto-demo")
CONFIG = os.path.join(RAIZ, "config")

ENTRADAS = ("proyecto.yaml", "jurisdiccion.yaml", "cargas.csv", "unifilar.json", "red-de-tierras.yaml")
SALIDAS = ("validacion.json", "cortocircuito.json", "unifilar.svg", "resultados.json", "squared.json",
           "squared.md", "red-tierras.json", "red-tierras.md", "memoria-de-calculo.md", "bitacora.json")
ESTATICOS = {"/": ("index.html", "text/html; charset=utf-8"),
             "/index.html": ("index.html", "text/html; charset=utf-8"),
             "/app.js": ("app.js", "text/javascript; charset=utf-8"),
             "/estilos.css": ("estilos.css", "text/css; charset=utf-8")}
TIPO_ARCHIVO = {".md": "text/markdown; charset=utf-8", ".json": "application/json; charset=utf-8",
                ".svg": "image/svg+xml", ".csv": "text/csv; charset=utf-8", ".yaml": "text/plain; charset=utf-8"}

TIPOS_NODO = ["acometida", "medidor", "transformador", "interruptor_principal", "tablero", "barra",
              "carga", "motor", "generador", "ups", "bess", "fotovoltaico", "cargador_ve",
              "transferencia", "capacitor"]
FUENTES = ("bess", "fotovoltaico", "generador", "ups")
CALIBRES = ["14", "12", "10", "8", "6", "4", "3", "2", "1", "1/0", "2/0", "3/0", "4/0",
            "250", "300", "350", "400", "500", "600", "750"]
COLS_CARGAS = ["id", "nombre", "va", "tension", "fases", "fase", "continua", "longitud_m",
               "n_conductores", "material", "ambiente_c", "tablero", "notas"]
ORDEN_NODO = ["id", "tipo", "padre", "descripcion", "tension_V", "fases", "hilos", "conexion", "kva",
              "z_pct", "x_r", "icc_kA", "proteccion_primario_A", "proteccion_secundario_A",
              "interruptor_A", "sccr_kA", "calibre", "conductores_por_fase", "material", "egc",
              "longitud_m", "reactancia_ohm_km", "carga_va", "aporte_icc_kA", "notas"]
NODO_FLOAT = ("tension_V", "sccr_kA", "longitud_m", "carga_va", "kva", "z_pct", "x_r",
              "aporte_icc_kA", "reactancia_ohm_km", "icc_kA")
NODO_INT = ("fases", "hilos", "interruptor_A", "proteccion_primario_A", "proteccion_secundario_A",
            "conductores_por_fase")
NODO_TEXTO = ("id", "tipo", "padre", "descripcion", "calibre", "material", "egc", "conexion")
PASOS = [("validar", "Validación del unifilar"),
         ("cortocircuito", "Cortocircuito por bus infinito"),
         ("validar_sccr", "SCCR contra la Icc de cada nodo"),
         ("render", "Dibujo del unifilar (SVG)"),
         ("circuitos", "Circuitos, protecciones y balanceo"),
         ("squared", "Tableros e interruptores Square D"),
         ("tierras", "Red de tierras (IEEE 80)"),
         ("memoria", "Memoria de cálculo")]
TODO = tuple(p for p, _ in PASOS)
P_UNI = ("validar", "cortocircuito", "validar_sccr", "render", "circuitos", "squared", "memoria")
P_CC = ("cortocircuito", "validar_sccr", "squared")
P_CARG = ("circuitos", "squared", "memoria")
RE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
RE_PROYECTO = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
RE_PENDIENTE = re.compile(r"\[(COMPLETAR|VERIFICAR|FALTA|SUPUESTO)")
CANDADOS = {}
CANDADO_GLOBAL = threading.Lock()


# ------------------------------------------------------------ utilidades

def _texto(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _numero(v):
    """float de un texto; None si esta vacio. ValueError si no es un numero finito."""
    t = _texto(v)
    if t == "":
        return None
    x = float(t)
    if not math.isfinite(x):
        raise ValueError(t)
    return x


def _num_o_error(v):
    """(valor, error): valor float o None; error True si hay texto que no es numero."""
    try:
        return _numero(v), False
    except ValueError:
        return None, True


def _bool(v):
    if isinstance(v, bool):
        return v
    return _texto(v).lower() in ("true", "si", "sí", "yes", "1")


def _lista(v):
    if isinstance(v, list):
        return [_texto(x) for x in v if _texto(x)]
    if isinstance(v, dict):
        return [_texto(k) for k in v if _texto(k)]
    return [x.strip() for x in _texto(v).splitlines() if x.strip()]


def _cal(v):
    """Normaliza un calibre como lo hacen los scripts; '' si esta vacio."""
    t = _texto(v).upper().replace("AWG", "").replace("KCMIL", "").replace("MCM", "").strip()
    return {"0000": "4/0", "000": "3/0", "00": "2/0", "0": "1/0"}.get(t, t)


def _ahora():
    return datetime.now().isoformat(timespec="seconds")


# ------------------------------------------------------------ YAML

def _sin_comentario(linea):
    comilla = None
    for i, ch in enumerate(linea):
        if comilla:
            if ch == comilla:
                comilla = None
        elif ch in "\"'":
            comilla = ch
        elif ch == "#" and (i == 0 or linea[i - 1] in " \t"):
            return linea[:i]
    return linea


def _escalar(v):
    v = v.strip()
    if v in ("", "null", "~", "None"):
        return None
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v == "[]":
        return []
    if v.lower() in ("true", "si", "sí", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    for tipo in (int, float):
        try:
            return tipo(v)
        except ValueError:
            pass
    return v


def leer_yaml(ruta):
    """YAML minimo compatible con los lectores de los scripts: secciones anidadas por
    sangria, escalares y listas con guion."""
    raiz, pila, ultimo = {}, [(-1, None)], None
    pila[0] = (-1, raiz)
    with open(ruta, encoding="utf-8-sig") as fh:
        for linea in fh:
            linea = _sin_comentario(linea.rstrip("\r\n"))
            if not linea.strip():
                continue
            sangria = len(linea) - len(linea.lstrip())
            limpia = linea.strip()
            if limpia.startswith("- ") or limpia == "-":
                if ultimo is not None:
                    padre, clave = ultimo
                    if not isinstance(padre[clave], list):
                        padre[clave] = []
                    padre[clave].append(_escalar(limpia[1:]))
                continue
            if ":" not in limpia:
                continue
            clave, _, valor = limpia.partition(":")
            clave = clave.strip()
            while sangria <= pila[-1][0]:
                pila.pop()
            padre = pila[-1][1]
            if valor.strip() == "":
                padre[clave] = {}
                pila.append((sangria, padre[clave]))
                ultimo = (padre, clave)
            else:
                padre[clave] = _escalar(valor)
                ultimo = None
    return raiz


def _q(v):
    """Texto YAML entre comillas dobles, en una sola linea (los lectores no procesan escapes)."""
    t = _texto(v).replace("\r", " ").replace("\n", " ").replace('"', "'")
    return f'"{t}"'


def _n(v):
    """Numero YAML o null. Un texto que no es numero se escribe entre comillas para no
    perderlo; la revision lo marca y bloquea el calculo."""
    t = _texto(v)
    if t == "":
        return "null"
    x, error = _num_o_error(t)
    if error:
        return _q(t)
    if x.is_integer() and not re.search(r"[.eE]", t):
        return str(int(x))
    return repr(x)


def _b(v):
    return "true" if _bool(v) else "false"


def _lista_yaml(clave, items, sangria=""):
    items = _lista(items)
    if not items:
        return [f"{sangria}{clave}: []"]
    return [f"{sangria}{clave}:"] + [f"{sangria}  - {_q(i)}" for i in items]


def escribir(ruta, texto):
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(texto)


def escribir_proyecto(ruta, p):
    L = ["# Datos del proyecto. Lo escribe la interfaz (scripts/interfaz.py); se puede editar a mano.",
         f"proyecto: {_q(p.get('proyecto'))}",
         f"cliente: {_q(p.get('cliente'))}",
         f"ubicacion: {_q(p.get('ubicacion'))}",
         f"tipo_instalacion: {_q(p.get('tipo_instalacion'))}          # industrial | comercial | residencial | mixto",
         f"tipo_ocupacion: {_q(p.get('tipo_ocupacion'))}            # para factores de demanda (art. 220)",
         f"revision: {_q(p.get('revision') or 'A')}",
         f"fecha: {_q(p.get('fecha'))}",
         f"responsable_calculo: {_q(p.get('responsable_calculo'))}",
         f"revisor: {_q(p.get('revisor'))}",
         f"responsable_tecnico: {_q(p.get('responsable_tecnico'))}       # Quien firma. Debe tener licencia vigente.",
         f"numero_licencia: {_q(p.get('numero_licencia'))}",
         f"descripcion_instalacion: {_q(p.get('descripcion_instalacion'))}",
         ""]
    L += _lista_yaml("alcance_incluye", p.get("alcance_incluye"))
    L += _lista_yaml("alcance_no_incluye", p.get("alcance_no_incluye"))
    L += [""] + _lista_yaml("supuestos_pendientes_de_confirmar", p.get("supuestos_pendientes_de_confirmar"))
    escribir(ruta, "\n".join(L) + "\n")


def escribir_jurisdiccion(ruta, j):
    tx, mx = j.get("texas") or {}, j.get("mexico") or {}
    si, cr = j.get("sitio") or {}, j.get("criterios") or {}
    jur = _texto(j.get("jurisdiccion")).lower()
    L = ["# Jurisdiccion y edicion normativa del proyecto. Lo escribe la interfaz (scripts/interfaz.py).",
         "# EL AGENTE NO CALCULA SIN ESTO.",
         "",
         f"jurisdiccion: {jur if jur in ('mexico', 'texas') else _q(jur)}          # mexico | texas",
         "",
         "texas:",
         '  norma_base: "NFPA 70 (National Electrical Code)"',
         f"  edicion: {_q(tx.get('edicion'))}             # 2023 o 2026: TDLR adopto el NEC 2026 con efecto 1-sep-2026",
         f"  fecha_inicio_obra: {_q(tx.get('fecha_inicio_obra'))}",
         f"  fecha_verificacion_edicion: {_q(tx.get('fecha_verificacion_edicion'))}",
         f"  fuente_consultada: {_q(tx.get('fuente_consultada'))}",
         '  autoridad_estatal: "Texas Department of Licensing and Regulation (TDLR)"',
         f"  ahj_municipal: {_q(tx.get('ahj_municipal'))}",
         f"  enmiendas_locales: {_q(tx.get('enmiendas_locales'))}",
         '  unidades: "AWG/kcmil, pies, F"',
         '  licencia_requerida: "Contratista electrico licenciado por TDLR para trabajo no exento"',
         "",
         "mexico:",
         '  norma_base: "NOM-001-SEDE, Instalaciones Electricas (utilizacion)"',
         f"  edicion: {_q(mx.get('edicion'))}             # Confirmar en el DOF y en el Catalogo Nacional de Normas",
         f"  fecha_verificacion_edicion: {_q(mx.get('fecha_verificacion_edicion'))}",
         f"  fuente_consultada: {_q(mx.get('fuente_consultada'))}",
         f"  unidad_verificacion: {_q(mx.get('unidad_verificacion'))}",
         '  unidades: "mm2 y AWG, metros, C"',
         "",
         "# Datos del sitio que NO se asumen",
         "sitio:",
         f"  icc_disponible_kA: {_n(si.get('icc_disponible_kA'))}",
         f"  fuente_icc: {_q(si.get('fuente_icc'))}",
         f"  temperatura_ambiente_C: {_n(si.get('temperatura_ambiente_C'))}",
         f"  temperatura_terminales_C: {_n(si.get('temperatura_terminales_C'))}",
         f"  altitud_msnm: {_n(si.get('altitud_msnm'))}",
         f"  area_clasificada: {_b(si.get('area_clasificada'))}",
         f"  clasificacion: {_q(si.get('clasificacion'))}",
         "",
         "# Criterios de proyecto (NO son requisitos normativos: son decisiones)",
         "criterios:",
         f"  caida_tension_derivado_pct: {_n(cr.get('caida_tension_derivado_pct'))}",
         f"  caida_tension_alimentador_pct: {_n(cr.get('caida_tension_alimentador_pct'))}",
         f"  caida_tension_total_pct: {_n(cr.get('caida_tension_total_pct'))}",
         f"  margen_crecimiento_pct: {_n(cr.get('margen_crecimiento_pct'))}",
         f"  desbalance_maximo_pct: {_n(cr.get('desbalance_maximo_pct'))}",
         f"  reserva_espacios_pct: {_n(cr.get('reserva_espacios_pct'))}",
         f"  material_conductor: {_texto(cr.get('material_conductor')).lower() or 'cobre'}",
         f"  temp_aislamiento_C: {_n(cr.get('temp_aislamiento_C'))}"]
    escribir(ruta, "\n".join(L) + "\n")


def escribir_tierras(ruta, t, nombre_proyecto):
    g = lambda sec, k: (t.get(sec) or {}).get(k)  # noqa: E731
    L = ["# Red de tierras de la subestacion (IEEE Std 80, suelo uniforme). Lo escribe la interfaz.",
         "# Los valores marcados [CRITERIO] son decisiones de proyecto.",
         "",
         f"proyecto: {_q(t.get('proyecto') or nombre_proyecto)}",
         f"subestacion: {_q(t.get('subestacion'))}",
         "",
         "terreno:",
         f"  resistividad_ohm_m: {_n(g('terreno', 'resistividad_ohm_m'))}      # Medicion Wenner (IEEE Std 81)",
         f"  fuente: {_q(g('terreno', 'fuente'))}",
         "",
         "suministrador:",
         f"  tension_kV: {_n(g('suministrador', 'tension_kV'))}",
         f"  mva_cc_3f: {_n(g('suministrador', 'mva_cc_3f'))}",
         f"  mva_cc_1f: {_n(g('suministrador', 'mva_cc_1f'))}",
         f"  x_r: {_n(g('suministrador', 'x_r'))}",
         f"  frecuencia_Hz: {_n(g('suministrador', 'frecuencia_Hz'))}",
         f"  fuente: {_q(g('suministrador', 'fuente'))}",
         "",
         "falla:",
         f"  tiempo_choque_s: {_n(g('falla', 'tiempo_choque_s'))}          # [CRITERIO]",
         f"  tiempo_conductor_s: {_n(g('falla', 'tiempo_conductor_s'))}       # [CRITERIO]",
         f"  factor_division_Sf: {_n(g('falla', 'factor_division_Sf'))}       # [CRITERIO] 1.0 es conservador",
         "",
         "malla:",
         f"  largo_m: {_n(g('malla', 'largo_m'))}",
         f"  ancho_m: {_n(g('malla', 'ancho_m'))}",
         f"  separacion_m: {_n(g('malla', 'separacion_m'))}",
         f"  profundidad_m: {_n(g('malla', 'profundidad_m'))}            # [CRITERIO]",
         f"  calibre: {_q(_cal(g('malla', 'calibre')))}               # [CRITERIO]",
         f"  material: {_texto(g('malla', 'material')) or 'cobre_duro'}",
         f"  temperatura_ambiente_C: {_n(g('malla', 'temperatura_ambiente_C'))}   # [CRITERIO]",
         f"  temperatura_maxima_C: {_n(g('malla', 'temperatura_maxima_C'))}     # vacio = fusion del material",
         "",
         "varillas:",
         f"  cantidad: {_n(g('varillas', 'cantidad'))}",
         f"  longitud_m: {_n(g('varillas', 'longitud_m'))}",
         f"  en_perimetro: {_b(g('varillas', 'en_perimetro'))}",
         "",
         "capa_superficial:",
         f"  resistividad_ohm_m: {_n(g('capa_superficial', 'resistividad_ohm_m'))}   # [CRITERIO] vacio = sin capa",
         f"  espesor_m: {_n(g('capa_superficial', 'espesor_m'))}",
         "",
         "persona:",
         f"  peso_kg: {_n(g('persona', 'peso_kg'))}                  # 50 o 70 [CRITERIO]",
         "",
         f"resistencia_objetivo_ohm: {_n(t.get('resistencia_objetivo_ohm'))}"]
    escribir(ruta, "\n".join(L) + "\n")


# ------------------------------------------------------------ CSV y unifilar

def escribir_cargas(ruta, filas):
    extras = []
    for f in filas:
        for k in f:
            if k not in COLS_CARGAS and k not in extras and k and not k.startswith("_"):
                extras.append(k)
    cols = COLS_CARGAS + extras
    with open(ruta, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        for f in filas:
            if not any(_texto(f.get(c)) for c in cols):
                continue
            fila = []
            for c in cols:
                v = _texto(f.get(c)).replace("\r", " ").replace("\n", " ")
                if c == "fase":
                    v = v.upper()
                elif c in ("continua", "material"):
                    v = v.lower()
                fila.append(v)
            w.writerow(fila)


def _raices(nodos):
    ids = {_texto(n.get("id")) for n in nodos}
    return [n for n in nodos if not _texto(n.get("padre")) or _texto(n.get("padre")) not in ids]


def _es_bt_sin_trafo(n):
    v, _ = _num_o_error(n.get("tension_V"))
    return (_texto(n.get("tipo")) == "acometida" and v is not None and v <= 1000
            and not (_texto(n.get("kva")) and _texto(n.get("z_pct"))))


def norma_de(j):
    jur = _texto(j.get("jurisdiccion")).lower()
    if jur == "mexico":
        ed = _texto((j.get("mexico") or {}).get("edicion"))
        return ed if ed.upper().startswith("NOM") else f"NOM-001-SEDE-{ed or '[COMPLETAR]'}"
    if jur == "texas":
        return f"NFPA 70 (NEC) {_texto((j.get('texas') or {}).get('edicion')) or '[COMPLETAR]'}"
    return "[COMPLETAR: jurisdiccion y edicion]"


def escribir_unifilar(ruta, u, p, j):
    doc = {k: v for k, v in (u or {}).items() if k != "nodos" and not k.startswith("_")}
    for k in ("proyecto", "cliente", "ubicacion", "revision", "fecha"):
        if _texto(p.get(k)):
            doc[k] = _texto(p.get(k))
    doc["norma"] = norma_de(j)
    icc = _num_o_error((j.get("sitio") or {}).get("icc_disponible_kA"))[0]
    if icc:
        doc["icc_disponible_kA"] = icc if not icc.is_integer() else int(icc)
    else:
        doc.pop("icc_disponible_kA", None)

    nodos = []
    for n in (u or {}).get("nodos", []):
        m = {}
        for k in ORDEN_NODO + [k for k in n if k not in ORDEN_NODO]:
            if k not in n or k.startswith("_"):
                continue
            v = n[k]
            if k in NODO_FLOAT or k in NODO_INT:
                t = _texto(v)
                if t == "":
                    continue
                x, error = _num_o_error(t)
                if error:
                    m[k] = t
                elif x.is_integer():
                    m[k] = int(x)
                else:
                    m[k] = x
            elif k == "notas":
                notas = _lista(v)
                if notas:
                    m[k] = notas
            elif k in NODO_TEXTO:
                t = _texto(v)
                if t == "":
                    continue
                if k in ("tipo", "material"):
                    t = t.lower()
                elif k in ("calibre", "egc"):
                    t = _cal(t)
                m[k] = t
            else:
                m[k] = v
        nodos.append(m)

    # Servicio en baja tension sin transformador propio: la Icc del punto de entrega
    # (dato de CFE en Norma y sitio) va en el nodo raiz, que es donde la lee ec.py.
    for n in _raices(nodos):
        if _es_bt_sin_trafo(n):
            if icc:
                n["icc_kA"] = doc["icc_disponible_kA"]
            else:
                n.pop("icc_kA", None)
    doc["nodos"] = nodos
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# ------------------------------------------------------------ modelo <-> archivos

def ruta_proyecto(pid):
    if not RE_PROYECTO.match(pid or ""):
        raise ValueError("Identificador de proyecto invalido.")
    return os.path.join(PROYECTOS, pid)


def version_de(P):
    tiempos = [os.path.getmtime(os.path.join(P, f)) for f in ENTRADAS if os.path.exists(os.path.join(P, f))]
    return f"{max(tiempos):.6f}" if tiempos else "0"


def _ui(v):
    """Valor para un campo de la interfaz: texto, salvo listas y booleanos."""
    if isinstance(v, bool) or isinstance(v, list):
        return v
    if isinstance(v, dict):
        return {k: _ui(x) for k, x in v.items()}
    return _texto(v)


def cargar_proyecto(pid):
    P = ruta_proyecto(pid)
    if not os.path.isdir(P):
        raise FileNotFoundError(f"No existe el proyecto {pid}.")
    leer = lambda f: leer_yaml(os.path.join(P, f)) if os.path.exists(os.path.join(P, f)) else {}  # noqa: E731
    proy, jur = leer("proyecto.yaml"), leer("jurisdiccion.yaml")

    proyecto = {k: _texto(proy.get(k)) for k in (
        "proyecto", "cliente", "ubicacion", "tipo_instalacion", "tipo_ocupacion", "revision", "fecha",
        "responsable_calculo", "revisor", "responsable_tecnico", "numero_licencia", "descripcion_instalacion")}
    for k in ("alcance_incluye", "alcance_no_incluye", "supuestos_pendientes_de_confirmar"):
        proyecto[k] = _lista(proy.get(k))

    sec = lambda d, k: d.get(k) if isinstance(d.get(k), dict) else {}  # noqa: E731
    tx, mx, si, cr = sec(jur, "texas"), sec(jur, "mexico"), sec(jur, "sitio"), sec(jur, "criterios")
    jurisdiccion = {
        "jurisdiccion": _texto(jur.get("jurisdiccion")).lower(),
        "texas": {k: _texto(tx.get(k)) for k in ("edicion", "fecha_inicio_obra", "fecha_verificacion_edicion",
                                                 "fuente_consultada", "ahj_municipal", "enmiendas_locales")},
        "mexico": {k: _texto(mx.get(k)) for k in ("edicion", "fecha_verificacion_edicion", "fuente_consultada",
                                                  "unidad_verificacion")},
        "sitio": {k: _texto(si.get(k)) for k in ("icc_disponible_kA", "fuente_icc", "temperatura_ambiente_C",
                                                 "temperatura_terminales_C", "altitud_msnm", "clasificacion")},
        "criterios": {k: _texto(cr.get(k)) for k in (
            "caida_tension_derivado_pct", "caida_tension_alimentador_pct", "caida_tension_total_pct",
            "margen_crecimiento_pct", "desbalance_maximo_pct", "reserva_espacios_pct", "material_conductor",
            "temp_aislamiento_C")},
    }
    jurisdiccion["sitio"]["area_clasificada"] = _bool(si.get("area_clasificada"))
    if not jurisdiccion["criterios"]["reserva_espacios_pct"]:
        jurisdiccion["criterios"]["reserva_espacios_pct"] = "25"

    cargas = []
    ruta_csv = os.path.join(P, "cargas.csv")
    if os.path.exists(ruta_csv):
        with open(ruta_csv, encoding="utf-8-sig", newline="") as fh:
            for fila in csv.DictReader(fh):
                cargas.append({k: _texto(v) for k, v in fila.items() if k})

    unifilar = {"nodos": []}
    ruta_uni = os.path.join(P, "unifilar.json")
    if os.path.exists(ruta_uni):
        with open(ruta_uni, encoding="utf-8-sig") as fh:
            unifilar = json.load(fh)
        if _texto(unifilar.get("icc_disponible_kA")) and not jurisdiccion["sitio"]["icc_disponible_kA"]:
            jurisdiccion["sitio"]["icc_disponible_kA"] = _texto(unifilar.get("icc_disponible_kA"))
        unifilar["nodos"] = [{k: (_lista(v) if k == "notas" else (v if k not in ORDEN_NODO else _ui(v)))
                              for k, v in n.items()} for n in unifilar.get("nodos", [])]
        # La Icc de un servicio en BT se captura en Norma y sitio; si solo estaba en el nodo, se sube.
        for n in _raices(unifilar["nodos"]):
            if _es_bt_sin_trafo(n) and _texto(n.get("icc_kA")) and not jurisdiccion["sitio"]["icc_disponible_kA"]:
                jurisdiccion["sitio"]["icc_disponible_kA"] = _texto(n.get("icc_kA"))
            if _es_bt_sin_trafo(n):
                n.pop("icc_kA", None)

    tierras = None
    if os.path.exists(os.path.join(P, "red-de-tierras.yaml")):
        tierras = _ui(leer("red-de-tierras.yaml"))
        vr = tierras.get("varillas") if isinstance(tierras.get("varillas"), dict) else {}
        tierras.setdefault("varillas", vr)["en_perimetro"] = _bool(vr.get("en_perimetro", True))

    return {"proyecto": proyecto, "jurisdiccion": jurisdiccion, "unifilar": unifilar,
            "cargas": cargas, "tierras": tierras}


def guardar_proyecto(pid, m):
    P = ruta_proyecto(pid)
    os.makedirs(P, exist_ok=True)
    p, j = m.get("proyecto") or {}, m.get("jurisdiccion") or {}
    escribir_proyecto(os.path.join(P, "proyecto.yaml"), p)
    escribir_jurisdiccion(os.path.join(P, "jurisdiccion.yaml"), j)
    escribir_cargas(os.path.join(P, "cargas.csv"), m.get("cargas") or [])
    escribir_unifilar(os.path.join(P, "unifilar.json"), m.get("unifilar") or {}, p, j)
    rt = os.path.join(P, "red-de-tierras.yaml")
    if m.get("tierras"):
        escribir_tierras(rt, m["tierras"], _texto(p.get("proyecto")))
    elif os.path.exists(rt):
        os.remove(rt)
    return version_de(P)


def plantilla_tierras():
    t = _ui(leer_yaml(os.path.join(CONFIG, "red-de-tierras.yaml")))
    t.setdefault("varillas", {})["en_perimetro"] = True
    return t


def crear_proyecto(nombre, origen):
    base = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:48] or "proyecto"
    pid, i = base, 2
    while os.path.exists(os.path.join(PROYECTOS, pid)):
        pid, i = f"{base}-{i}", i + 1
    P = ruta_proyecto(pid)
    os.makedirs(P)
    for f in ("proyecto.yaml", "jurisdiccion.yaml"):
        shutil.copyfile(os.path.join(CONFIG, f), os.path.join(P, f))
    if origen == "demo":
        for f in ("cargas.csv", "unifilar.json", "red-de-tierras.yaml"):
            shutil.copyfile(os.path.join(DEMO, f), os.path.join(P, f))
    else:
        escribir(os.path.join(P, "cargas.csv"), ",".join(COLS_CARGAS) + "\n")
        escribir(os.path.join(P, "unifilar.json"), '{\n  "nodos": []\n}\n')
    m = cargar_proyecto(pid)
    m["proyecto"]["proyecto"] = nombre.strip()
    m["proyecto"]["revision"] = m["proyecto"]["revision"] or "A"
    m["proyecto"]["fecha"] = date.today().isoformat()
    if origen == "demo":
        with open(os.path.join(DEMO, "unifilar.json"), encoding="utf-8") as fh:
            demo = json.load(fh)
        m["proyecto"]["cliente"] = demo.get("cliente", "")
        m["proyecto"]["ubicacion"] = demo.get("ubicacion", "")
        m["proyecto"]["tipo_instalacion"] = "industrial"
    # Datos que nunca se asumen: la plantilla trae valores de ejemplo que hay que pedir.
    m["jurisdiccion"]["jurisdiccion"] = ""
    m["jurisdiccion"]["texas"]["edicion"] = ""
    m["jurisdiccion"]["sitio"]["temperatura_terminales_C"] = ""
    guardar_proyecto(pid, m)
    return pid


def listar_proyectos():
    if not os.path.isdir(PROYECTOS):
        return []
    lista = []
    for pid in sorted(os.listdir(PROYECTOS)):
        P = os.path.join(PROYECTOS, pid)
        if not (RE_PROYECTO.match(pid) and os.path.isdir(P)):
            continue
        nombre = ""
        try:
            nombre = _texto(leer_yaml(os.path.join(P, "proyecto.yaml")).get("proyecto"))
        except (OSError, ValueError):
            pass
        lista.append({"id": pid, "nombre": nombre or pid, "modificado": float(version_de(P))})
    return sorted(lista, key=lambda x: -x["modificado"])


def catalogos():
    def claves(archivo, ruta):
        try:
            with open(os.path.join(RAIZ, "datos", archivo), encoding="utf-8") as fh:
                d = json.load(fh)
            for k in ruta:
                d = d[k]
            return d
        except (OSError, KeyError, ValueError):
            return []
    ocup = [x.get("ocupacion") for x in claves("factores_demanda_220.json", ["factores_demanda_alumbrado_220_42"])]
    mats = claves("ieee80.json", ["materiales"])
    return {"tipos_nodo": TIPOS_NODO, "calibres": CALIBRES, "ocupaciones": [o for o in ocup if o],
            "materiales_malla": [{"clave": k, "descripcion": v.get("descripcion", k)} for k, v in mats.items()]
            if isinstance(mats, dict) else [],
            "pasos": [{"clave": c, "titulo": t} for c, t in PASOS]}


# ------------------------------------------------------------ revision previa

def revisar(m):
    """Revisa los datos antes de calcular. Cada hallazgo dice que pasos bloquea.
    Aqui solo se revisa lo que los scripts no revisan o suponen en silencio;
    las reglas de ingenieria las aplican los scripts."""
    H = []

    def h(nivel, seccion, ref, mensaje, bloquea=()):
        H.append({"nivel": nivel, "seccion": seccion, "ref": ref, "mensaje": mensaje, "bloquea": list(bloquea)})

    p = m.get("proyecto") or {}
    j = m.get("jurisdiccion") or {}
    si, cr = j.get("sitio") or {}, j.get("criterios") or {}
    nodos = (m.get("unifilar") or {}).get("nodos") or []
    cargas = [c for c in (m.get("cargas") or []) if any(_texto(v) for v in c.values())]
    t = m.get("tierras")

    # --- proyecto
    for k, nombre in (("proyecto", "Nombre del proyecto"), ("cliente", "Cliente"),
                      ("ubicacion", "Ubicación"), ("tipo_instalacion", "Tipo de instalación")):
        if not _texto(p.get(k)):
            h("pendiente", "proyecto", f"proyecto.{k}", f"{nombre}: la memoria saldrá con [COMPLETAR].")
    if not _lista(p.get("alcance_incluye")):
        h("pendiente", "proyecto", "proyecto.alcance_incluye", "Alcance: qué cubre esta memoria.")
    if not _lista(p.get("alcance_no_incluye")):
        h("pendiente", "proyecto", "proyecto.alcance_no_incluye",
          "Alcance negativo (qué NO incluye): es obligatorio en la memoria.")
    if _texto(p.get("fecha")) and not re.match(r"^\d{4}-\d{2}-\d{2}$", _texto(p.get("fecha"))):
        h("aviso", "proyecto", "proyecto.fecha", "Fecha en formato AAAA-MM-DD.")
    for k, nombre in (("responsable_tecnico", "Responsable técnico"), ("numero_licencia", "Número de licencia")):
        if not _texto(p.get(k)):
            h("aviso", "proyecto", f"proyecto.{k}",
              f"{nombre}: necesario antes de emitir. La memoria requiere la firma de un responsable con licencia vigente.")

    # --- jurisdiccion y edicion: sin esto no se calcula nada
    jur = _texto(j.get("jurisdiccion")).lower()
    if jur not in ("mexico", "texas"):
        h("bloquea", "norma", "jurisdiccion.jurisdiccion",
          "Declara la jurisdicción (México o Texas). El agente no calcula sin esto.", TODO)
    elif jur == "mexico":
        mx = j.get("mexico") or {}
        for k, msg in (("edicion", "Edición de la NOM-001-SEDE: confírmala en el DOF y en el Catálogo Nacional de Normas. No se asume."),
                       ("fecha_verificacion_edicion", "Fecha en que confirmaste la edición vigente."),
                       ("fuente_consultada", "Fuente donde confirmaste la edición (DOF, Catálogo Nacional de Normas).")):
            if not _texto(mx.get(k)):
                h("bloquea", "norma", f"jurisdiccion.mexico.{k}", msg, TODO)
        if not _texto(mx.get("unidad_verificacion")):
            h("pendiente", "norma", "jurisdiccion.mexico.unidad_verificacion",
              "Unidad de Verificación (UVIE) que emitirá el dictamen.")
    else:
        tx = j.get("texas") or {}
        if _texto(tx.get("edicion")) not in ("2023", "2026"):
            h("bloquea", "norma", "jurisdiccion.texas.edicion",
              "Edición del NEC (2023 o 2026). TDLR adoptó el NEC 2026 con efecto el 1-sep-2026.", TODO)
        for k, msg in (("fecha_inicio_obra", "Fecha de inicio de obra: define si rige el NEC 2023 o el 2026."),
                       ("fecha_verificacion_edicion", "Fecha en que confirmaste la edición con TDLR y el AHJ."),
                       ("fuente_consultada", "Fuente de la confirmación (TDLR, AHJ municipal).")):
            if not _texto(tx.get(k)):
                h("bloquea", "norma", f"jurisdiccion.texas.{k}", msg, TODO)
        if _texto(tx.get("fecha_inicio_obra")) >= "2026-09-01" and _texto(tx.get("edicion")) == "2023":
            h("aviso", "norma", "jurisdiccion.texas.edicion",
              "La obra inicia después del 1-sep-2026, cuando TDLR adoptó el NEC 2026. Confirma que rige el 2023.")
        if not _texto(tx.get("ahj_municipal")):
            h("pendiente", "norma", "jurisdiccion.texas.ahj_municipal",
              "AHJ municipal: puede tener enmiendas locales.")
        h("aviso", "norma", "jurisdiccion.jurisdiccion",
          "Texas: los scripts trabajan en metros y °C y la memoria sale en español. "
          "Captura longitudes en metros; Claude convierte y traduce el entregable.")

    # --- sitio
    ta, err = _num_o_error(si.get("temperatura_ambiente_C"))
    if ta is None and not err:
        h("bloquea", "norma", "jurisdiccion.sitio.temperatura_ambiente_C",
          "Temperatura ambiente de diseño: nunca se asume (sin ella el cálculo usaría 30 °C).", ("circuitos", "memoria"))
    elif err or not ta.is_integer() or not -100 <= ta <= 85:
        h("bloquea", "norma", "jurisdiccion.sitio.temperatura_ambiente_C",
          "Temperatura ambiente: número entero en °C, hasta 85 (la tabla de factores usa rangos enteros).",
          ("circuitos", "memoria"))
    if _texto(si.get("temperatura_terminales_C")) not in ("60", "75", "90"):
        h("bloquea", "norma", "jurisdiccion.sitio.temperatura_terminales_C",
          "Temperatura de terminales del equipo real (60, 75 o 90 °C): nunca se asume.", ("circuitos", "memoria"))
    icc, err = _num_o_error(si.get("icc_disponible_kA"))
    if err or (icc is not None and icc <= 0):
        h("bloquea", "norma", "jurisdiccion.sitio.icc_disponible_kA", "Icc disponible: número mayor que 0, en kA.", P_CC)
    elif icc is None:
        h("pendiente", "norma", "jurisdiccion.sitio.icc_disponible_kA",
          "Icc en el punto de entrega: pídela a la compañía suministradora (oficio).")
    elif not _texto(si.get("fuente_icc")):
        h("pendiente", "norma", "jurisdiccion.sitio.fuente_icc", "Fuente de la Icc (oficio de CFE o de la utility, fecha).")
    if _bool(si.get("area_clasificada")) and not _texto(si.get("clasificacion")):
        h("pendiente", "norma", "jurisdiccion.sitio.clasificacion", "Clasificación del área (clase, división o zona).")
    for k in ("altitud_msnm",):
        if _num_o_error(si.get(k))[1]:
            h("aviso", "norma", f"jurisdiccion.sitio.{k}", "Altitud: número en metros sobre el nivel del mar.")

    # --- criterios
    dv, err = _num_o_error(cr.get("caida_tension_derivado_pct"))
    if err or dv is None or dv <= 0:
        h("bloquea", "norma", "jurisdiccion.criterios.caida_tension_derivado_pct",
          "Límite de caída de tensión del derivado (%): número mayor que 0.", ("circuitos", "memoria"))
    if _texto(cr.get("temp_aislamiento_C")) not in ("60", "75", "90"):
        h("bloquea", "norma", "jurisdiccion.criterios.temp_aislamiento_C",
          "Clase de aislamiento: 60, 75 o 90 °C.", ("circuitos", "memoria"))
    if _texto(cr.get("material_conductor")).lower() not in ("cobre", "aluminio"):
        h("bloquea", "norma", "jurisdiccion.criterios.material_conductor", "Material del conductor: cobre o aluminio.",
          ("circuitos", "memoria"))
    res, err = _num_o_error(cr.get("reserva_espacios_pct"))
    if err or res is None or res < 0:
        h("bloquea", "norma", "jurisdiccion.criterios.reserva_espacios_pct",
          "Reserva de espacios en tableros (%): número de 0 en adelante.", ("squared",))
    for k in ("caida_tension_alimentador_pct", "caida_tension_total_pct", "margen_crecimiento_pct",
              "desbalance_maximo_pct"):
        x, err = _num_o_error(cr.get(k))
        if err or x is None or x < 0:
            h("pendiente", "norma", f"jurisdiccion.criterios.{k}", "Criterio de proyecto: número de 0 en adelante.")

    # --- unifilar
    ids, tableros_uni = {}, {}
    if not nodos:
        h("bloquea", "unifilar", "unifilar", "Agrega el diagrama unifilar: al menos la acometida y un tablero.", P_UNI)
    for i, n in enumerate(nodos):
        nid = _texto(n.get("id"))
        ref = f"unifilar.nodos.{i}"
        nombre = nid or f"Nodo {i + 1}"
        if not nid:
            h("bloquea", "unifilar", f"{ref}.id", f"{nombre}: falta el identificador (p. ej. TG-1).", P_UNI)
        elif not RE_ID.match(nid):
            h("bloquea", "unifilar", f"{ref}.id", f"{nombre}: el identificador no lleva espacios ni símbolos (use TD-1).", P_UNI)
        elif nid in ids:
            h("bloquea", "unifilar", f"{ref}.id", f"{nombre}: identificador repetido.", P_UNI)
        else:
            ids[nid] = i
        tipo = _texto(n.get("tipo")).lower()
        if tipo not in TIPOS_NODO:
            h("bloquea", "unifilar", f"{ref}.tipo", f"{nombre}: elige el tipo de equipo.", P_UNI)
        if tipo in ("tablero", "barra") and nid:
            tableros_uni[nid] = n
        for k in NODO_FLOAT + NODO_INT:
            x, err = _num_o_error(n.get(k))
            if err or (x is not None and x < 0):
                h("bloquea", "unifilar", f"{ref}.{k}", f"{nombre}: '{_texto(n.get(k))}' no es un número válido.", P_UNI)
            elif x is not None and k in NODO_INT and not x.is_integer():
                h("bloquea", "unifilar", f"{ref}.{k}", f"{nombre}: {k} debe ser un número entero.", P_UNI)
        if _texto(n.get("fases")) and _texto(n.get("fases")) not in ("1", "2", "3"):
            h("bloquea", "unifilar", f"{ref}.fases", f"{nombre}: fases debe ser 1, 2 o 3.", P_UNI)
        if _texto(n.get("hilos")) and _texto(n.get("hilos")) not in ("2", "3", "4"):
            h("bloquea", "unifilar", f"{ref}.hilos", f"{nombre}: hilos debe ser 2, 3 o 4.", P_UNI)

    for i, n in enumerate(nodos):
        nid, ref = _texto(n.get("id")), f"unifilar.nodos.{i}"
        nombre = nid or f"Nodo {i + 1}"
        tipo = _texto(n.get("tipo")).lower()
        padre = _texto(n.get("padre"))
        if padre and padre not in ids:
            h("bloquea", "unifilar", f"{ref}.padre", f"{nombre}: el nodo de arriba '{padre}' no existe.", P_UNI)
        elif padre and padre == nid:
            h("bloquea", "unifilar", f"{ref}.padre", f"{nombre}: no puede alimentarse a sí mismo.", P_UNI)
        tension = _num_o_error(n.get("tension_V"))[0]
        if tension is None and not _num_o_error(n.get("tension_V"))[1]:
            if tipo in ("acometida", "transformador", "tablero", "barra"):
                h("bloquea", "unifilar", f"{ref}.tension_V",
                  f"{nombre}: tensión nominal en V ({'del secundario' if tipo == 'transformador' else 'entre fases'}).",
                  ("cortocircuito", "validar_sccr", "squared", "circuitos", "memoria"))
            elif tipo not in ("medidor", "interruptor_principal"):
                h("pendiente", "unifilar", f"{ref}.tension_V", f"{nombre}: tensión nominal en V.")
        if tipo == "transformador":
            for k, msg in (("kva", "kVA de placa"), ("z_pct", "Z% de placa")):
                if not _texto(n.get(k)):
                    h("bloquea", "unifilar", f"{ref}.{k}", f"{nombre}: {msg}. Nunca se supone.", P_CC)
            z = _num_o_error(n.get("z_pct"))[0]
            if z is not None and not 0.5 <= z <= 20:
                h("aviso", "unifilar", f"{ref}.z_pct", f"{nombre}: Z% = {z:g} fuera de lo usual (típicamente 1.5 a 10 %). Revisa la placa.")
            if not _texto(n.get("conexion")):
                h("pendiente", "unifilar", f"{ref}.conexion", f"{nombre}: grupo de conexión (p. ej. Dyn11).")
            if not (_texto(n.get("proteccion_primario_A")) and _texto(n.get("proteccion_secundario_A"))):
                h("pendiente", "unifilar", f"{ref}.proteccion_primario_A",
                  f"{nombre}: protección de primario y secundario (art. 450).")
        if tipo in ("tablero", "barra"):
            if not _texto(n.get("sccr_kA")):
                h("pendiente", "unifilar", f"{ref}.sccr_kA", f"{nombre}: SCCR del tablero (kA).")
            if padre and not _texto(n.get("longitud_m")):
                h("pendiente", "unifilar", f"{ref}.longitud_m",
                  f"{nombre}: longitud real del alimentador. Sin ella la Icc no descuenta el conductor (resultado conservador).")
        if tipo in FUENTES and _texto(n.get("aporte_icc_kA")) == "":
            h("pendiente", "unifilar", f"{ref}.aporte_icc_kA",
              f"{nombre}: corriente de falla que aporta según el fabricante. Sin ella la Icc de su sistema no la incluye.")
        if tipo == "motor" and not _texto(n.get("carga_va")):
            h("pendiente", "unifilar", f"{ref}.carga_va", f"{nombre}: carga en VA (base de su aporte a la Icc).")
        lon = _num_o_error(n.get("longitud_m"))[0]
        cal = _cal(n.get("calibre"))
        if lon and lon > 0 and not cal:
            h("bloquea", "unifilar", f"{ref}.calibre", f"{nombre}: calibre del conductor que lo alimenta (hay longitud).", P_CC)
        if cal and cal not in CALIBRES:
            h("bloquea", "unifilar", f"{ref}.calibre", f"{nombre}: calibre '{_texto(n.get('calibre'))}' no está en la tabla.", P_CC)
        if _texto(n.get("egc")) and _cal(n.get("egc")) not in CALIBRES:
            h("aviso", "unifilar", f"{ref}.egc", f"{nombre}: calibre de EGC '{_texto(n.get('egc'))}' no reconocido.")
        mat = _texto(n.get("material")).lower()
        if mat and mat not in ("cobre", "aluminio"):
            h("bloquea", "unifilar", f"{ref}.material", f"{nombre}: material cobre o aluminio.", P_CC)

    # Ciclos
    padres = {_texto(n.get("id")): _texto(n.get("padre")) for n in nodos if _texto(n.get("id"))}
    en_ciclo = set()
    for nid in padres:
        vistos, actual = set(), nid
        while actual in padres and padres[actual] and actual not in vistos:
            vistos.add(actual)
            actual = padres[actual]
        if actual in vistos:
            en_ciclo.add(nid)
    for nid in sorted(en_ciclo):
        h("bloquea", "unifilar", f"unifilar.nodos.{ids[nid]}.padre", f"{nid}: forma un ciclo en la jerarquía.", P_UNI)

    raices = [n for n in _raices(nodos) if _texto(n.get("id")) not in en_ciclo]
    if nodos and len(raices) > 1:
        h("aviso", "unifilar", "unifilar",
          f"Hay {len(raices)} nodos sin alimentación aguas arriba ({', '.join(_texto(r.get('id')) or '?' for r in raices)}). "
          "Normalmente solo la acometida está en la raíz.")
    for r in raices:
        i = nodos.index(r)
        tipo, nombre = _texto(r.get("tipo")).lower(), _texto(r.get("id")) or f"Nodo {i + 1}"
        v = _num_o_error(r.get("tension_V"))[0]
        if tipo == "acometida" and v is not None and v <= 1000:
            if not (_texto(r.get("kva")) and _texto(r.get("z_pct"))) and icc is None:
                h("bloquea", "unifilar", f"unifilar.nodos.{i}.tension_V",
                  f"{nombre}: servicio en baja tensión. Da la Icc en el punto de entrega (Norma y sitio) "
                  "o el kVA y Z% del transformador del suministrador.", P_CC)
        elif tipo == "acometida" and v is not None and v > 1000 and _texto(r.get("longitud_m")):
            h("aviso", "unifilar", f"unifilar.nodos.{i}.longitud_m",
              f"{nombre}: con bus infinito no se declara conductor en la acometida de media tensión.")
        elif tipo not in ("acometida", "transformador", "generador", "") and nodos:
            h("bloquea", "unifilar", f"unifilar.nodos.{i}.tipo",
              f"{nombre}: el nodo de la raíz debe ser la acometida o un transformador.", P_CC)

    # --- cargas
    material_def = _texto(cr.get("material_conductor")).lower() or "cobre"
    if not cargas:
        h("bloquea", "cargas", "cargas", "Agrega al menos una carga al cuadro.", P_CARG)
    vistos, sin_ncond, motores, clasificables = {}, [], [], []
    for i, c in enumerate(m.get("cargas") or []):
        if not any(_texto(v) for v in c.values()):
            continue
        ref, cid = f"cargas.{i}", _texto(c.get("id"))
        nombre = cid or f"Fila {i + 1}"
        if not cid:
            h("bloquea", "cargas", f"{ref}.id", f"{nombre}: falta el identificador del circuito.", P_CARG)
        elif cid in vistos:
            h("bloquea", "cargas", f"{ref}.id", f"{nombre}: identificador repetido.", P_CARG)
        else:
            vistos[cid] = i
        if not _texto(c.get("nombre")):
            h("pendiente", "cargas", f"{ref}.nombre", f"{nombre}: descripción del equipo.")
        va, err = _num_o_error(c.get("va"))
        if va is None and not err:
            h("bloquea", "cargas", f"{ref}.va", f"{nombre}: carga en VA. Nunca se estima.", P_CARG)
        elif err or va <= 0:
            h("bloquea", "cargas", f"{ref}.va", f"{nombre}: VA debe ser un número mayor que 0, sin comas ni unidades.", P_CARG)
        fases = _texto(c.get("fases"))
        if fases not in ("1", "2", "3"):
            h("bloquea", "cargas", f"{ref}.fases", f"{nombre}: conexión: 1 = fase-neutro, 2 = fase-fase, 3 = trifásica.", P_CARG)
        vt, err = _num_o_error(c.get("tension"))
        if vt is None and not err:
            h("bloquea", "cargas", f"{ref}.tension", f"{nombre}: tensión de la carga en V.", P_CARG)
        elif err or vt <= 0:
            h("bloquea", "cargas", f"{ref}.tension", f"{nombre}: tensión debe ser un número mayor que 0.", P_CARG)
        if _texto(c.get("continua")).lower() not in ("si", "no"):
            h("bloquea", "cargas", f"{ref}.continua",
              f"{nombre}: ¿opera 3 horas o más de forma continua? Se pregunta caso por caso.", P_CARG)
        tab = _texto(c.get("tablero"))
        if not tab:
            h("bloquea", "cargas", f"{ref}.tablero", f"{nombre}: tablero que la alimenta.", P_CARG)
        elif tab not in tableros_uni:
            h("bloquea", "cargas", f"{ref}.tablero", f"{nombre}: el tablero '{tab}' no está en el unifilar como tablero.", P_CARG)
        lon, err = _num_o_error(c.get("longitud_m"))
        if lon is None and not err:
            h("pendiente", "cargas", f"{ref}.longitud_m",
              f"{nombre}: longitud real del recorrido. Sin ella no se verifica la caída de tensión.")
        elif err or lon <= 0:
            h("bloquea", "cargas", f"{ref}.longitud_m", f"{nombre}: longitud en metros, mayor que 0.", P_CARG)
        nc, err = _num_o_error(c.get("n_conductores"))
        if nc is None and not err:
            sin_ncond.append(nombre)
        elif err or nc < 1 or not nc.is_integer():
            h("bloquea", "cargas", f"{ref}.n_conductores", f"{nombre}: conductores portadores: número entero de 1 en adelante.", P_CARG)
        mat = _texto(c.get("material")).lower()
        if mat and mat not in ("cobre", "aluminio"):
            h("bloquea", "cargas", f"{ref}.material", f"{nombre}: material cobre o aluminio.", P_CARG)
        amb, err = _num_o_error(c.get("ambiente_c"))
        if err or (amb is not None and (not amb.is_integer() or not -100 <= amb <= 85)):
            h("bloquea", "cargas", f"{ref}.ambiente_c", f"{nombre}: temperatura ambiente en °C, número entero hasta 85.", P_CARG)
        fase = re.sub(r"\s", "", _texto(c.get("fase")).upper())
        if fase:
            validas = {"1": ("A", "B", "C"), "2": ("AB", "BC", "CA", "BA", "CB", "AC")}.get(fases, ())
            if fases == "3":
                h("aviso", "cargas", f"{ref}.fase", f"{nombre}: una carga trifásica ocupa las tres fases; la columna fase se ignora.")
            elif fase not in validas:
                h("bloquea", "cargas", f"{ref}.fase",
                  f"{nombre}: fase {'A, B o C' if fases == '1' else 'AB, BC o CA'} (o vacío para que la asigne el balanceo).", P_CARG)
        if tab in tableros_uni and vt and fases in ("1", "2", "3"):
            nodo = tableros_uni[tab]
            v_ll = _num_o_error(nodo.get("tension_V"))[0]
            f_tab = _texto(nodo.get("fases")) or "3"
            hilos = _texto(nodo.get("hilos")) or ("4" if f_tab == "3" else "3")
            if v_ll:
                v_fn = v_ll / math.sqrt(3) if f_tab == "3" else v_ll / 2
                if fases == "3" and f_tab != "3":
                    h("pendiente", "cargas", f"{ref}.fases", f"{nombre}: carga trifásica en el tablero monofásico {tab}.")
                elif fases == "1" and ((f_tab == "3" and hilos != "4") or (f_tab != "3" and hilos not in ("3", "4"))):
                    h("pendiente", "cargas", f"{ref}.fases", f"{nombre}: carga fase-neutro en {tab}, que no tiene neutro.")
                else:
                    esperada = v_fn if fases == "1" else v_ll
                    if abs(vt - esperada) / esperada > 0.05:
                        con = "fase-neutro" if fases == "1" else ("fase-fase" if fases == "2" else "trifásica")
                        h("pendiente", "cargas", f"{ref}.tension",
                          f"{nombre}: {vt:g} V no corresponde a una carga {con} de {tab} "
                          f"({v_ll:g} V entre fases, {v_fn:.0f} V fase-neutro). Revisa la tensión o la conexión.")
        texto = f"{_texto(c.get('nombre'))} {_texto(c.get('notas'))}".lower()
        if re.search(r"\bmotor|\bhp\b|compresor|bomba|ventilador|extractor|amasadora|banda", texto):
            motores.append(nombre)
        if re.search(r"harina|az[uú]car|grano|solvente|pintura|bater[ií]a|polvo", texto):
            clasificables.append(nombre)
    if sin_ncond:
        h("aviso", "cargas", "cargas",
          f"Se suponen 3 conductores portadores en la canalización (sin ajuste por agrupamiento): {', '.join(sin_ncond)}.")
    if motores:
        h("aviso", "cargas", "cargas",
          f"Posibles motores ({', '.join(motores)}): el agente todavía no aplica el art. 430 (corriente de tabla, "
          "protección 430.52). Se dimensionan como carga general; Claude debe revisarlos.")
    if clasificables and not _bool(si.get("area_clasificada")):
        h("aviso", "norma", "jurisdiccion.sitio.area_clasificada",
          f"Hay cargas que sugieren polvos, solventes o baterías ({', '.join(clasificables)}). "
          "Confirma si el área es clasificada antes de especificar equipo.")
    if material_def == "aluminio":
        h("aviso", "cargas", "cargas", "Material por omisión aluminio: el aluminio empieza en 12 AWG en las tablas.")

    # --- red de tierras
    if t:
        T = ("tierras",)
        g = lambda sec, k: (t.get(sec) or {}).get(k) if isinstance(t.get(sec), dict) else None  # noqa: E731

        def num(sec, k, nombre, requerido=False, positivo=True, entero=False):
            ref = f"tierras.{sec}.{k}" if sec else f"tierras.{k}"
            v, err = _num_o_error(g(sec, k) if sec else t.get(k))
            if v is None and not err:
                if requerido:
                    h("bloquea", "tierras", ref, f"{nombre}: dato obligatorio. No se supone.", T)
                return None
            if err or (positivo and v <= 0) or (entero and not v.is_integer()):
                h("bloquea", "tierras", ref,
                  f"{nombre}: número {'entero ' if entero else ''}{'mayor que 0' if positivo else 'válido'}.", T)
                return None
            return v

        num("terreno", "resistividad_ohm_m", "Resistividad del terreno (Ω·m)", True)
        if not _texto(g("terreno", "fuente")):
            h("pendiente", "tierras", "tierras.terreno.fuente", "Fuente de la resistividad: informe de medición Wenner y fecha.")
        kv = num("suministrador", "tension_kV", "Tensión del suministro (kV)", True)
        num("suministrador", "mva_cc_3f", "Potencia de cortocircuito trifásica (MVA)", True)
        if num("suministrador", "mva_cc_1f", "Potencia de cortocircuito monofásica (MVA)") is None and \
                not _num_o_error(g("suministrador", "mva_cc_1f"))[1]:
            h("pendiente", "tierras", "tierras.suministrador.mva_cc_1f",
              "Potencia de cortocircuito monofásica: sin ella se usa la trifásica. Pídela al suministrador.")
        if num("suministrador", "x_r", "Relación X/R") is None and not _num_o_error(g("suministrador", "x_r"))[1]:
            h("pendiente", "tierras", "tierras.suministrador.x_r", "Relación X/R en el punto de entrega: sin ella Df = 1.")
        num("suministrador", "frecuencia_Hz", "Frecuencia (Hz)")
        if not _texto(g("suministrador", "fuente")):
            h("pendiente", "tierras", "tierras.suministrador.fuente", "Fuente de los datos del suministrador (oficio y fecha).")
        num("falla", "tiempo_choque_s", "Tiempo de liberación de la falla (s)")
        num("falla", "tiempo_conductor_s", "Tiempo para dimensionar el conductor (s)")
        sf = num("falla", "factor_division_Sf", "Factor de división Sf")
        if sf is not None and sf > 1:
            h("bloquea", "tierras", "tierras.falla.factor_division_Sf", "Sf va de 0 a 1.", T)
        elif sf is not None and sf < 1:
            h("aviso", "tierras", "tierras.falla.factor_division_Sf",
              f"Sf = {sf:g} requiere justificación con un estudio de división de corriente.")
        largo = num("malla", "largo_m", "Largo de la malla (m)", True)
        ancho = num("malla", "ancho_m", "Ancho de la malla (m)", True)
        d = num("malla", "separacion_m", "Separación entre conductores (m)", True)
        if d and largo and ancho and d > min(largo, ancho):
            h("bloquea", "tierras", "tierras.malla.separacion_m", "La separación no puede ser mayor que el lado corto de la malla.", T)
        num("malla", "profundidad_m", "Profundidad de la malla (m)")
        if _cal(g("malla", "calibre")) and _cal(g("malla", "calibre")) not in CALIBRES:
            h("bloquea", "tierras", "tierras.malla.calibre", "Calibre de la malla: de la tabla (p. ej. 4/0).", T)
        mats = [x["clave"] for x in catalogos()["materiales_malla"]]
        if _texto(g("malla", "material")) and mats and _texto(g("malla", "material")) not in mats:
            h("bloquea", "tierras", "tierras.malla.material", "Material de la malla: elige uno de la lista (IEEE 80 Tabla 1).", T)
        tamb = num("malla", "temperatura_ambiente_C", "Temperatura ambiente de la malla (°C)", positivo=False)
        tmax = num("malla", "temperatura_maxima_C", "Temperatura máxima del conductor (°C)")
        if tmax is not None and tamb is not None and tmax <= tamb:
            h("bloquea", "tierras", "tierras.malla.temperatura_maxima_C", "La temperatura máxima debe ser mayor que la ambiente.", T)
        nvar = num("varillas", "cantidad", "Cantidad de varillas", positivo=False, entero=True)
        if nvar is not None and nvar < 0:
            h("bloquea", "tierras", "tierras.varillas.cantidad", "Cantidad de varillas: 0 o más.", T)
        if nvar:
            num("varillas", "longitud_m", "Longitud de varilla (m)", True)
        rs, es = _texto(g("capa_superficial", "resistividad_ohm_m")), _texto(g("capa_superficial", "espesor_m"))
        num("capa_superficial", "resistividad_ohm_m", "Resistividad de la capa superficial (Ω·m)")
        num("capa_superficial", "espesor_m", "Espesor de la capa superficial (m)")
        if bool(rs) != bool(es):
            h("bloquea", "tierras", "tierras.capa_superficial.espesor_m",
              "Capa superficial: da resistividad y espesor, o deja los dos vacíos (sin capa).", T)
        if _texto(g("persona", "peso_kg")) not in ("50", "70"):
            h("bloquea", "tierras", "tierras.persona.peso_kg", "Peso de la persona: 50 o 70 kg.", T)
        num(None, "resistencia_objetivo_ohm", "Resistencia objetivo (Ω)")
        acom = next((r for r in raices if _texto(r.get("tipo")) == "acometida"), None)
        v_acom = _num_o_error(acom.get("tension_V"))[0] if acom else None
        if kv and v_acom and v_acom > 1000 and abs(v_acom / 1000 - kv) / kv > 0.05:
            h("aviso", "tierras", "tierras.suministrador.tension_kV",
              f"La acometida del unifilar es de {v_acom / 1000:g} kV y la red de tierras dice {kv:g} kV.")
    return H


# ------------------------------------------------------------ flujo de calculo

def _cmd(args):
    return "python " + " ".join(f'"{a}"' if (" " in a or not a) else a for a in args)


def correr(args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run([sys.executable] + args, cwd=RAIZ, capture_output=True, env=env, timeout=180)
    except subprocess.TimeoutExpired:
        return 1, None, "El script tardó más de 3 minutos y se detuvo."
    out = r.stdout.decode("utf-8", "replace")
    err = r.stderr.decode("utf-8", "replace")
    try:
        datos = json.loads(out)
    except ValueError:
        datos = None
    return r.returncode, datos, (err.strip() or out.strip())


def calcular(pid):
    P = ruta_proyecto(pid)

    def rel(f):
        try:
            return os.path.relpath(os.path.join(P, f), RAIZ).replace(os.sep, "/")
        except ValueError:  # otra unidad en Windows
            return os.path.join(P, f)

    m = cargar_proyecto(pid)
    hallazgos = revisar(m)
    bloqueos = {}
    for x in hallazgos:
        for paso in x["bloquea"]:
            bloqueos.setdefault(paso, []).append(x["mensaje"])
    for f in SALIDAS:
        if os.path.exists(os.path.join(P, f)):
            os.remove(os.path.join(P, f))

    j = m["jurisdiccion"]
    pasos, ok = [], {}

    def paso(clave, estado, mensaje="", comando="", detalle=None):
        titulo = dict(PASOS)[clave]
        pasos.append({"clave": clave, "titulo": titulo, "estado": estado, "mensaje": mensaje,
                      "comando": comando, "detalle": detalle or []})
        ok[clave] = estado in ("ok", "con_errores", "con_avisos")

    def bloqueado(clave, requisitos=()):
        if clave in bloqueos:
            paso(clave, "bloqueado", f"Faltan {len(bloqueos[clave])} dato(s) que no se suponen.", detalle=bloqueos[clave])
            return True
        caidos = [dict(PASOS)[r] for r in requisitos if not ok.get(r)]
        if caidos:
            paso(clave, "omitido", "Necesita antes: " + ", ".join(caidos) + ".")
            return True
        return False

    def ejecutar(clave, args, salida_json=None):
        codigo, datos, texto = correr(args)
        comando = _cmd(args)
        if isinstance(datos, dict) and datos.get("error") == "DATO_FALTANTE":
            paso(clave, "falta", datos.get("mensaje", ""), comando)
            return None
        if codigo != 0 and not (isinstance(datos, dict) and "hallazgos" in datos):
            ultima = [x for x in texto.splitlines() if x.strip()][-3:]
            paso(clave, "error", "El script terminó con error: " + " | ".join(ultima), comando)
            return None
        if salida_json:
            with open(os.path.join(P, salida_json), "w", encoding="utf-8") as fh:
                json.dump(datos, fh, indent=2, ensure_ascii=False)
        return datos, comando

    # 1. Validacion estructural (el SCCR se decide contra la Icc calculada, paso 3)
    validacion = None
    if not bloqueado("validar"):
        r = ejecutar("validar", ["scripts/unifilar.py", "validar", "--json", rel("unifilar.json")])
        if r:
            datos, comando = r
            datos["hallazgos"] = [x for x in datos.get("hallazgos", [])
                                  if not x.get("hallazgo", "").startswith("SCCR ")]
            datos["errores"] = sum(1 for x in datos["hallazgos"] if x.get("severidad") == "ERROR")
            datos["advertencias"] = sum(1 for x in datos["hallazgos"] if x.get("severidad") != "ERROR")
            datos["total"] = len(datos["hallazgos"])
            validacion = dict(datos, etapa="estructura")
            paso("validar", "con_errores" if datos["errores"] else ("con_avisos" if datos["total"] else "ok"),
                 f"{datos['errores']} error(es), {datos['advertencias']} advertencia(s).", comando)
    # 2. Cortocircuito
    if not bloqueado("cortocircuito", ("validar",)):
        r = ejecutar("cortocircuito", ["scripts/ec.py", "cortocircuito", "--json", rel("unifilar.json"),
                                       "--salida", rel("cortocircuito.json")])
        if r:
            datos, comando = r
            malos = [n["id"] for n in datos.get("nodos", []) if n.get("verificacion") == "NO CUMPLE"]
            paso("cortocircuito", "con_errores" if malos else ("con_avisos" if datos.get("avisos") else "ok"),
                 (f"SCCR menor que la Icc en: {', '.join(malos)}. " if malos else "") +
                 f"{len(datos.get('nodos', []))} nodos calculados.", comando)
    # 3. SCCR contra la Icc calculada
    if not bloqueado("validar_sccr", ("validar", "cortocircuito")):
        r = ejecutar("validar_sccr", ["scripts/unifilar.py", "validar", "--json", rel("unifilar.json"),
                                      "--cortocircuito", rel("cortocircuito.json")])
        if r:
            datos, comando = r
            validacion = dict(datos, etapa="completa")
            paso("validar_sccr", "con_errores" if datos.get("errores") else ("con_avisos" if datos.get("total") else "ok"),
                 f"{datos.get('errores', 0)} error(es), {datos.get('advertencias', 0)} advertencia(s).", comando)
    if validacion:
        with open(os.path.join(P, "validacion.json"), "w", encoding="utf-8") as fh:
            json.dump(validacion, fh, indent=2, ensure_ascii=False)
    # 4. Render
    if not bloqueado("render", ("validar",)):
        r = ejecutar("render", ["scripts/unifilar.py", "render", "--json", rel("unifilar.json"),
                                "--svg", rel("unifilar.svg")])
        if r:
            paso("render", "ok", "Diagrama generado.", r[1])
    # 5. Circuitos
    si, cr = j["sitio"], j["criterios"]
    if not bloqueado("circuitos", ("validar",)):
        r = ejecutar("circuitos", [
            "scripts/ec.py", "circuito", "--archivo", rel("cargas.csv"), "--unifilar", rel("unifilar.json"),
            "--salida", rel("resultados.json"),
            "--ambiente-c", _texto(int(float(si["temperatura_ambiente_C"]))),
            "--temp-terminal", _texto(si["temperatura_terminales_C"]),
            "--temp-aislamiento", _texto(cr["temp_aislamiento_C"]),
            "--limite-dv", _texto(cr["caida_tension_derivado_pct"]),
            "--material", _texto(cr["material_conductor"]).lower() or "cobre"])
        if r:
            datos, comando = r
            alertas = sum(1 for c in datos.get("circuitos", [])
                          if c.get("alerta") or c.get("alerta_tension") or c.get("alerta_longitud"))
            paso("circuitos", "con_avisos" if alertas else "ok",
                 f"{len(datos.get('circuitos', []))} circuitos; {alertas} con alertas.", comando)
    # 6. Square D
    if not bloqueado("squared", ("cortocircuito", "circuitos")):
        r = ejecutar("squared", ["scripts/squared.py", "--unifilar", rel("unifilar.json"),
                                 "--cortocircuito", rel("cortocircuito.json"), "--resultados", rel("resultados.json"),
                                 "--reserva-pct", _texto(cr["reserva_espacios_pct"]),
                                 "--salida", rel("squared.json"), "--reporte", rel("squared.md")])
        if r:
            datos, comando = r
            avisos = sum(len(t.get("avisos", [])) for t in datos.get("tableros", []))
            paso("squared", "con_avisos" if avisos else "ok",
                 f"{len(datos.get('tableros', []))} tablero(s); {avisos} aviso(s).", comando)
    # 7. Red de tierras
    if m["tierras"]:
        if not bloqueado("tierras"):
            r = ejecutar("tierras", ["scripts/red_tierras.py", "--entrada", rel("red-de-tierras.yaml"),
                                     "--salida", rel("red-tierras.json"), "--reporte", rel("red-tierras.md")])
            if r:
                datos, comando = r
                paso("tierras", "ok" if datos.get("cumple") else "con_errores",
                     "La malla cumple." if datos.get("cumple") else "La malla NO cumple: revisa la sugerencia.", comando)
    else:
        paso("tierras", "no_aplica", "Sin subestación propia: no se diseña malla.")
    # 8. Memoria: no se emite con errores del unifilar ni con SCCR insuficiente
    errores_bloq = []
    if validacion and validacion.get("errores"):
        errores_bloq.append(f"{validacion['errores']} error(es) en el unifilar")
    if any(p["clave"] == "cortocircuito" and p["estado"] == "con_errores" for p in pasos):
        errores_bloq.append("SCCR menor que la Icc")
    if not bloqueado("memoria", ("circuitos",)):
        if errores_bloq:
            paso("memoria", "bloqueado", "No se genera: " + "; ".join(errores_bloq) +
                 ". Un ERROR bloquea la emisión.")
        else:
            args = ["scripts/memoria.py", "--resultados", rel("resultados.json"),
                    "--proyecto", rel("proyecto.yaml"), "--jurisdiccion", rel("jurisdiccion.yaml")]
            if ok.get("cortocircuito"):
                args += ["--cortocircuito", rel("cortocircuito.json")]
            if ok.get("squared"):
                args += ["--squared", rel("squared.json")]
            if ok.get("tierras"):
                args += ["--tierras", rel("red-tierras.json")]
            args += ["--salida", rel("memoria-de-calculo.md")]
            r = ejecutar("memoria", args)
            if r:
                with open(os.path.join(P, "memoria-de-calculo.md"), encoding="utf-8") as fh:
                    pendientes = len(RE_PENDIENTE.findall(fh.read()))
                faltan = [dict(PASOS)[c] for c in ("cortocircuito", "squared") if not ok.get(c)]
                if m["tierras"] and not ok.get("tierras"):
                    faltan.append(dict(PASOS)["tierras"])
                paso("memoria", "con_avisos" if pendientes or faltan else "ok",
                     f"Borrador generado con {pendientes} marcador(es) por completar." +
                     (f" Sin: {', '.join(faltan)}." if faltan else ""), r[1])

    bitacora = {"fecha": _ahora(), "version_entradas": version_de(P), "pasos": pasos,
                "hallazgos_previos": hallazgos,
                "comandos": [p["comando"] for p in pasos if p["comando"]]}
    with open(os.path.join(P, "bitacora.json"), "w", encoding="utf-8") as fh:
        json.dump(bitacora, fh, indent=2, ensure_ascii=False)
    return bitacora


def leer_salidas(pid):
    P = ruta_proyecto(pid)
    out = {}
    for clave, f in (("bitacora", "bitacora.json"), ("validacion", "validacion.json"),
                     ("cortocircuito", "cortocircuito.json"), ("resultados", "resultados.json"),
                     ("squared", "squared.json"), ("tierras", "red-tierras.json")):
        ruta = os.path.join(P, f)
        if os.path.exists(ruta):
            try:
                with open(ruta, encoding="utf-8") as fh:
                    out[clave] = json.load(fh)
            except ValueError:
                pass
    ruta = os.path.join(P, "memoria-de-calculo.md")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as fh:
            out["memoria"] = fh.read()
    out["svg"] = os.path.exists(os.path.join(P, "unifilar.svg"))
    if out.get("bitacora"):
        out["desactualizado"] = out["bitacora"].get("version_entradas") != version_de(P)
    return out


# ------------------------------------------------------------ servidor HTTP

def candado(pid):
    with CANDADO_GLOBAL:
        return CANDADOS.setdefault(pid, threading.Lock())


class Manejador(BaseHTTPRequestHandler):
    server_version = "AgenteElectrico/1.0"

    def log_message(self, fmt, *args):
        if "--verbose" in sys.argv:
            super().log_message(fmt, *args)

    # --- respuestas
    def _enviar(self, codigo, cuerpo, tipo="application/json; charset=utf-8", extra=None):
        if isinstance(cuerpo, (dict, list)):
            cuerpo = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        elif isinstance(cuerpo, str):
            cuerpo = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _error(self, codigo, mensaje):
        self._enviar(codigo, {"error": mensaje})

    def _host_valido(self):
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _json(self):
        largo = int(self.headers.get("Content-Length") or 0)
        if largo > 20 * 1024 * 1024:
            raise ValueError("Solicitud demasiado grande.")
        return json.loads(self.rfile.read(largo).decode("utf-8") or "{}")

    # --- GET
    def do_GET(self):
        if not self._host_valido():
            return self._error(403, "Host no permitido.")
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            if url.path in ESTATICOS:
                archivo, tipo = ESTATICOS[url.path]
                with open(os.path.join(WEB, archivo), "rb") as fh:
                    return self._enviar(200, fh.read(), tipo)
            if url.path == "/api/inicio":
                return self._enviar(200, {"proyectos": listar_proyectos(), "catalogos": catalogos(),
                                          "raiz": RAIZ, "tierras_plantilla": plantilla_tierras()})
            if url.path == "/api/proyecto":
                pid = q.get("id", "")
                P = ruta_proyecto(pid)
                m = cargar_proyecto(pid)
                return self._enviar(200, {"id": pid, "modelo": m, "version": version_de(P),
                                          "hallazgos": revisar(m), "salidas": leer_salidas(pid),
                                          "carpeta": P})
            if url.path == "/api/archivo":
                pid, nombre = q.get("id", ""), q.get("nombre", "")
                if nombre not in SALIDAS + ENTRADAS:
                    return self._error(404, "Archivo no disponible.")
                ruta = os.path.join(ruta_proyecto(pid), nombre)
                if not os.path.exists(ruta):
                    return self._error(404, "Todavía no existe. Corre el cálculo.")
                with open(ruta, "rb") as fh:
                    datos = fh.read()
                tipo = TIPO_ARCHIVO.get(os.path.splitext(nombre)[1], "text/plain; charset=utf-8")
                extra = {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"}
                if q.get("descargar"):
                    extra["Content-Disposition"] = f'attachment; filename="{pid}-{nombre}"'
                return self._enviar(200, datos, tipo, extra)
            return self._error(404, "No encontrado.")
        except FileNotFoundError as exc:
            return self._error(404, str(exc))
        except ValueError as exc:
            return self._error(400, str(exc))

    # --- POST
    def do_POST(self):
        if not self._host_valido():
            return self._error(403, "Host no permitido.")
        if self.headers.get("X-Agente-Electrico") != "1":
            return self._error(403, "Solicitud no permitida.")
        url = urlparse(self.path)
        try:
            cuerpo = self._json()
            if url.path == "/api/revisar":
                return self._enviar(200, {"hallazgos": revisar(cuerpo.get("modelo") or {})})
            if url.path == "/api/nuevo":
                nombre = _texto(cuerpo.get("nombre"))
                if not nombre:
                    return self._error(400, "Escribe el nombre del proyecto.")
                pid = crear_proyecto(nombre, "demo" if cuerpo.get("origen") == "demo" else "vacio")
                return self._enviar(200, {"id": pid})
            pid = _texto(cuerpo.get("id"))
            P = ruta_proyecto(pid)
            if not os.path.isdir(P):
                return self._error(404, f"No existe el proyecto {pid}.")
            if url.path == "/api/guardar":
                with candado(pid):
                    if cuerpo.get("version") and cuerpo["version"] != version_de(P) and not cuerpo.get("forzar"):
                        return self._enviar(409, {"error": "Los archivos del proyecto cambiaron fuera de la interfaz "
                                                           "(por ejemplo, los editó Claude). Recarga para ver la versión actual.",
                                                  "version": version_de(P)})
                    version = guardar_proyecto(pid, cuerpo.get("modelo") or {})
                    return self._enviar(200, {"version": version, "hallazgos": revisar(cuerpo.get("modelo") or {}),
                                              "guardado": _ahora()})
            if url.path == "/api/calcular":
                with candado(pid):
                    bitacora = calcular(pid)
                    return self._enviar(200, {"bitacora": bitacora, "salidas": leer_salidas(pid),
                                              "version": version_de(P)})
            if url.path == "/api/abrir":
                if os.name == "nt":
                    os.startfile(P)  # noqa: S606 (carpeta local del proyecto)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", P])
                else:
                    subprocess.Popen(["xdg-open", P])
                return self._enviar(200, {"ok": True})
            return self._error(404, "No encontrado.")
        except FileNotFoundError as exc:
            return self._error(404, str(exc))
        except (ValueError, KeyError) as exc:
            return self._error(400, f"Datos no válidos: {exc}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Interfaz local del agente electrico")
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument("--sin-navegador", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    os.makedirs(PROYECTOS, exist_ok=True)
    servidor = None
    for puerto in range(a.puerto, a.puerto + 20):
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Manejador)
            break
        except OSError:
            continue
    if servidor is None:
        sys.exit(f"No hay puertos libres entre {a.puerto} y {a.puerto + 19}.")
    url = f"http://127.0.0.1:{servidor.server_address[1]}/"
    print(f"Interfaz del agente electrico en {url}", flush=True)
    print(f"Proyectos en {PROYECTOS}", flush=True)
    print("Ctrl+C para salir.", flush=True)
    if not a.sin_navegador:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nInterfaz cerrada.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
