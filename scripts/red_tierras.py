#!/usr/bin/env python3
"""
red_tierras.py - Diseño de la red de tierras (malla) de una subestacion con el
metodo de IEEE Std 80 para suelo uniforme.

La entrada va separada del resto del proyecto (config/red-de-tierras.yaml):
resistividad del terreno, potencia de cortocircuito del suministrador,
geometria de la malla, varillas, capa superficial y tiempos de falla.

Uso:
  python3 scripts/red_tierras.py --entrada config/red-de-tierras.yaml \
      --salida red-tierras.json --reporte red-tierras.md

Regla de oro: los datos marcados OBLIGATORIO no se suponen. Si faltan, el script
devuelve DATO_FALTANTE y el agente pregunta.
"""

import argparse
import json
import math
import os
import sys
from datetime import date

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "datos")


class DatoFaltante(Exception):
    """Dato obligatorio ausente: preguntar al usuario, no suponerlo."""


def _cargar(nombre):
    ruta = os.path.join(DATOS, nombre)
    if not os.path.exists(ruta):
        raise DatoFaltante(f"Falta el archivo de datos {ruta}.")
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


IEEE = _cargar("ieee80.json")
PRO = _cargar("propiedades_conductores.json")


# ------------------------------------------------------------ lectura YAML

def _escalar(v):
    v = v.strip()
    if v in ("", "null", "~", "None"):
        return None
    if v.lower() in ("true", "si", "sí", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    for tipo in (int, float):
        try:
            return tipo(v)
        except ValueError:
            pass
    return v


def _sin_comentario(linea):
    salida, comilla = [], None
    for ch in linea:
        if comilla:
            if ch == comilla:
                comilla = None
        elif ch in "\"'":
            comilla = ch
        elif ch == "#":
            break
        salida.append(ch)
    return "".join(salida).rstrip()


def leer_yaml(ruta):
    """YAML minimo: secciones anidadas por sangria y valores escalares (sin listas)."""
    raiz, pila = {}, [(-1, {})]
    pila[0] = (-1, raiz)
    with open(ruta, encoding="utf-8") as fh:
        for num, linea in enumerate(fh, 1):
            limpia = _sin_comentario(linea.rstrip("\n"))
            if not limpia.strip():
                continue
            if ":" not in limpia:
                raise DatoFaltante(f"{ruta}:{num}: se esperaba 'clave: valor'.")
            sangria = len(limpia) - len(limpia.lstrip())
            clave, _, valor = limpia.strip().partition(":")
            while sangria <= pila[-1][0]:
                pila.pop()
            padre = pila[-1][1]
            if valor.strip() == "":
                padre[clave.strip()] = {}
                pila.append((sangria, padre[clave.strip()]))
            else:
                padre[clave.strip()] = _escalar(valor)
    return raiz


def obtener(d, ruta, defecto=None):
    cur = d
    for k in ruta.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return defecto
        cur = cur[k]
    return defecto if cur in (None, "", {}) else cur


def requerido(d, ruta):
    v = obtener(d, ruta)
    if v is None:
        raise DatoFaltante(f"Falta '{ruta}' en la entrada de la red de tierras. Pedirlo; no suponerlo.")
    return v


# ------------------------------------------------------------ calculo

def area_de_calibre(calibre):
    c = str(calibre).strip().upper().replace("AWG", "").replace("KCMIL", "").strip()
    c = {"0000": "4/0", "000": "3/0", "00": "2/0", "0": "1/0"}.get(c, c)
    eq = PRO["equivalencia_awg_mm2"]
    if c not in eq:
        raise DatoFaltante(f"Calibre '{calibre}' no esta en la tabla de equivalencias AWG-mm2.")
    return c, eq[c]


def calibre_minimo(area_mm2):
    for c in PRO["orden_calibres"]:
        if PRO["equivalencia_awg_mm2"][c] >= area_mm2:
            return c
    return None


def factor_decremento(x_r, t, frecuencia):
    if not x_r:
        return 1.0
    ta = x_r / (2 * math.pi * frecuencia)
    return math.sqrt(1 + ta / t * (1 - math.exp(-2 * t / ta)))


def evaluar_malla(rho, ig, g):
    """g: Lx, Ly, D, h, d, nr, Lr, perimetro. Ecuaciones de IEEE Std 80 para mallas rectangulares."""
    lx, ly, h, d = g["Lx"], g["Ly"], g["h"], g["d"]
    nx = math.ceil(ly / g["D"] - 1e-9) + 1          # conductores paralelos al largo
    ny = math.ceil(lx / g["D"] - 1e-9) + 1          # conductores paralelos al ancho
    dm = (ly / (nx - 1) + lx / (ny - 1)) / 2        # separacion efectiva
    lc = nx * lx + ny * ly
    lr = g["nr"] * g["Lr"]
    lt = lc + lr
    area = lx * ly
    lp = 2 * (lx + ly)
    diag = math.hypot(lx, ly)
    n = (2 * lc / lp) * math.sqrt(lp / (4 * math.sqrt(area)))   # na * nb; nc = nd = 1
    ki = 0.644 + 0.148 * n
    kh = math.sqrt(1 + h / 1.0)
    perimetro = g["nr"] > 0 and g["perimetro"]
    kii = 1.0 if perimetro else 1 / (2 * n) ** (2 / n)
    km = (1 / (2 * math.pi)) * (
        math.log(dm ** 2 / (16 * h * d) + (dm + 2 * h) ** 2 / (8 * dm * d) - h / (4 * d))
        + kii / kh * math.log(8 / (math.pi * (2 * n - 1))))
    lm = lc + (1.55 + 1.22 * g["Lr"] / diag) * lr if perimetro else lc + lr
    ks = (1 / math.pi) * (1 / (2 * h) + 1 / (dm + h) + (1 / dm) * (1 - 0.5 ** (n - 2)))
    ls = 0.75 * lc + 0.85 * lr
    rg = rho * (1 / lt + 1 / math.sqrt(20 * area) * (1 + 1 / (1 + h * math.sqrt(20 / area))))
    return {
        "largo_m": lx, "ancho_m": ly, "separacion_m": round(dm, 2),
        "conductores_largo": nx, "conductores_ancho": ny,
        "varillas": g["nr"], "longitud_varilla_m": g["Lr"], "varillas_en_perimetro": bool(perimetro),
        "LC_m": round(lc, 1), "LR_m": round(lr, 1), "LT_m": round(lt, 1), "area_m2": round(area, 1),
        "n": round(n, 3), "Ki": round(ki, 3), "Kh": round(kh, 3), "Kii": round(kii, 3),
        "Km": round(km, 4), "Ks": round(ks, 4), "LM_m": round(lm, 1), "LS_m": round(ls, 1),
        "Rg_ohm": round(rg, 3), "GPR_V": round(ig * rg, 0),
        "Em_V": round(rho * km * ki * ig / lm, 0), "Es_V": round(rho * ks * ki * ig / ls, 0),
    }


def cumple_tensiones(r, tol):
    if r["GPR_V"] <= tol["E_toque_V"]:
        return True
    return r["Em_V"] <= tol["E_toque_V"] and r["Es_V"] <= tol["E_paso_V"]


def fuera_de_validez(r, g):
    lim = IEEE["limites_validez"]
    avisos = []
    if r["n"] > lim["n_max"]:
        avisos.append(f"n = {r['n']} > {lim['n_max']}")
    if not lim["h_min_m"] <= g["h"] <= lim["h_max_m"]:
        avisos.append(f"h = {g['h']} m fuera de {lim['h_min_m']}-{lim['h_max_m']} m")
    if g["d"] >= lim["d_max_sobre_h"] * g["h"]:
        avisos.append(f"d = {g['d']:.4f} m no es menor que {lim['d_max_sobre_h']} h")
    if r["separacion_m"] < lim["D_min_m"]:
        avisos.append(f"D = {r['separacion_m']} m < {lim['D_min_m']} m")
    return avisos


def disenar(e):
    avisos, criterios = [], []
    rho = float(requerido(e, "terreno.resistividad_ohm_m"))
    kv = float(requerido(e, "suministrador.tension_kV"))
    mva3 = float(requerido(e, "suministrador.mva_cc_3f"))
    mva1 = obtener(e, "suministrador.mva_cc_1f")
    x_r = obtener(e, "suministrador.x_r")
    frec = float(obtener(e, "suministrador.frecuencia_Hz", 60))
    ts = float(obtener(e, "falla.tiempo_choque_s", 0.5))
    tc = float(obtener(e, "falla.tiempo_conductor_s", ts))
    sf = float(obtener(e, "falla.factor_division_Sf", 1.0))

    # 1. corriente de falla
    i3 = mva3 * 1000 / (math.sqrt(3) * kv)
    if mva1:
        i_falla, origen = float(mva1) * 1000 / (math.sqrt(3) * kv), "monofasica del suministrador"
    else:
        i_falla, origen = i3, "trifasica (falta la monofasica)"
        avisos.append("Sin mva_cc_1f: se usa la corriente trifasica como corriente de falla a tierra. "
                      "Pedir la potencia de cortocircuito monofasica al suministrador.")
    if not x_r:
        avisos.append("Sin X/R del suministrador: factor de decremento Df = 1 (subestima la corriente "
                      "asimetrica). Pedir el dato.")
    df_s = factor_decremento(x_r, ts, frec)
    df_c = factor_decremento(x_r, tc, frec)
    ig = df_s * sf * i_falla
    i_cond = df_c * i_falla
    if sf < 1:
        criterios.append(f"Sf = {sf}: requiere justificacion (estudio de division de corriente).")

    # 2. conductor
    clave = obtener(e, "malla.material", "cobre_duro")
    mat = IEEE["materiales"].get(clave)
    if mat is None:
        raise DatoFaltante(f"Material '{clave}' no esta en datos/ieee80.json. Opciones: "
                           f"{', '.join(IEEE['materiales'])}.")
    tm = float(obtener(e, "malla.temperatura_maxima_C", mat["Tm_fusion_C"]))
    ta = float(obtener(e, "malla.temperatura_ambiente_C", 40))
    area_min = (i_cond / 1000) / math.sqrt(
        (mat["TCAP_J_cm3_C"] * 1e-4 / (tc * mat["alfa_r_20C"] * mat["rho_r_20C_microohm_cm"]))
        * math.log((mat["K0_C"] + tm) / (mat["K0_C"] + ta)))
    calibre, area = area_de_calibre(obtener(e, "malla.calibre", "4/0"))
    diametro = math.sqrt(4 * area / math.pi) / 1000

    # 3. tensiones tolerables
    rho_s = obtener(e, "capa_superficial.resistividad_ohm_m")
    hs = obtener(e, "capa_superficial.espesor_m")
    if rho_s and hs:
        cs = 1 - 0.09 * (1 - rho / float(rho_s)) / (2 * float(hs) + 0.09)
        rho_s = float(rho_s)
    else:
        cs, rho_s = 1.0, rho
    peso = str(int(obtener(e, "persona.peso_kg", 50)))
    if peso not in IEEE["corriente_cuerpo_k"]:
        raise DatoFaltante("persona.peso_kg debe ser 50 o 70.")
    k = IEEE["corriente_cuerpo_k"][peso]
    tol = {
        "Cs": round(cs, 4), "rho_s_ohm_m": rho_s, "peso_kg": int(peso), "ts_s": ts,
        "E_toque_V": round((1000 + 1.5 * cs * rho_s) * k / math.sqrt(ts), 0),
        "E_paso_V": round((1000 + 6 * cs * rho_s) * k / math.sqrt(ts), 0),
    }

    # 4. malla
    geo = {
        "Lx": float(requerido(e, "malla.largo_m")), "Ly": float(requerido(e, "malla.ancho_m")),
        "D": float(requerido(e, "malla.separacion_m")), "h": float(obtener(e, "malla.profundidad_m", 0.6)),
        "d": diametro, "nr": int(obtener(e, "varillas.cantidad", 0) or 0),
        "Lr": float(obtener(e, "varillas.longitud_m", 3.05)),
        "perimetro": bool(obtener(e, "varillas.en_perimetro", True)),
    }
    malla = evaluar_malla(rho, ig, geo)
    for a in fuera_de_validez(malla, geo):
        avisos.append(f"Fuera del rango de validez de IEEE 80 para Em y Es: {a}.")
    r_obj = obtener(e, "resistencia_objetivo_ohm")

    verif = [
        {"criterio": "Sección del conductor", "calculado": f"{area} mm² ({calibre})",
         "limite": f">= {area_min:.1f} mm²", "resultado": "CUMPLE" if area >= area_min else "NO CUMPLE"},
        {"criterio": "Tensión de malla Em contra toque tolerable", "calculado": f"{malla['Em_V']:.0f} V",
         "limite": f"<= {tol['E_toque_V']:.0f} V",
         "resultado": "CUMPLE" if malla["Em_V"] <= tol["E_toque_V"] else "NO CUMPLE"},
        {"criterio": "Tensión de paso Es contra paso tolerable", "calculado": f"{malla['Es_V']:.0f} V",
         "limite": f"<= {tol['E_paso_V']:.0f} V",
         "resultado": "CUMPLE" if malla["Es_V"] <= tol["E_paso_V"] else "NO CUMPLE"},
        {"criterio": "Elevación de potencial GPR contra toque tolerable", "calculado": f"{malla['GPR_V']:.0f} V",
         "limite": f"<= {tol['E_toque_V']:.0f} V",
         "resultado": "CUMPLE" if malla["GPR_V"] <= tol["E_toque_V"] else "NO CUMPLE (revisar Em y Es)"},
    ]
    if r_obj:
        verif.append({"criterio": "Resistencia de la malla", "calculado": f"{malla['Rg_ohm']} ohm",
                      "limite": f"<= {r_obj} ohm",
                      "resultado": "CUMPLE" if malla["Rg_ohm"] <= float(r_obj) else "NO CUMPLE"})
    cumple = (area >= area_min and cumple_tensiones(malla, tol)
              and (not r_obj or malla["Rg_ohm"] <= float(r_obj)))

    # 5. si no cumple, buscar separacion y varillas que cumplan
    sugerencia, recomendaciones = None, []
    if not cumple_tensiones(malla, tol):
        d_min = IEEE["limites_validez"]["D_min_m"]
        pasos = [geo["D"] - 0.5 * i for i in range(int((geo["D"] - d_min) / 0.5) + 1)]
        nx, ny = malla["conductores_largo"], malla["conductores_ancho"]
        opciones_varillas = [(geo["nr"], geo["perimetro"]), (2 * (nx + ny) - 4, True)]
        for nr, per in opciones_varillas:
            for dd in pasos:
                g2 = dict(geo, D=dd, nr=nr, perimetro=per)
                r2 = evaluar_malla(rho, ig, g2)
                if cumple_tensiones(r2, tol) and (not r_obj or r2["Rg_ohm"] <= float(r_obj)):
                    sugerencia = r2
                    break
            if sugerencia:
                break
        if not sugerencia:
            recomendaciones = [
                "Ampliar el area de la malla o unirla con otras mallas y con el acero de la cimentacion.",
                "Usar una capa superficial de mayor resistividad o mayor espesor.",
                "Pedir un estudio de division de corriente para justificar un Sf menor que 1.",
                "Reducir el tiempo de liberacion de la falla (ts) con la proteccion del suministrador.",
                "Controlar los gradientes en la periferia con conductores adicionales y varillas.",
            ]
    if area < area_min:
        recomendaciones.insert(0, f"Subir el conductor a {calibre_minimo(area_min)} o mayor.")

    return {
        "norma": "IEEE Std 80-2000, suelo uniforme",
        "proyecto": obtener(e, "proyecto", ""),
        "subestacion": obtener(e, "subestacion", ""),
        "entradas": {
            "resistividad_ohm_m": rho, "fuente_resistividad": obtener(e, "terreno.fuente", ""),
            "tension_kV": kv, "mva_cc_3f": mva3, "mva_cc_1f": mva1, "x_r": x_r, "frecuencia_Hz": frec,
            "fuente_suministrador": obtener(e, "suministrador.fuente", ""),
            "tiempo_choque_s": ts, "tiempo_conductor_s": tc, "factor_division_Sf": sf,
            "material": clave, "temperatura_ambiente_C": ta, "temperatura_maxima_C": tm,
            "calibre": calibre, "profundidad_m": geo["h"], "resistencia_objetivo_ohm": r_obj,
        },
        "corriente_falla": {
            "icc_3f_A": round(i3, 0), "corriente_falla_tierra_A": round(i_falla, 0), "origen": origen,
            "Df_ts": round(df_s, 4), "Df_tc": round(df_c, 4), "Sf": sf,
            "IG_A": round(ig, 0), "I_conductor_A": round(i_cond, 0),
        },
        "conductor": {
            "material": mat["descripcion"], "Tm_C": tm, "Ta_C": ta, "tc_s": tc,
            "area_minima_mm2": round(area_min, 1), "calibre_minimo": calibre_minimo(area_min),
            "calibre_elegido": calibre, "area_elegida_mm2": area, "diametro_m": round(diametro, 4),
        },
        "tolerables": tol,
        "malla": malla,
        "verificacion": verif,
        "cumple": cumple,
        "sugerencia": sugerencia,
        "recomendaciones": recomendaciones,
        "criterios": criterios,
        "avisos": avisos,
    }


# ------------------------------------------------------------ reporte

def _tabla(encabezados, filas):
    out = ["| " + " | ".join(encabezados) + " |", "|" + "|".join(["---"] * len(encabezados)) + "|"]
    out += ["| " + " | ".join(str(x) for x in f) + " |" for f in filas]
    return "\n".join(out)


def reporte(r):
    e, cf, co, tol, m = r["entradas"], r["corriente_falla"], r["conductor"], r["tolerables"], r["malla"]
    L = [
        "# Memoria de cálculo — Red de tierras\n",
        f"**Proyecto:** {r['proyecto'] or '[COMPLETAR]'}  ",
        f"**Subestación:** {r['subestacion'] or '[COMPLETAR]'}  ",
        f"**Método:** {r['norma']}  ",
        f"**Fecha:** {date.today().isoformat()}\n",
        "> **Documento preliminar.** Requiere revisión, validación y firma de un responsable técnico "
        "con licencia vigente. La resistencia de la malla se mide en campo (IEEE Std 81) antes de energizar.\n",
        "## 1. Datos de entrada\n",
        _tabla(["Parámetro", "Valor", "Tipo", "Origen"], [
            ["Resistividad del terreno", f"{e['resistividad_ohm_m']} Ω·m", "Dato de sitio",
             e["fuente_resistividad"] or "**Confirmar medición**"],
            ["Tensión en el punto de entrega", f"{e['tension_kV']} kV", "Dato del suministrador",
             e["fuente_suministrador"] or "**Confirmar**"],
            ["Potencia de cortocircuito trifásica", f"{e['mva_cc_3f']} MVA", "Dato del suministrador",
             e["fuente_suministrador"] or "**Confirmar**"],
            ["Potencia de cortocircuito monofásica",
             f"{e['mva_cc_1f']} MVA" if e["mva_cc_1f"] else "[FALTA]", "Dato del suministrador",
             e["fuente_suministrador"] or "**Confirmar**"],
            ["Relación X/R", e["x_r"] or "[FALTA]", "Dato del suministrador", ""],
            ["Tiempo de choque ts", f"{e['tiempo_choque_s']} s", "[CRITERIO]", "Protección"],
            ["Tiempo para el conductor tc", f"{e['tiempo_conductor_s']} s", "[CRITERIO]", "Protección de respaldo"],
            ["Factor de división Sf", e["factor_division_Sf"], "[CRITERIO]", "1.0 = conservador"],
            ["Conductor", f"{e['calibre']} {co['material']}", "[CRITERIO]", "Proyecto"],
            ["Profundidad de la malla", f"{e['profundidad_m']} m", "[CRITERIO]", "Proyecto"],
            ["Capa superficial", f"{tol['rho_s_ohm_m']} Ω·m" if tol["Cs"] < 1 else "Sin capa", "[CRITERIO]", ""],
            ["Peso corporal", f"{tol['peso_kg']} kg", "[CRITERIO]", "IEEE Std 80"],
        ]),
        "",
        "## 2. Corriente de falla\n",
        "Icc = MVA × 1000 / (√3 × kV). Corriente de la malla: IG = Df × Sf × 3I0, con "
        "Df = √(1 + (Ta/tf)(1 − e^(−2tf/Ta))) y Ta = X/(ωR).\n",
        _tabla(["Concepto", "Valor"], [
            ["Icc trifásica", f"{cf['icc_3f_A']:,.0f} A"],
            [f"Corriente de falla a tierra 3I0 ({cf['origen']})", f"{cf['corriente_falla_tierra_A']:,.0f} A"],
            ["Df (ts)", cf["Df_ts"]],
            ["Sf", cf["Sf"]],
            ["Corriente de la malla IG", f"{cf['IG_A']:,.0f} A"],
            ["Corriente para el conductor (Df × 3I0)", f"{cf['I_conductor_A']:,.0f} A"],
        ]),
        "",
        "## 3. Conductor de la malla\n",
        "A = I / √[(TCAP × 10⁻⁴ / (tc αr ρr)) × ln((K0 + Tm)/(K0 + Ta))], con I en kA y A en mm² "
        "(IEEE Std 80, constantes de la Tabla 1).\n",
        _tabla(["Concepto", "Valor"], [
            ["Material", co["material"]],
            ["Tm / Ta / tc", f"{co['Tm_C']} °C / {co['Ta_C']} °C / {co['tc_s']} s"],
            ["Sección mínima", f"{co['area_minima_mm2']} mm² ({co['calibre_minimo']})"],
            ["Conductor elegido", f"{co['calibre_elegido']} ({co['area_elegida_mm2']} mm²)"],
        ]),
        "",
        "## 4. Tensiones tolerables\n",
        f"Cs = 1 − 0.09 (1 − ρ/ρs) / (2hs + 0.09) = {tol['Cs']}. "
        f"Para {tol['peso_kg']} kg y ts = {tol['ts_s']} s:\n",
        _tabla(["Tensión", "Tolerable"], [
            ["Toque: (1000 + 1.5 Cs ρs) k / √ts", f"{tol['E_toque_V']:,.0f} V"],
            ["Paso: (1000 + 6 Cs ρs) k / √ts", f"{tol['E_paso_V']:,.0f} V"],
        ]),
        "",
        "## 5. Malla, resistencia y tensiones calculadas\n",
        _tabla(["Concepto", "Valor"], [
            ["Dimensiones", f"{m['largo_m']} × {m['ancho_m']} m ({m['area_m2']} m²)"],
            ["Conductores", f"{m['conductores_largo']} a lo largo × {m['conductores_ancho']} a lo ancho, "
                            f"separación {m['separacion_m']} m"],
            ["Varillas", f"{m['varillas']} de {m['longitud_varilla_m']} m"
                         + (" en el perímetro" if m["varillas_en_perimetro"] else "")],
            ["LC / LR / LT", f"{m['LC_m']} / {m['LR_m']} / {m['LT_m']} m"],
            ["n / Ki / Km / Ks", f"{m['n']} / {m['Ki']} / {m['Km']} / {m['Ks']}"],
            ["Resistencia Rg (Sverak)", f"{m['Rg_ohm']} Ω"],
            ["GPR = IG × Rg", f"{m['GPR_V']:,.0f} V"],
            ["Tensión de malla Em = ρ Km Ki IG / LM", f"{m['Em_V']:,.0f} V"],
            ["Tensión de paso Es = ρ Ks Ki IG / LS", f"{m['Es_V']:,.0f} V"],
        ]),
        "",
        "## 6. Verificación\n",
        _tabla(["Criterio", "Calculado", "Límite", "Resultado"],
               [[v["criterio"], v["calculado"], v["limite"], v["resultado"]] for v in r["verificacion"]]),
        "",
        f"**Resultado:** {'CUMPLE' if r['cumple'] else 'NO CUMPLE'}.\n",
    ]
    if r["sugerencia"]:
        s = r["sugerencia"]
        L += ["## 7. Configuración que cumple\n",
              f"Con separación de {s['separacion_m']} m ({s['conductores_largo']} × {s['conductores_ancho']} "
              f"conductores) y {s['varillas']} varillas de {s['longitud_varilla_m']} m"
              f"{' en el perímetro' if s['varillas_en_perimetro'] else ''}: Rg = {s['Rg_ohm']} Ω, "
              f"Em = {s['Em_V']:,.0f} V ≤ {tol['E_toque_V']:,.0f} V y Es = {s['Es_V']:,.0f} V ≤ "
              f"{tol['E_paso_V']:,.0f} V.\n"]
    if r["recomendaciones"]:
        L += ["## 7. Recomendaciones\n"] + [f"- {x}" for x in r["recomendaciones"]] + [""]
    if r["avisos"] or r["criterios"]:
        L += ["## 8. Supuestos y avisos\n"] + [f"- {x}" for x in r["criterios"] + r["avisos"]] + [""]
    L += ["## 9. Límites del cálculo\n",
          "- Modelo de suelo uniforme; con resistividad variable en profundidad se requiere un modelo de dos capas.",
          "- No evalúa potenciales transferidos (tuberías, rieles, cercas) ni la zona fuera del perímetro de la malla.",
          "- La resistencia real se mide en campo antes de energizar y se registra en el dossier."]
    return "\n".join(L) + "\n"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Red de tierras de subestacion (IEEE Std 80)")
    p.add_argument("--entrada", required=True, help="config/red-de-tierras.yaml")
    p.add_argument("--salida", help="Resultado en JSON")
    p.add_argument("--reporte", help="Memoria de la red de tierras en Markdown")
    a = p.parse_args()
    try:
        r = disenar(leer_yaml(a.entrada))
    except DatoFaltante as exc:
        print(json.dumps({"error": "DATO_FALTANTE", "mensaje": str(exc),
                          "accion": "PREGUNTAR AL USUARIO. No estimar el valor."},
                         indent=2, ensure_ascii=False))
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
