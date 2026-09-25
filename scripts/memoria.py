#!/usr/bin/env python3
"""
memoria.py - Arma el esqueleto de la memoria de calculo desde los resultados
de ec.py. Las secciones de criterio, descripcion y conclusiones las completa
el ingeniero: no se autogeneran porque requieren juicio.

Uso:
  python3 scripts/memoria.py --resultados resultados.json --salida memoria.md
  python3 scripts/memoria.py --resultados resultados.json --proyecto config/proyecto.yaml \
      --jurisdiccion config/jurisdiccion.yaml --cortocircuito cortocircuito.json \
      --squared squared.json --tierras red-tierras.json --salida memoria.md
"""

import argparse
import json
import os
import sys
from datetime import date


def _sin_comentario(texto):
    """Quita un comentario '#' que este fuera de comillas y al inicio o tras un espacio."""
    comilla = None
    for i, ch in enumerate(texto):
        if comilla:
            if ch == comilla:
                comilla = None
        elif ch in "\"'":
            comilla = ch
        elif ch == "#" and (i == 0 or texto[i - 1] in " \t"):
            return texto[:i]
    return texto


def _valor(crudo):
    v = crudo.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return "" if v in ("null", "~", "[]", "None") else v


def yaml_simple(ruta):
    """Lector minimo de YAML: clave: valor, una seccion de un nivel y listas con guion
    (sin dependencias externas)."""
    d = {}
    if not ruta or not os.path.exists(ruta):
        return d
    seccion = None
    with open(ruta, encoding="utf-8-sig") as fh:
        for linea in fh:
            linea = _sin_comentario(linea.rstrip("\r\n"))
            if not linea.strip():
                continue
            sangria = len(linea) - len(linea.lstrip())
            limpia = linea.strip()
            if limpia.startswith("- ") or limpia == "-":
                if seccion is not None:
                    if not isinstance(d[seccion], list):
                        d[seccion] = []
                    elemento = _valor(limpia[1:])
                    if elemento:
                        d[seccion].append(elemento)
                continue
            if ":" not in limpia:
                continue
            k, _, v = limpia.partition(":")
            k, v = k.strip(), _valor(v)
            if sangria == 0:
                if v or _sin_comentario(linea.partition(":")[2]).strip():
                    d[k] = v
                    seccion = None
                else:
                    seccion = k
                    d[k] = {}
            elif seccion is not None and isinstance(d[seccion], dict):
                d[seccion][k] = v
    return d


def _lista(v):
    """Lista de textos a partir de una lista YAML o de un texto con renglones."""
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    if isinstance(v, dict):
        return [str(k) for k in v if str(k).strip()]
    return [x.strip() for x in str(v or "").splitlines() if x.strip()]


def leer_json(ruta):
    if not ruta:
        return {}
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)


def tabla(encabezados, filas):
    out = ["| " + " | ".join(encabezados) + " |",
           "|" + "|".join(["---"] * len(encabezados)) + "|"]
    for f in filas:
        out.append("| " + " | ".join(str(x).replace("|", "\\|") for x in f) + " |")
    return "\n".join(out)


CONEXION = {1: "F-N", 2: "F-F", 3: "3F"}


def construir(res, proy, jur, cc=None, sq=None, rt=None):
    cc, sq, rt = cc or {}, sq or {}, rt or {}
    j = jur.get("jurisdiccion", "")
    bloque = jur.get(j, {}) if isinstance(jur.get(j), dict) else {}
    crit = jur.get("criterios", {})
    sitio = jur.get("sitio", {})
    circ = res.get("circuitos", [])
    bal = res.get("balanceo", {})
    equipo = {i["circuito"]: i for t in sq.get("tableros", []) for i in t.get("interruptores", [])}

    L = []
    A = L.append

    A(f"# Memoria de cálculo eléctrico\n")
    A(f"**Proyecto:** {proy.get('proyecto') or '[COMPLETAR]'}  ")
    A(f"**Cliente:** {proy.get('cliente') or '[COMPLETAR]'}  ")
    A(f"**Ubicación:** {proy.get('ubicacion') or '[COMPLETAR]'}  ")
    A(f"**Tipo de instalación:** {proy.get('tipo_instalacion') or '[COMPLETAR]'}  ")
    A(f"**Revisión:** {proy.get('revision') or 'A'}  ")
    A(f"**Fecha:** {proy.get('fecha') or date.today().isoformat()}\n")

    A("> **Documento preliminar.** Requiere revisión, validación y firma de un "
      "responsable técnico con licencia vigente antes de su emisión o uso para "
      "permiso, construcción o verificación.\n")

    A("## 1. Objeto y alcance\n")
    incluye, no_incluye = _lista(proy.get("alcance_incluye")), _lista(proy.get("alcance_no_incluye"))
    if incluye:
        A("**Incluye:**\n")
        A("\n".join(f"- {x}" for x in incluye) + "\n")
    else:
        A("[COMPLETAR: qué cubre esta memoria]\n")
    if no_incluye:
        A("**No incluye:**\n")
        A("\n".join(f"- {x}" for x in no_incluye) + "\n")
    else:
        A("**No incluye:** [COMPLETAR — el alcance negativo es obligatorio]\n")

    A("## 2. Bases normativas\n")
    A(f"- Norma base: **{bloque.get('norma_base', '[COMPLETAR]')}**")
    A(f"- Edición aplicable: **{bloque.get('edicion') or '[COMPLETAR — OBLIGATORIO]'}**")
    if j == "texas":
        A(f"- Autoridad: {bloque.get('autoridad_estatal', '')}")
        A(f"- AHJ municipal: {bloque.get('ahj_municipal') or '[COMPLETAR]'}")
        A(f"- Enmiendas locales: {bloque.get('enmiendas_locales') or '[VERIFICAR]'}")
    elif j == "mexico":
        A(f"- Unidad de Verificación: {bloque.get('unidad_verificacion') or '[COMPLETAR]'}")
        A(f"- Edición confirmada el: {bloque.get('fecha_verificacion_edicion') or '[COMPLETAR]'}")
        A(f"- Fuente consultada: {bloque.get('fuente_consultada') or '[COMPLETAR]'}")
    if rt:
        A("- Red de tierras: IEEE Std 80 (método de suelo uniforme)")
    A("\n- Normas concurrentes aplicables: [COMPLETAR según el proyecto]\n")

    A("## 3. Criterios y supuestos de diseño\n")
    A("Los criterios marcados como **[CRITERIO]** son decisiones de proyecto, no "
      "requisitos normativos. Los marcados **[SUPUESTO]** requieren confirmación "
      "antes de la firma.\n")
    if cc:
        icc_fila = ["Icc de diseño", "Calculada por bus infinito en cada tablero (sección 7.1)",
                    "[CRITERIO]", "kVA y Z% de placa de los transformadores"]
    else:
        icc_fila = ["Icc disponible", f"{sitio.get('icc_disponible_kA') or '**[FALTA — OBLIGATORIO]**'} kA",
                    "Dato externo", sitio.get("fuente_icc") or "**Solicitar a la compañía suministradora**"]
    A(tabla(["Parámetro", "Valor", "Tipo", "Origen"], [
        ["Temperatura ambiente de diseño",
         f"{sitio.get('temperatura_ambiente_C') or '[SUPUESTO 30 °C]'}",
         "Dato de sitio", sitio.get("temperatura_ambiente_C") and "Medido" or "**Confirmar**"],
        ["Temperatura de terminales", f"{sitio.get('temperatura_terminales_C', 75)} °C",
         "Dato de equipo", "Placa del equipo real"],
        ["Material del conductor", crit.get("material_conductor", "cobre"), "[CRITERIO]", "Proyecto"],
        ["Aislamiento", f"{crit.get('temp_aislamiento_C', 90)} °C", "[CRITERIO]", "Proyecto"],
        ["Caída de tensión, derivado", f"{crit.get('caida_tension_derivado_pct', 3)} %",
         "[CRITERIO]", "Nota informativa de la norma"],
        ["Caída de tensión, alimentador", f"{crit.get('caida_tension_alimentador_pct', 2)} %",
         "[CRITERIO]", "Nota informativa de la norma"],
        ["Margen de crecimiento", f"{crit.get('margen_crecimiento_pct', 25)} %", "[CRITERIO]", "Proyecto"],
        ["Desbalance máximo", f"{crit.get('desbalance_maximo_pct', 5)} %", "[CRITERIO]", "Proyecto"],
        icc_fila,
    ]))
    A("")

    A("## 4. Descripción de la instalación\n")
    if proy.get("descripcion_instalacion"):
        A(f"{proy['descripcion_instalacion']} Ver el diagrama unifilar del Anexo B.\n")
    else:
        A("[COMPLETAR: acometida, arquitectura de tensiones, jerarquía de tableros. "
          "Referir al diagrama unifilar del Anexo B.]\n")

    A("## 5. Cuadro de cargas\n")
    A("Conexión: F-N = fase-neutro (1 polo), F-F = fase-fase (2 polos), 3F = trifásica (3 polos).\n")
    if circ:
        filas = []
        for c in circ:
            filas.append([c.get("id", ""), c.get("nombre", ""), c.get("tablero") or "—",
                          f"{c.get('va', 0):,.0f}", f"{c.get('tension_V', 0):g}",
                          CONEXION.get(c.get("fases"), c.get("fases", "")),
                          "Sí" if c.get("continua") else "No",
                          f"{c.get('corriente_carga_A', 0):.1f}",
                          f"{c.get('corriente_diseno_A', 0):.1f}"])
        A(tabla(["ID", "Descripción", "Tablero", "VA", "V", "Conexión", "Continua", "I carga (A)",
                 "I diseño (A)"], filas))
        total = sum(float(c.get("va", 0)) for c in circ)
        A(f"\n**Carga instalada total:** {total:,.0f} VA")
        A("**Demanda máxima:** [COMPLETAR — aplicar factores de demanda y justificar cuáles]\n")
        alertas_v = [c for c in circ if c.get("alerta_tension")]
        for c in alertas_v:
            A(f"- **{c['id']}:** {c['alerta_tension']}")
        if alertas_v:
            A("")

    if bal.get("tableros"):
        A("### 5.1 Balanceo de fases por tablero\n")
        A(f"{bal.get('arreglo', '')}\n")
        for t in bal["tableros"]:
            fases = list(t["va_por_fase"])
            A(f"**{t['tablero']}** — desbalance {t['desbalance_pct']} % "
              f"(criterio de proyecto: ≤ {crit.get('desbalance_maximo_pct', 5)} %)\n")
            filas = []
            for e in t["cedula"]:
                filas.append(["-".join(str(p) for p in e["posiciones"]), e["circuito"], e["polos"],
                              CONEXION.get(e["polos"], ""), "-".join(e["fases"])]
                             + [f"{e['va_por_fase'].get(f, 0):,.0f}" if f in e["va_por_fase"] else ""
                                for f in fases])
            filas.append(["", "**Total**", "", "", ""] + [f"**{t['va_por_fase'][f]:,.0f}**" for f in fases])
            A(tabla(["Posición", "Circuito", "Polos", "Conexión", "Fases"] + [f"VA {f}" for f in fases], filas))
            for a in t.get("avisos", []):
                A(f"- {a}")
            A("")

    A("## 6. Cálculo de conductores\n")
    if circ:
        c = circ[0]
        cond = c.get("conductor", {})
        A("### 6.1 Cálculo desarrollado (ejemplo)\n")
        A(f"**Circuito {c.get('id')} — {c.get('nombre')}**\n")
        A("```")
        A(f"Carga:                {c.get('va'):,.0f} VA, {c.get('tension_V')} V, "
          f"{c.get('conexion', c.get('fases'))}, {'continua' if c.get('continua') else 'no continua'}")
        A(f"Corriente de carga:   {c.get('corriente_carga_A')} A")
        A(f"Corriente de diseño:  {c.get('corriente_diseno_A')} A"
          f"{'  (x1.25 por carga continua)' if c.get('continua') else ''}")
        A(f"Conductor propuesto:  {cond.get('calibre')} {cond.get('material')}, "
          f"aislamiento {cond.get('temp_aislamiento_C')} °C")
        A(f"Ampacidad de tabla:   {cond.get('ampacidad_tabla_A')} A")
        A(f"Factor temperatura:   x {cond.get('factor_temperatura')}")
        A(f"Factor agrupamiento:  x {cond.get('factor_agrupamiento')}")
        A(f"Ampacidad corregida:  {cond.get('ampacidad_corregida_A')} A")
        A(f"Límite por terminal:  {cond.get('ampacidad_limitada_terminal_A')} A "
          f"a {cond.get('temp_terminal_C')} °C")
        A(f"Regla que gobierna:   {cond.get('regla_gobernante')}")
        A(f"Ampacidad utilizable: {cond.get('ampacidad_utilizable_A')} A  ->  "
          f"{'CUMPLE' if cond.get('ampacidad_utilizable_A', 0) >= c.get('corriente_diseno_A', 0) else 'NO CUMPLE'}")
        if c.get("caida_tension"):
            A(f"Caída de tensión:     {c['caida_tension']['caida_pct']} % "
              f"en {c['caida_tension']['longitud_m']} m")
        A(f"Calibre final:        {c.get('calibre_final')}")
        A("```\n")

        A("### 6.2 Resumen por circuito\n")
        filas = []
        for c in circ:
            dv = c.get("caida_tension", {})
            filas.append([c.get("id"), c.get("calibre_final"),
                          c.get("conductor", {}).get("material", ""),
                          c.get("egc", {}).get("egc_calibre", ""),
                          c.get("proteccion", {}).get("capacidad_nominal_A", ""),
                          dv.get("longitud_m", "n/d"),
                          f"{dv.get('caida_pct', 'n/d')}",
                          "⚠" if c.get("alerta") else ""])
        A(tabla(["ID", "Calibre", "Material", "EGC", "Protección (A)", "Long. (m)", "Δ V (%)", ""], filas))
        A("")
        alertas = [c for c in circ if c.get("alerta") or c.get("alerta_longitud")]
        if alertas:
            A("### 6.3 Observaciones\n")
            for c in alertas:
                A(f"- **{c.get('id')}:** {c.get('alerta') or c.get('alerta_longitud')}")
            A("")

    A("## 7. Protecciones\n")
    if circ:
        filas = []
        for c in circ:
            e = equipo.get(c.get("id"), {})
            filas.append([c.get("id"), c.get("proteccion", {}).get("capacidad_nominal_A"),
                          c.get("polos", c.get("fases")),
                          f"{e['tipo']} ({e['catalogo']})" if e else "[COMPLETAR]",
                          e.get("kA", "[COMPLETAR]")])
        A(tabla(["ID", "Capacidad (A)", "Polos", "Tipo", "Cap. interruptiva (kA)"], filas))
        if equipo:
            A("\nTipo y capacidad interruptiva: sugerencia Square D de la sección 9.1.")
    if cc:
        A("\n### 7.1 Corriente de cortocircuito (método del bus infinito)\n")
        A(f"{cc.get('formula', '')}.\n")
        A(tabla(["Nodo", "Tipo", "V sistema", "Z (Ω)", "Icc sim. (kA)", "Aporte (kA)", "Icc total (kA)",
                 "SCCR (kA)", "Verificación"],
                [[n["id"], n["tipo"], f"{n['tension_sistema_V']:g}", n["z_ohm"], n["icc_simetrica_kA"] or "∞",
                  n["aporte_kA"], n["icc_total_kA"] or "∞", n.get("sccr_kA", "—"), n.get("verificacion", "")]
                 for n in cc.get("nodos", [])]))
        A("\n**Supuestos del cálculo:**\n")
        for s in cc.get("supuestos", []):
            A(f"- {s}")
        for a in cc.get("avisos", []):
            A(f"- **Aviso:** {a}")
        A("\n### 7.2 Verificación de SCCR\n")
        malos = [n for n in cc.get("nodos", []) if n.get("verificacion") in ("NO CUMPLE", "AL LIMITE",
                                                                             "SIN SCCR DECLARADO")]
        if malos:
            for n in malos:
                A(f"- **{n['id']}:** {n['verificacion']} (Icc {n['icc_total_kA']} kA, SCCR {n.get('sccr_kA', '—')} kA)")
        else:
            A("Todos los tableros y equipos con SCCR declarado cumplen contra la Icc calculada en su punto.")
        A("")
    else:
        A("\n**Verificación de SCCR:** [COMPLETAR — comparar el SCCR de cada tablero "
          "contra la Icc disponible en ese punto. Sin el dato de Icc esta verificación "
          "no puede cerrarse.]\n")

    A("## 8. Puesta a tierra y unión\n")
    A("- Conductor del electrodo de puesta a tierra (GEC): [COMPLETAR — `ec.py gec`]")
    A("- Punto único de unión neutro-tierra: [COMPLETAR]")
    A("- EGC por circuito: ver tabla 6.2")
    if rt:
        m, tol, co = rt["malla"], rt["tolerables"], rt["conductor"]
        A(f"- Red de tierras (memoria separada, Anexo E): malla de {m['largo_m']} × {m['ancho_m']} m, "
          f"conductor {co['calibre_elegido']}, {m['varillas']} varillas; Rg = {m['Rg_ohm']} Ω; "
          f"Em = {m['Em_V']:,.0f} V contra {tol['E_toque_V']:,.0f} V tolerables; "
          f"Es = {m['Es_V']:,.0f} V contra {tol['E_paso_V']:,.0f} V. "
          f"Resultado: **{'CUMPLE' if rt['cumple'] else 'NO CUMPLE'}**.")
        if rt.get("sugerencia"):
            s = rt["sugerencia"]
            A(f"- Configuración que cumple: separación {s['separacion_m']} m y {s['varillas']} varillas "
              f"(Rg = {s['Rg_ohm']} Ω, Em = {s['Em_V']:,.0f} V).")
    else:
        A("- Sistema de electrodos y red de tierras: [COMPLETAR — `red_tierras.py`]")
    A("- Resistencia objetivo y método de medición: [COMPLETAR]")
    A("\n[Si algún conductor de fase se aumentó de calibre, verificar el aumento "
      "proporcional del EGC.]\n")

    A("## 9. Especificación de tableros\n")
    if sq.get("tableros"):
        A("### 9.1 Equipo sugerido — Square D\n")
        A(f"> {sq.get('advertencia', '')}\n")
        A(tabla(["Tablero", "Sistema", "Icc (kA)", "Familia", "Barras (A)", "Principal", "Espacios mín.",
                 "SCCR (kA)"],
                [[t["id"], t["sistema"], t["icc_kA"], t.get("familia") or "Consultar",
                  t.get("barras_minimas_A") or "—", t.get("principal", {}).get("descripcion", "—"),
                  t.get("espacios_minimos") or "—", t.get("sccr_resultante_kA") or "—"]
                 for t in sq["tableros"]]))
        A("\nEnvolvente NEMA, barra de tierra, neutro aislado en tableros derivados y directorio: "
          "[COMPLETAR por tablero]. Interruptores por circuito: Anexo G.\n")
    else:
        A("[COMPLETAR por tablero: tensión y configuración, capacidad de barras, "
          "principal o zapatas, SCCR, espacios instalados y de reserva, envolvente "
          "NEMA, barra de tierra y neutro aislado, directorio.]\n")

    A("## 10. Conclusiones\n")
    A("[COMPLETAR: cumplimiento, limitaciones, pendientes de verificación en campo.]\n")

    A("## 11. Supuestos pendientes de confirmación\n")
    A("| # | Supuesto | Valor usado | Quién confirma | Estatus |")
    A("|---|----------|-------------|----------------|---------|")
    for i, s in enumerate(_lista(proy.get("supuestos_pendientes_de_confirmar")) or
                          ["[COMPLETAR]"], 1):
        A(f"| {i} | {s} | | | Pendiente |")
    A("")

    A("## 12. Anexos\n")
    A("- Anexo A: cuadro de cargas (`cargas.csv`)")
    A("- Anexo B: diagrama unifilar (`unifilar.json` / `unifilar.svg`)")
    A("- Anexo C: salida de cálculo (`resultados.json`)")
    A("- Anexo D: hojas de datos y certificados de listado")
    if rt:
        A("- Anexo E: memoria de la red de tierras (`red-tierras.md`, `red-tierras.json`)")
    if cc:
        A("- Anexo F: cálculo de cortocircuito (`cortocircuito.json`)")
    if sq:
        A("- Anexo G: tableros e interruptores sugeridos Square D (`squared.md`, `squared.json`)")
    A("")

    A("## 13. Firmas\n")
    A(tabla(["Rol", "Nombre", "Licencia/Cédula", "Firma", "Fecha"], [
        ["Elaboró", proy.get("responsable_calculo", ""), "", "", ""],
        ["Revisó", proy.get("revisor", ""), "", "", ""],
        ["Responsable técnico", proy.get("responsable_tecnico", ""),
         proy.get("numero_licencia", ""), "", ""],
    ]))

    return "\n".join(L)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--resultados", required=True)
    p.add_argument("--proyecto")
    p.add_argument("--jurisdiccion")
    p.add_argument("--cortocircuito", help="Salida de `ec.py cortocircuito`")
    p.add_argument("--squared", help="Salida de `squared.py`")
    p.add_argument("--tierras", help="Salida JSON de `red_tierras.py`")
    p.add_argument("--salida", default="memoria.md")
    a = p.parse_args()

    doc = construir(leer_json(a.resultados), yaml_simple(a.proyecto), yaml_simple(a.jurisdiccion),
                    leer_json(a.cortocircuito), leer_json(a.squared), leer_json(a.tierras))
    with open(a.salida, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"Memoria generada: {a.salida}")
    print("Buscar y completar todos los marcadores [COMPLETAR] antes de emitir.")


if __name__ == "__main__":
    main()
