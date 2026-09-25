/* Interfaz local del agente eléctrico JARRSTECH.
   La página no calcula: captura datos, los guarda en proyectos/<id>/ a través de
   scripts/interfaz.py y muestra lo que devuelven los scripts. */
"use strict";
(() => {
  // ------------------------------------------------------------ utilidades
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const texto = (v) => (v === null || v === undefined ? "" : String(v).trim());
  const num = (v) => { const t = texto(v); if (t === "") return null; const x = Number(t); return Number.isFinite(x) ? x : NaN; };
  const fmt = (v, d = 0) => {
    if (v === null || v === undefined || v === "" || Number.isNaN(Number(v))) return "—";
    return Number(v).toLocaleString("es-MX", { maximumFractionDigits: d });
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const pref = {
    leer(k) { try { return localStorage.getItem("agente-electrico." + k); } catch { return null; } },
    guardar(k, v) { try { localStorage.setItem("agente-electrico." + k, v); } catch { /* sin almacenamiento */ } },
  };

  const SECCIONES = [
    { clave: "proyecto", titulo: "Proyecto" },
    { clave: "norma", titulo: "Norma y sitio" },
    { clave: "unifilar", titulo: "Unifilar" },
    { clave: "cargas", titulo: "Cargas" },
    { clave: "tierras", titulo: "Red de tierras" },
    { clave: "resultados", titulo: "Resultados" },
  ];
  const TIPO = {
    acometida: { nombre: "Acometida", sim: "ACOM", prefijo: "ACOM" },
    medidor: { nombre: "Medidor", sim: "MED", prefijo: "MED-" },
    transformador: { nombre: "Transformador", sim: "TR", prefijo: "TR-" },
    interruptor_principal: { nombre: "Interruptor principal", sim: "IP", prefijo: "IP-" },
    tablero: { nombre: "Tablero", sim: "TAB", prefijo: "TD-" },
    barra: { nombre: "Barra", sim: "BAR", prefijo: "BARRA-" },
    carga: { nombre: "Carga", sim: "CG", prefijo: "CARGA-" },
    motor: { nombre: "Motor", sim: "M", prefijo: "M-" },
    generador: { nombre: "Generador", sim: "GEN", prefijo: "GEN-" },
    ups: { nombre: "UPS", sim: "UPS", prefijo: "UPS-" },
    bess: { nombre: "Baterías (BESS)", sim: "BESS", prefijo: "BESS-" },
    fotovoltaico: { nombre: "Fotovoltaico", sim: "PV", prefijo: "PV-" },
    cargador_ve: { nombre: "Cargador de VE", sim: "EVSE", prefijo: "EVSE-" },
    transferencia: { nombre: "Transferencia (ATS)", sim: "ATS", prefijo: "ATS-" },
    capacitor: { nombre: "Capacitor", sim: "CAP", prefijo: "CAP-" },
  };
  const FUENTES = ["bess", "fotovoltaico", "generador", "ups"];
  const ESTADO_PASO = {
    ok: ["✓", "Listo"], con_avisos: ["!", "Con avisos"], con_errores: ["✕", "Con errores"],
    falta: ["?", "Falta un dato"], error: ["✕", "Error del script"], bloqueado: ["—", "Bloqueado"],
    omitido: ["—", "Omitido"], no_aplica: ["—", "No aplica"],
  };
  const NIVEL = { bloquea: "Bloquea", pendiente: "Pendiente", aviso: "Aviso" };

  const E = {
    inicio: null, id: null, modelo: null, version: null, hallazgos: [], salidas: null, carpeta: "",
    seccion: "proyecto", nodoSel: 0, sucio: false, guardando: false, calculando: false,
    temporizador: null, conflicto: null,
  };
  const principal = $("#principal");
  const nav = $("#nav");

  // ------------------------------------------------------------ errores visibles
  function mostrarError(msg) {
    const caja = $("#errores-js");
    caja.hidden = false;
    caja.textContent = "Error en la página: " + msg;
  }
  window.addEventListener("error", (e) => mostrarError(e.message));
  window.addEventListener("unhandledrejection", (e) => mostrarError(e.reason && e.reason.message ? e.reason.message : String(e.reason)));

  function toast(msg) {
    const t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3200);
  }

  // ------------------------------------------------------------ API
  async function api(ruta, datos) {
    const opts = datos === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Agente-Electrico": "1" },
      body: JSON.stringify(datos),
    };
    const r = await fetch(ruta, opts);
    let cuerpo = null;
    try { cuerpo = await r.json(); } catch { cuerpo = null; }
    if (!r.ok) {
      const e = new Error((cuerpo && cuerpo.error) || `Error ${r.status}`);
      e.status = r.status;
      e.cuerpo = cuerpo;
      throw e;
    }
    return cuerpo;
  }

  // ------------------------------------------------------------ modelo
  function obtener(ruta) {
    return ruta.split(".").reduce((o, k) => (o === null || o === undefined ? undefined : o[k]), E.modelo);
  }
  function fijar(ruta, valor) {
    const partes = ruta.split(".");
    let o = E.modelo;
    for (let i = 0; i < partes.length - 1; i++) {
      const k = partes[i];
      if (o[k] === null || o[k] === undefined || typeof o[k] !== "object") o[k] = /^\d+$/.test(partes[i + 1]) ? [] : {};
      o = o[k];
    }
    o[partes[partes.length - 1]] = valor;
  }
  function normalizarModelo() {
    const m = E.modelo;
    m.proyecto = m.proyecto || {};
    for (const k of ["alcance_incluye", "alcance_no_incluye", "supuestos_pendientes_de_confirmar"]) {
      if (!Array.isArray(m.proyecto[k])) m.proyecto[k] = [];
    }
    m.jurisdiccion = m.jurisdiccion || {};
    for (const k of ["texas", "mexico", "sitio", "criterios"]) m.jurisdiccion[k] = m.jurisdiccion[k] || {};
    m.unifilar = m.unifilar || {};
    if (!Array.isArray(m.unifilar.nodos)) m.unifilar.nodos = [];
    if (!Array.isArray(m.cargas)) m.cargas = [];
    if (!m.cargas.length) m.cargas.push(cargaNueva());
    if (E.nodoSel >= m.unifilar.nodos.length) E.nodoSel = 0;
  }
  const nodos = () => E.modelo.unifilar.nodos;
  const tableros = () => nodos().filter((n) => ["tablero", "barra"].includes(texto(n.tipo)) && texto(n.id));
  const nodoPorId = (id) => nodos().find((n) => texto(n.id) === texto(id));

  function sistemaEtq(n) {
    const v = num(n && n.tension_V);
    if (!v) return "";
    const f = texto(n.fases) || "3";
    const h = texto(n.hilos) || (f === "3" ? "4" : "3");
    if (f === "3") return h === "4" ? `${fmt(v)}Y/${fmt(Math.round(v / Math.sqrt(3)))} V 3F-4H` : `${fmt(v)} V 3F-3H`;
    return h === "3" || h === "4" ? `${fmt(v)}/${fmt(v / 2)} V 1F-3H` : `${fmt(v)} V 1F-2H`;
  }
  function tensionSugerida(c) {
    const n = nodoPorId(c.tablero);
    const v = num(n && n.tension_V);
    if (!v || !["1", "2", "3"].includes(texto(c.fases))) return null;
    if (texto(c.fases) === "1") return Math.round((texto(n.fases) || "3") === "3" ? v / Math.sqrt(3) : v / 2);
    return v;
  }
  function conexionEtq(f) {
    return { 1: "fase-neutro", 2: "fase-fase", 3: "trifásica" }[texto(f)] || "";
  }

  // ------------------------------------------------------------ guardado
  function estadoGuardado(msg, error = false) {
    const el = $("#estado-guardado");
    el.textContent = msg;
    el.classList.toggle("error", error);
  }
  const hora = (iso) => (iso ? iso.slice(11, 16) : "");

  function marcarSucio() {
    E.sucio = true;
    estadoGuardado("Sin guardar…");
    clearTimeout(E.temporizador);
    E.temporizador = setTimeout(() => guardar(), 900);
  }
  async function guardar({ forzar = false } = {}) {
    clearTimeout(E.temporizador);
    if (!E.id || (E.conflicto && !forzar)) return;
    if (E.guardando) { E.otraVez = true; return; }
    E.guardando = true;
    E.sucio = false;
    estadoGuardado("Guardando…");
    let bien = false;
    try {
      const r = await api("/api/guardar", { id: E.id, modelo: E.modelo, version: E.version, forzar });
      E.version = r.version;
      E.hallazgos = r.hallazgos;
      E.conflicto = null;
      bien = true;
      estadoGuardado("Guardado " + hora(r.guardado));
      aplicarHallazgos();
      if (forzar) render();
    } catch (e) {
      E.sucio = true;
      if (e.status === 409) {
        E.conflicto = e.message;
        render();
        estadoGuardado("Sin guardar: los archivos cambiaron fuera de la interfaz", true);
      } else {
        estadoGuardado("No se guardó: " + e.message, true);
      }
    } finally {
      E.guardando = false;
      if (bien && (E.otraVez || E.sucio)) { E.otraVez = false; marcarSucio(); }
    }
  }
  async function guardarAhora() {
    clearTimeout(E.temporizador);
    while (E.guardando) await sleep(80);
    if (E.sucio) await guardar();
    while (E.guardando) await sleep(80);
  }

  // ------------------------------------------------------------ hallazgos
  function seccionDeRef(ref) {
    if (ref.startsWith("proyecto")) return "proyecto";
    if (ref.startsWith("jurisdiccion")) return "norma";
    if (ref.startsWith("unifilar")) return "unifilar";
    if (ref.startsWith("cargas")) return "cargas";
    if (ref.startsWith("tierras")) return "tierras";
    return "resultados";
  }
  function cuenta(sec) {
    const hs = E.hallazgos.filter((h) => h.seccion === sec);
    return { b: hs.filter((h) => h.nivel === "bloquea").length, p: hs.filter((h) => h.nivel === "pendiente").length };
  }
  function listaHallazgos(lista, vacio = "") {
    if (!lista.length) return vacio;
    const orden = { bloquea: 0, pendiente: 1, aviso: 2 };
    return `<ul class="hallazgos">${[...lista].sort((a, b) => orden[a.nivel] - orden[b.nivel]).map((h) => `
      <li class="${h.nivel}" data-accion="ir" data-ref="${esc(h.ref)}" tabindex="0" role="button">
        <span class="tipo">${NIVEL[h.nivel]}</span><span>${esc(h.mensaje)}</span></li>`).join("")}</ul>`;
  }
  function cajaHallazgos(sec) {
    const lista = E.hallazgos.filter((h) => h.seccion === sec);
    const c = cuenta(sec);
    const abierto = c.b > 0 ? "open" : "";
    return `<details class="tarjeta resumen-hallazgos" ${abierto} ${lista.length ? "" : "hidden"} id="caja-hallazgos">
      <summary>${c.b ? `${c.b} dato(s) bloquean el cálculo` : "Nada bloquea el cálculo en esta sección"}${c.p ? ` · ${c.p} pendiente(s)` : ""}</summary>
      <div id="hallazgos-seccion">${listaHallazgos(lista)}</div></details>`;
  }
  function aplicarHallazgos() {
    renderNav();
    $$("[data-bind]", principal).forEach((el) => {
      el.classList.remove("nivel-bloquea", "nivel-pendiente", "nivel-aviso");
      el.removeAttribute("title");
    });
    $$("[data-msg]", principal).forEach((el) => { el.textContent = ""; el.className = "msg"; });
    const orden = { aviso: 0, pendiente: 1, bloquea: 2 };
    for (const h of [...E.hallazgos].sort((a, b) => orden[a.nivel] - orden[b.nivel])) {
      const sel = `[data-bind="${CSS.escape(h.ref)}"]`;
      const el = principal.querySelector(sel);
      if (el) {
        el.classList.remove("nivel-bloquea", "nivel-pendiente", "nivel-aviso");
        el.classList.add("nivel-" + h.nivel);
        el.title = h.mensaje;
      }
      const m = principal.querySelector(`[data-msg="${CSS.escape(h.ref)}"]`);
      if (m) { m.textContent = h.mensaje; m.className = "msg nivel-" + h.nivel; }
    }
    const caja = $("#caja-hallazgos");
    if (caja) {
      const sec = E.seccion;
      const lista = E.hallazgos.filter((h) => h.seccion === sec);
      const c = cuenta(sec);
      caja.hidden = !lista.length;
      caja.querySelector("summary").textContent =
        (c.b ? `${c.b} dato(s) bloquean el cálculo` : "Nada bloquea el cálculo en esta sección") + (c.p ? ` · ${c.p} pendiente(s)` : "");
      $("#hallazgos-seccion").innerHTML = listaHallazgos(lista);
    }
    if (E.seccion === "unifilar") {
      $$(".arbol .nodo").forEach((b) => {
        const i = b.dataset.i;
        const hs = E.hallazgos.filter((h) => h.ref.startsWith(`unifilar.nodos.${i}.`));
        const p = b.querySelector(".punto");
        p.className = "punto " + (hs.some((h) => h.nivel === "bloquea") ? "bloquea" : hs.some((h) => h.nivel === "pendiente") ? "pendiente" : "");
      });
    }
    const previa = $("#lista-previa");
    if (previa) previa.innerHTML = resumenPrevio();
  }
  function irA(ref) {
    const sec = seccionDeRef(ref);
    const m = ref.match(/^unifilar\.nodos\.(\d+)/);
    if (m) E.nodoSel = Number(m[1]);
    irSeccion(sec, false);
    const el = principal.querySelector(`[data-bind="${CSS.escape(ref)}"]`) || principal.querySelector(`[data-bind^="${CSS.escape(ref)}"]`);
    if (el) {
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      el.focus({ preventScroll: true });
    } else {
      principal.focus();
    }
  }

  // ------------------------------------------------------------ campos
  function campo(ruta, etiqueta, o = {}) {
    const v = obtener(ruta);
    const id = "f-" + ruta.replace(/[^\w]/g, "_");
    const rr = o.rerender ? 'data-rerender="1"' : "";
    const unidad = o.unidad ? ` <span style="font-weight:400;color:var(--texto-3)">(${esc(o.unidad)})</span>` : "";
    const ayuda = o.ayuda ? `<div class="ayuda">${o.ayuda}</div>` : "";
    const msg = `<div class="msg" data-msg="${esc(ruta)}"></div>`;
    let control;
    if (o.opciones) {
      const actual = texto(v);
      const ops = [...o.opciones];
      if (actual && !ops.some(([val]) => String(val) === actual)) ops.push([actual, actual + " (no reconocido)"]);
      control = `<select id="${id}" data-bind="${esc(ruta)}" ${rr}>${ops.map(([val, txt]) =>
        `<option value="${esc(val)}" ${String(val) === actual ? "selected" : ""}>${esc(txt)}</option>`).join("")}</select>`;
    } else if (o.tipo === "textarea") {
      const valor = o.lista ? (Array.isArray(v) ? v.join("\n") : texto(v)) : texto(v);
      control = `<textarea id="${id}" data-bind="${esc(ruta)}" ${o.lista ? 'data-lista="1"' : ""} placeholder="${esc(o.ph || "")}" rows="${o.filas || 3}">${esc(valor)}</textarea>`;
    } else if (o.tipo === "checkbox") {
      return `<div class="campo ${o.clase || ""}"><label class="check"><input type="checkbox" id="${id}" data-bind="${esc(ruta)}" ${v ? "checked" : ""} ${rr}> ${esc(etiqueta)}</label>${ayuda}${msg}</div>`;
    } else {
      const tipo = o.tipo === "date" ? "date" : "text";
      const modo = o.numero ? 'inputmode="decimal"' : "";
      control = `<input id="${id}" type="${tipo}" ${modo} data-bind="${esc(ruta)}" value="${esc(texto(v))}" placeholder="${esc(o.ph || "")}" autocomplete="off" ${rr} ${o.attrs || ""}>`;
    }
    return `<div class="campo ${o.clase || ""}"><label for="${id}" class="${o.req ? "req" : ""}">${esc(etiqueta)}${unidad}</label>${control}${ayuda}${msg}</div>`;
  }
  const n_ = (ruta, etiqueta, unidad, o = {}) => campo(ruta, etiqueta, { numero: true, unidad, ...o });
  const cab = (titulo, desc, acciones = "") =>
    `<div class="seccion-cab"><div><h1>${esc(titulo)}</h1><p>${desc}</p></div>${acciones ? `<div class="acciones">${acciones}</div>` : ""}</div>`;
  const bannerConflicto = () => E.conflicto ? `<div class="banner error"><div><strong>No se guardó.</strong> ${esc(E.conflicto)}</div>
    <div class="acciones"><button class="btn" data-accion="recargar">Recargar del disco</button>
    <button class="btn peligro" data-accion="forzar">Sobrescribir con lo de la interfaz</button></div></div>` : "";

  // ------------------------------------------------------------ navegación
  function renderNav() {
    if (!E.modelo) { nav.innerHTML = ""; return; }
    const pasos = (E.salidas && E.salidas.bitacora && E.salidas.bitacora.pasos) || [];
    nav.innerHTML = SECCIONES.map((s, i) => {
      let ins = "";
      if (s.clave === "resultados") {
        if (pasos.length) {
          const malos = pasos.filter((p) => ["falta", "error", "con_errores"].includes(p.estado)).length;
          ins = malos ? `<span class="insignia bloquea" title="Pasos con error o dato faltante">${malos}</span>` : `<span class="insignia ok">✓</span>`;
        }
      } else {
        const c = cuenta(s.clave);
        ins = (c.b ? `<span class="insignia bloquea" title="Bloquean el cálculo">${c.b}</span>` : "") +
          (c.p ? `<span class="insignia pendiente" title="Pendientes">${c.p}</span>` : "");
      }
      return `<button type="button" data-seccion="${s.clave}" class="${E.seccion === s.clave ? "activo" : ""}" ${E.seccion === s.clave ? 'aria-current="page"' : ""}>
        <span class="num">${i + 1}</span><span class="titulo">${s.titulo}</span><span class="insignias">${ins}</span></button>`;
    }).join("") + `<div class="pie">
      <p><span class="insignia bloquea">n</span> dato que bloquea el cálculo.</p>
      <p><span class="insignia pendiente">n</span> pendiente: el cálculo corre, pero el resultado queda incompleto.</p>
      <p>Todo se guarda solo en <span class="mono">${esc(E.carpeta.split(/[\\/]/).slice(-2).join("/"))}</span>.</p></div>`;
  }
  function irSeccion(sec, arriba = true) {
    E.seccion = sec;
    try { history.replaceState(null, "", "#" + sec); } catch { /* sin historial */ }
    render();
    if (arriba) window.scrollTo(0, 0);
  }

  // ------------------------------------------------------------ render principal
  function render() {
    if (!E.modelo) return;
    const activo = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.bind : null;
    renderNav();
    const r = { proyecto: renderProyecto, norma: renderNorma, unifilar: renderUnifilar, cargas: renderCargas,
      tierras: renderTierras, resultados: renderResultados }[E.seccion] || renderProyecto;
    principal.innerHTML = bannerConflicto() + r();
    aplicarHallazgos();
    if (activo) {
      const el = principal.querySelector(`[data-bind="${CSS.escape(activo)}"]`);
      if (el) el.focus({ preventScroll: true });
    }
    botonCalcular();
  }

  // ---------- 1. Proyecto
  function renderProyecto() {
    const p = "proyecto.";
    const ocup = [["", "—"], ...((E.inicio && E.inicio.catalogos.ocupaciones) || []).map((o) =>
      [o, o === "otros" ? "Otros (100 %)" : o.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())]), ["otra", "Otra (Claude la documenta)"]];
    return cab("Proyecto", "Datos generales. Salen en la portada, el alcance y las firmas de la memoria de cálculo.") +
      cajaHallazgos("proyecto") + `
      <section class="tarjeta"><h2>Identificación</h2><p class="sub">Lo que quede vacío sale como [COMPLETAR] en la memoria.</p>
        <div class="rejilla">
          ${campo(p + "proyecto", "Nombre del proyecto", { req: true })}
          ${campo(p + "cliente", "Cliente")}
          ${campo(p + "ubicacion", "Ubicación", { ph: "Municipio, estado" })}
          ${campo(p + "tipo_instalacion", "Tipo de instalación", { opciones: [["", "—"], ["industrial", "Industrial"], ["comercial", "Comercial"], ["residencial", "Residencial"], ["mixto", "Mixto"]] })}
          ${campo(p + "tipo_ocupacion", "Ocupación (art. 220)", { opciones: ocup, ayuda: "Para los factores de demanda. Si no encaja, se aplica 100 % y se documenta." })}
          ${campo(p + "revision", "Revisión")}
          ${campo(p + "fecha", "Fecha", { tipo: "date" })}
        </div>
        <div style="margin-top:12px">${campo(p + "descripcion_instalacion", "Descripción de la instalación", { tipo: "textarea", ph: "Acometida en 13.8 kV, transformador de 300 kVA a 480Y/277 V, tablero general y dos tableros derivados…" })}</div>
      </section>
      <section class="tarjeta"><h2>Alcance</h2><p class="sub">Un renglón por concepto. El alcance negativo protege tanto como el positivo.</p>
        <div class="rejilla dos">
          ${campo(p + "alcance_incluye", "Incluye", { tipo: "textarea", lista: true, filas: 5, ph: "Tablero general y alimentadores\nCircuitos derivados de TD-1 y TD-2" })}
          ${campo(p + "alcance_no_incluye", "No incluye", { tipo: "textarea", lista: true, filas: 5, ph: "Media tensión aguas arriba del transformador\nEstudio de arco eléctrico (IEEE 1584)" })}
        </div>
        <div style="margin-top:12px">${campo(p + "supuestos_pendientes_de_confirmar", "Supuestos pendientes de confirmar", { tipo: "textarea", lista: true, ph: "Temperatura ambiente 35 °C: confirmar con el cliente" })}</div>
      </section>
      <section class="tarjeta"><h2>Firmas</h2>
        <div class="rejilla">
          ${campo(p + "responsable_calculo", "Elaboró")}
          ${campo(p + "revisor", "Revisó")}
          ${campo(p + "responsable_tecnico", "Responsable técnico")}
          ${campo(p + "numero_licencia", "Número de licencia o cédula")}
        </div>
        <p class="nota importante">La memoria es un documento preliminar. Antes de usarla para permiso, construcción o verificación
          la debe revisar y firmar un responsable técnico con licencia vigente (PE registrado en Texas; en México, responsable con cédula y dictamen de UVIE).</p>
      </section>`;
  }

  // ---------- 2. Norma y sitio
  function renderNorma() {
    const j = E.modelo.jurisdiccion;
    const jur = texto(j.jurisdiccion);
    const radio = (val, titulo, desc) => `<label class="opcion"><input type="radio" name="jur" value="${val}" data-bind="jurisdiccion.jurisdiccion" data-rerender="1" ${jur === val ? "checked" : ""}>
      <div><strong>${titulo}</strong><span>${desc}</span></div></label>`;
    const mx = "jurisdiccion.mexico.";
    const tx = "jurisdiccion.texas.";
    const si = "jurisdiccion.sitio.";
    const cr = "jurisdiccion.criterios.";
    const bloqueJur = jur === "mexico" ? `
        <h3>NOM-001-SEDE</h3>
        <div class="rejilla">
          ${campo(mx + "edicion", "Edición vigente", { req: true, ph: "p. ej. NOM-001-SEDE-2012", ayuda: "Confírmala en el DOF: hay fuentes públicas contradictorias. No se asume." })}
          ${campo(mx + "fecha_verificacion_edicion", "Fecha de la confirmación", { tipo: "date", req: true })}
          ${campo(mx + "fuente_consultada", "Fuente consultada", { req: true, ph: "DOF / Catálogo Nacional de Normas" })}
          ${campo(mx + "unidad_verificacion", "Unidad de Verificación (UVIE)")}
        </div>` : jur === "texas" ? `
        <h3>NFPA 70 (NEC)</h3>
        <div class="rejilla">
          ${campo(tx + "edicion", "Edición del NEC", { req: true, opciones: [["", "—"], ["2023", "NEC 2023"], ["2026", "NEC 2026"]], ayuda: "TDLR adoptó el NEC 2026 con efecto el 1-sep-2026. Depende del inicio de obra." })}
          ${campo(tx + "fecha_inicio_obra", "Inicio de obra", { tipo: "date", req: true })}
          ${campo(tx + "fecha_verificacion_edicion", "Fecha de la confirmación", { tipo: "date", req: true })}
          ${campo(tx + "fuente_consultada", "Fuente consultada", { req: true, ph: "TDLR / AHJ municipal" })}
          ${campo(tx + "ahj_municipal", "AHJ municipal", { ph: "Ciudad" })}
          ${campo(tx + "enmiendas_locales", "Enmiendas locales")}
        </div>
        <p class="nota">Los scripts trabajan en metros y °C, y la memoria sale en español. Captura longitudes en metros; Claude convierte y traduce el entregable para Texas.</p>` :
      `<p class="nota importante" style="margin-top:12px">Elige la jurisdicción. Un proyecto usa un solo marco normativo; si el cliente opera en los dos países, son dos proyectos.</p>`;
    return cab("Norma y sitio", "Jurisdicción, edición de la norma, datos del sitio que nunca se asumen y criterios de proyecto.") +
      cajaHallazgos("norma") + `
      <section class="tarjeta"><h2>Jurisdicción</h2><p class="sub">El agente no calcula sin la jurisdicción y la edición confirmada.</p>
        <div class="opciones" role="radiogroup" aria-label="Jurisdicción">
          ${radio("mexico", "México", "NOM-001-SEDE · mm² y AWG, metros, °C")}
          ${radio("texas", "Texas, EE. UU.", "NFPA 70 (NEC) · AWG/kcmil")}
        </div>
        <div class="msg" data-msg="jurisdiccion.jurisdiccion"></div>
        ${bloqueJur}
      </section>
      <section class="tarjeta"><h2>Datos del sitio</h2><p class="sub">Se piden siempre; no hay valor por omisión.</p>
        <div class="rejilla">
          ${n_(si + "temperatura_ambiente_C", "Temperatura ambiente de diseño", "°C", { req: true, ph: "p. ej. 35", ayuda: "Número entero. Corrige la ampacidad de todos los circuitos que no digan otra." })}
          ${campo(si + "temperatura_terminales_C", "Temperatura de terminales", { req: true, unidad: "°C", opciones: [["", "—"], ["60", "60 °C"], ["75", "75 °C"], ["90", "90 °C"]], ayuda: "De la placa del equipo real (110.14(C))." })}
          ${n_(si + "icc_disponible_kA", "Icc en el punto de entrega", "kA", { ayuda: "Del oficio de CFE o de la utility. En servicio de baja tensión sin transformador propio es obligatoria." })}
          ${campo(si + "fuente_icc", "Fuente de la Icc", { ph: "Oficio CFE núm. …, fecha" })}
          ${n_(si + "altitud_msnm", "Altitud", "m s. n. m.")}
          ${campo(si + "area_clasificada", "Hay áreas clasificadas (polvos, gases, vapores)", { tipo: "checkbox", rerender: true })}
          ${j.sitio.area_clasificada ? campo(si + "clasificacion", "Clasificación", { ph: "Clase II, Div. 2 (harina)…" }) : ""}
        </div>
      </section>
      <section class="tarjeta"><h2>Criterios de proyecto <span class="etiqueta-criterio">CRITERIO</span></h2>
        <p class="sub">Son decisiones de proyecto, no requisitos normativos. La caída de tensión y el aislamiento se pasan al cálculo de circuitos.</p>
        <div class="rejilla">
          ${n_(cr + "caida_tension_derivado_pct", "Caída máx. en derivados", "%")}
          ${n_(cr + "caida_tension_alimentador_pct", "Caída máx. en alimentadores", "%")}
          ${n_(cr + "caida_tension_total_pct", "Caída máx. total", "%")}
          ${n_(cr + "margen_crecimiento_pct", "Margen de crecimiento", "%")}
          ${n_(cr + "desbalance_maximo_pct", "Desbalance máximo", "%")}
          ${n_(cr + "reserva_espacios_pct", "Reserva de espacios en tableros", "%")}
          ${campo(cr + "material_conductor", "Material del conductor", { opciones: [["cobre", "Cobre"], ["aluminio", "Aluminio"]] })}
          ${campo(cr + "temp_aislamiento_C", "Clase de aislamiento", { unidad: "°C", opciones: [["", "—"], ["60", "60 °C"], ["75", "75 °C"], ["90", "90 °C (THHN/THWN-2)"]] })}
        </div>
      </section>`;
  }

  // ---------- 3. Unifilar
  function ordenArbol() {
    const lista = nodos();
    const ids = new Set(lista.map((n) => texto(n.id)));
    const hijos = new Map();
    lista.forEach((n, i) => {
      const p = texto(n.padre);
      const clave = p && ids.has(p) && p !== texto(n.id) ? p : "";
      if (!hijos.has(clave)) hijos.set(clave, []);
      hijos.get(clave).push(i);
    });
    const salida = [];
    const vistos = new Set();
    const recorrer = (clave, nivel) => {
      for (const i of hijos.get(clave) || []) {
        if (vistos.has(i)) continue;
        vistos.add(i);
        salida.push({ i, nivel });
        const id = texto(lista[i].id);
        if (id) recorrer(id, nivel + 1);
      }
    };
    recorrer("", 0);
    lista.forEach((_, i) => { if (!vistos.has(i)) salida.push({ i, nivel: 0 }); });
    return salida;
  }
  function renderUnifilar() {
    const lista = nodos();
    const acciones = `<button class="btn" data-accion="agregar-raiz">+ Nodo en la raíz</button>`;
    const intro = "El diagrama es un dato: cada equipo es un nodo y cuelga del que lo alimenta. El conductor de cada nodo es el que llega desde su padre.";
    if (!lista.length) {
      return cab("Unifilar", intro) + cajaHallazgos("unifilar") + `
        <section class="tarjeta"><h2>¿Cómo llega la energía?</h2><p class="sub">Elige un punto de partida; después completas los datos de placa.</p>
          <div class="inicio-rapido">
            <button class="btn" data-accion="inicio-mt"><div><strong>Media tensión con transformador propio</strong>
              <span>Acometida (13.8 kV, 23 kV…) → transformador → tablero general. La Icc se calcula por bus infinito con el kVA y Z% de placa.</span></div></button>
            <button class="btn" data-accion="inicio-bt"><div><strong>Baja tensión desde un transformador de CFE</strong>
              <span>Acometida en baja tensión → tablero general. Se necesita la Icc que declara CFE o el kVA y Z% de su transformador.</span></div></button>
          </div></section>`;
    }
    if (E.nodoSel >= lista.length) E.nodoSel = 0;
    const arbol = ordenArbol().map(({ i, nivel }) => {
      const n = lista[i];
      const t = TIPO[texto(n.tipo)] || { sim: "?" };
      return `<li><button type="button" class="nodo ${i === E.nodoSel ? "sel" : ""}" data-accion="sel-nodo" data-i="${i}" style="padding-left:${8 + nivel * 18}px">
        <span class="sim">${esc(t.sim)}</span><span class="txt"><span class="nid">${esc(texto(n.id) || "(sin id)")}</span>
        <span class="ndesc">${esc(texto(n.descripcion) || (TIPO[texto(n.tipo)] || {}).nombre || "")}${num(n.tension_V) ? " · " + fmt(num(n.tension_V)) + " V" : ""}</span></span>
        <span class="punto"></span></button></li>`;
    }).join("");
    const svg = E.salidas && E.salidas.svg ? `
      <section class="tarjeta"><h2>Diagrama del último cálculo</h2>
        <p class="sub">Se vuelve a dibujar cada vez que calculas${E.salidas.desactualizado ? " · <strong>no incluye tus últimos cambios</strong>" : ""}.</p>
        <div class="vista-svg"><img alt="Diagrama unifilar" src="/api/archivo?id=${encodeURIComponent(E.id)}&nombre=unifilar.svg&t=${encodeURIComponent((E.salidas.bitacora || {}).fecha || "")}"></div></section>` : "";
    return cab("Unifilar", intro, acciones) + cajaHallazgos("unifilar") + `
      <div class="unifilar-layout">
        <section class="tarjeta"><h2>Jerarquía</h2><p class="sub">${lista.length} nodo(s). Punto rojo: dato que bloquea.</p>
          <ul class="arbol">${arbol}</ul></section>
        <section class="tarjeta">${editorNodo(E.nodoSel)}</section>
      </div>${svg}`;
  }
  function editorNodo(i) {
    const n = nodos()[i];
    if (!n) return "";
    const b = `unifilar.nodos.${i}.`;
    const tipo = texto(n.tipo);
    const padreOps = [["", "— ninguno (raíz) —"], ...nodos().filter((x, k) => k !== i && texto(x.id)).map((x) => [texto(x.id), `${texto(x.id)} · ${(TIPO[texto(x.tipo)] || {}).nombre || ""}`])];
    const tipoOps = [["", "—"], ...Object.entries(TIPO).map(([k, v]) => [k, v.nombre])];
    const v = num(n.tension_V);
    const esRaiz = !texto(n.padre);
    const bt = tipo === "acometida" && v !== null && !Number.isNaN(v) && v <= 1000;
    const mt = tipo === "acometida" && v > 1000;
    const calOps = [["", "—"], ...((E.inicio && E.inicio.catalogos.calibres) || []).map((c) => [c, c.includes("/") || Number(c) < 250 ? `${c} AWG` : `${c} kcmil`])];
    const conProteccion = !["acometida", "medidor", "transformador"].includes(tipo);
    const conSccr = ["tablero", "barra", "interruptor_principal", "transformador", "transferencia", ...FUENTES].includes(tipo);
    const conCarga = ["tablero", "barra", "carga", "motor", "cargador_ve", "capacitor", "transformador"].includes(tipo);
    const conConductor = !esRaiz || bt;
    const sistema = sistemaEtq(n);
    let suma = "";
    if (["tablero", "barra"].includes(tipo) && texto(n.id)) {
      const cargas = E.modelo.cargas.filter((c) => texto(c.tablero) === texto(n.id));
      const total = cargas.reduce((s, c) => s + (num(c.va) > 0 ? num(c.va) : 0), 0);
      if (cargas.length) {
        suma = `<div class="ayuda">Cuadro de cargas: ${fmt(total)} VA en ${cargas.length} carga(s).
          <button class="btn chico" data-accion="usar-suma" data-i="${i}" data-valor="${total}">Usar</button></div>`;
      }
    }
    const hijoDef = tipo === "acometida" ? (mt ? "transformador" : "tablero") : tipo === "transformador" ? "tablero" : tipo === "tablero" ? "tablero" : "carga";
    return `
      <div class="seccion-cab" style="margin-bottom:6px"><div><h2 style="font-size:16px">${esc(texto(n.id) || "Nodo nuevo")}</h2>
        <p class="sub" style="margin:2px 0 0">${esc((TIPO[tipo] || {}).nombre || "Elige el tipo")}${sistema ? ` · <span class="sistema-etq">${esc(sistema)}</span>` : ""}</p></div>
        <div class="acciones">
          <select id="tipo-hijo" aria-label="Tipo del nodo nuevo">${Object.entries(TIPO).map(([k, t]) => `<option value="${k}" ${k === hijoDef ? "selected" : ""}>${t.nombre}</option>`).join("")}</select>
          <button class="btn" data-accion="agregar-hijo" data-i="${i}">+ Agregar debajo</button>
          <button class="btn peligro" data-accion="borrar-nodo" data-i="${i}">Borrar</button>
        </div></div>
      <div class="grupo-campos"><h3>Identificación</h3><div class="rejilla">
        ${campo(b + "id", "Identificador", { req: true, rerender: true, ph: "TD-1", attrs: `data-id-nodo="${i}" data-anterior="${esc(texto(n.id))}"`, ayuda: "Sin espacios: ACOM, TR-1, TG-1, TD-2, M-01, BESS-1…" })}
        ${campo(b + "tipo", "Tipo de equipo", { req: true, opciones: tipoOps, rerender: true })}
        ${campo(b + "padre", "Alimentado desde", { opciones: padreOps, rerender: true })}
        ${campo(b + "descripcion", "Descripción", { ph: "Tablero de producción" })}
      </div></div>
      <div class="grupo-campos"><h3>Tensión</h3><div class="rejilla">
        ${n_(b + "tension_V", tipo === "transformador" ? "Tensión del secundario" : "Tensión nominal entre fases", "V", { rerender: true, req: ["acometida", "transformador", "tablero", "barra"].includes(tipo), ph: tipo === "acometida" ? "13800 o 480" : "480", ayuda: "Número: 480 para 480Y/277; 220 para 220Y/127." })}
        ${campo(b + "fases", "Fases", { rerender: true, opciones: [["", "—"], ["3", "3 · trifásico"], ["2", "2 · bifásico (fase-fase)"], ["1", "1 · monofásico"]] })}
        ${campo(b + "hilos", "Hilos", { rerender: true, opciones: [["", "—"], ["4", "4 (con neutro)"], ["3", "3"], ["2", "2"]], ayuda: "Un tablero con cargas fase-neutro necesita neutro (4 hilos)." })}
      </div>
      ${mt ? `<p class="nota">Bus infinito: la red del suministrador se toma con impedancia cero en el primario de cada transformador. Su Icc no entra al cálculo de baja tensión.</p>` : ""}
      ${bt ? `<p class="nota importante">Servicio en baja tensión: se usa la Icc del punto de entrega capturada en <a href="#" data-accion="ir" data-ref="jurisdiccion.sitio.icc_disponible_kA">Norma y sitio</a>, o el kVA y Z% del transformador de CFE si los das aquí.</p>` : ""}
      </div>
      ${tipo === "transformador" || bt ? `<div class="grupo-campos"><h3>${bt ? "Transformador del suministrador (opcional)" : "Datos de placa"}</h3><div class="rejilla">
        ${n_(b + "kva", "Potencia", "kVA", { req: !bt })}
        ${n_(b + "z_pct", "Impedancia Z", "%", { req: !bt, ph: "5.75" })}
        ${n_(b + "x_r", "Relación X/R", "", { ayuda: "Opcional. Sin ella la impedancia se toma reactiva (conservador)." })}
        ${tipo === "transformador" ? campo(b + "conexion", "Grupo de conexión", { ph: "Dyn11" }) : ""}
        ${tipo === "transformador" ? n_(b + "proteccion_primario_A", "Protección del primario", "A") : ""}
        ${tipo === "transformador" ? n_(b + "proteccion_secundario_A", "Protección del secundario", "A") : ""}
      </div></div>` : ""}
      ${conProteccion || conSccr ? `<div class="grupo-campos"><h3>Protección</h3><div class="rejilla">
        ${conProteccion ? n_(b + "interruptor_A", tipo === "tablero" ? "Interruptor principal o del alimentador" : "Interruptor", "A", { ayuda: tipo === "tablero" ? "Vacío = zapatas principales." : "" }) : ""}
        ${conSccr ? n_(b + "sccr_kA", "SCCR / capacidad interruptiva", "kA") : ""}
      </div></div>` : ""}
      ${conConductor ? `<div class="grupo-campos"><h3>${tipo === "transformador" ? "Conductor del primario" : bt ? "Conductor de acometida" : "Conductor que lo alimenta"}</h3><div class="rejilla">
        ${campo(b + "calibre", "Calibre", { opciones: calOps })}
        ${n_(b + "conductores_por_fase", "Conductores por fase", "", { ph: "1" })}
        ${campo(b + "material", "Material", { opciones: [["", "— (cobre)"], ["cobre", "Cobre"], ["aluminio", "Aluminio"]] })}
        ${n_(b + "longitud_m", "Longitud real", "m", { ayuda: "Recorrido desde el nodo de arriba." })}
        ${campo(b + "egc", "Tierra de equipos (EGC)", { opciones: calOps })}
        ${n_(b + "reactancia_ohm_km", "Reactancia", "Ω/km", { ayuda: "Opcional. Vacío = 0 (conservador)." })}
      </div></div>` : ""}
      ${conCarga || FUENTES.includes(tipo) ? `<div class="grupo-campos"><h3>${FUENTES.includes(tipo) ? "Aporte de falla" : "Carga"}</h3><div class="rejilla">
        ${conCarga ? n_(b + "carga_va", "Carga conectada", "VA", { ayuda: tipo === "motor" ? "Base del aporte del motor a la Icc." : "Se compara contra la capacidad del nodo de arriba." }) : ""}
        ${FUENTES.includes(tipo) ? n_(b + "aporte_icc_kA", "Corriente de falla que aporta", "kA", { ayuda: "Dato del fabricante. No se supone." }) : ""}
      </div>${suma}</div>` : ""}
      <div class="grupo-campos"><h3>Notas</h3>
        ${campo(b + "notas", "Notas y justificaciones", { tipo: "textarea", lista: true, ph: "Una por renglón. Aquí se justifican las advertencias que no se corrigen." })}
      </div>`;
  }
  function idLibre(tipo) {
    const t = TIPO[tipo] || { prefijo: "N-" };
    const usados = new Set(nodos().map((n) => texto(n.id)));
    if (!t.prefijo.endsWith("-") && !usados.has(t.prefijo)) return t.prefijo;
    const base = t.prefijo.endsWith("-") ? t.prefijo : t.prefijo + "-";
    for (let k = 1; k < 1000; k++) {
      const id = base + (["motor"].includes(tipo) ? String(k).padStart(2, "0") : k);
      if (!usados.has(id)) return id;
    }
    return "";
  }
  function nodoNuevo(tipo, padre) {
    const n = { id: idLibre(tipo), tipo, padre: padre || "", descripcion: "", tension_V: "", fases: "3",
      hilos: ["transformador", "tablero", "barra"].includes(tipo) ? "4" : "3", notas: [] };
    if (tipo === "tablero" && padre) {
      const p = nodoPorId(padre);
      if (p && ["transformador", "acometida"].includes(texto(p.tipo)) && !nodos().some((x) => texto(x.id) === "TG-1")) n.id = "TG-1";
      if (p && num(p.tension_V) && texto(p.tipo) !== "acometida") n.tension_V = texto(p.tension_V);
      if (p && texto(p.tipo) === "acometida" && num(p.tension_V) <= 1000) n.tension_V = texto(p.tension_V);
    }
    return n;
  }

  // ---------- 4. Cargas
  function cargaNueva() {
    const usados = (E.modelo && E.modelo.cargas ? E.modelo.cargas : []).map((c) => texto(c.id));
    let k = 1;
    for (const id of usados) { const m = id.match(/^C-(\d+)$/); if (m) k = Math.max(k, Number(m[1]) + 1); }
    let id = "C-" + String(k).padStart(2, "0");
    while (usados.includes(id)) id = "C-" + String(++k).padStart(2, "0");
    const tabs = E.modelo ? tableros() : [];
    const ultimo = E.modelo && E.modelo.cargas.length ? texto(E.modelo.cargas[E.modelo.cargas.length - 1].tablero) : "";
    return { id, nombre: "", va: "", tension: "", fases: "", fase: "", continua: "", longitud_m: "", n_conductores: "",
      material: "", ambiente_c: "", tablero: ultimo || (tabs.length === 1 ? texto(tabs[0].id) : ""), notas: "" };
  }
  function pistaTension(c) {
    const n = nodoPorId(c.tablero);
    const partes = [];
    if (texto(c.fases)) partes.push(conexionEtq(c.fases));
    if (n && sistemaEtq(n)) partes.push(sistemaEtq(n).replace(/ V .*/, " V"));
    return partes.join(" · ");
  }
  function renderCargas() {
    const cargas = E.modelo.cargas;
    const tabs = tableros();
    const tabOps = [["", "—"], ...tabs.map((t) => [texto(t.id), texto(t.id)])];
    const amb = texto(E.modelo.jurisdiccion.sitio.temperatura_ambiente_C);
    const mat = texto(E.modelo.jurisdiccion.criterios.material_conductor) || "cobre";
    const sel = (ruta, ops, valor, extra = "") => `<select data-bind="${esc(ruta)}" ${extra}>${ops.map(([v, t]) =>
      `<option value="${esc(v)}" ${texto(valor) === v ? "selected" : ""}>${esc(t)}</option>`).join("")}${texto(valor) && !ops.some(([v]) => v === texto(valor)) ? `<option selected value="${esc(valor)}">${esc(valor)} (?)</option>` : ""}</select>`;
    const inp = (ruta, valor, ph = "", clase = "", extra = "") =>
      `<input class="${clase}" data-bind="${esc(ruta)}" value="${esc(texto(valor))}" placeholder="${esc(ph)}" autocomplete="off" ${extra}>`;
    const filas = cargas.map((c, i) => {
      const b = `cargas.${i}.`;
      const f = texto(c.fases);
      const faseOps = f === "1" ? [["", "auto"], ["A", "A"], ["B", "B"], ["C", "C"]] : f === "2" ? [["", "auto"], ["AB", "AB"], ["BC", "BC"], ["CA", "CA"]] : [["", "—"]];
      const sug = tensionSugerida(c);
      return `<tr>
        <td>${inp(b + "id", c.id, "", "c-id")}</td>
        <td>${inp(b + "nombre", c.nombre, "Descripción del equipo", "c-nombre")}</td>
        <td class="c-medio">${sel(b + "tablero", tabOps, c.tablero, 'data-rerender="1"')}</td>
        <td class="c-conexion">${sel(b + "fases", [["", "—"], ["1", "1 · F-N"], ["2", "2 · F-F"], ["3", "3 · Trifásica"]], c.fases, 'data-rerender="1"')}</td>
        <td class="c-corto">${inp(b + "tension", c.tension, sug ? String(sug) : "V", "", 'inputmode="decimal" data-vivo="tension"')}<span class="pista" data-pista="${i}">${esc(pistaTension(c))}</span></td>
        <td class="c-corto">${sel(b + "fase", faseOps, c.fase, f === "3" || !f ? "disabled" : "")}</td>
        <td class="c-medio">${inp(b + "va", c.va, "VA", "", 'inputmode="decimal"')}</td>
        <td class="c-corto">${sel(b + "continua", [["", "—"], ["si", "Sí"], ["no", "No"]], c.continua)}</td>
        <td class="c-corto">${inp(b + "longitud_m", c.longitud_m, "m", "", 'inputmode="decimal"')}</td>
        <td class="c-corto">${inp(b + "n_conductores", c.n_conductores, "3", "", 'inputmode="numeric"')}</td>
        <td class="c-medio">${sel(b + "material", [["", `(${mat})`], ["cobre", "Cobre"], ["aluminio", "Aluminio"]], c.material)}</td>
        <td class="c-corto">${inp(b + "ambiente_c", c.ambiente_c, amb ? amb : "°C", "", 'inputmode="numeric"')}</td>
        <td>${inp(b + "notas", c.notas, "", "c-notas")}</td>
        <td class="acc"><button class="btn fantasma chico" data-accion="dup-carga" data-i="${i}" title="Duplicar fila" aria-label="Duplicar fila">⧉</button><button class="btn fantasma chico peligro" data-accion="borrar-carga" data-i="${i}" title="Borrar fila" aria-label="Borrar fila">✕</button></td>
      </tr>`;
    }).join("");
    const porTablero = {};
    for (const c of cargas) {
      const t = texto(c.tablero) || "(sin tablero)";
      porTablero[t] = porTablero[t] || { va: 0, n: 0 };
      if (num(c.va) > 0) porTablero[t].va += num(c.va);
      if (texto(c.id) || texto(c.va)) porTablero[t].n += 1;
    }
    const totales = Object.entries(porTablero).filter(([, x]) => x.n).map(([t, x]) => `${esc(t)}: <strong>${fmt(x.va)} VA</strong> (${x.n})`).join(" · ");
    const acciones = `<button class="btn" data-accion="pegar">Pegar desde Excel</button>
      <button class="btn" data-accion="rellenar-tensiones" title="Llena las tensiones vacías con la del tablero según la conexión">Rellenar tensiones</button>
      <button class="btn primario" data-accion="agregar-carga">+ Agregar carga</button>`;
    return cab("Cargas", "Una fila por circuito derivado. Cada carga declara su conexión: <strong>1 = fase-neutro</strong> (p. ej. 277 V en 480Y/277), <strong>2 = fase-fase</strong> (480 V, 2 polos) o <strong>3 = trifásica</strong>.", acciones) +
      cajaHallazgos("cargas") + `
      ${tabs.length ? "" : `<div class="banner alerta">Primero agrega los tableros en <a href="#" data-accion="seccion" data-seccion="unifilar">Unifilar</a>: cada carga cuelga de un tablero.</div>`}
      <section class="tarjeta" style="padding:0">
        <div class="tabla-envoltura" style="border:0">
          <table class="tabla-cargas">
            <thead><tr>
              <th>ID</th><th>Descripción</th><th>Tablero</th><th>Conexión</th><th>Tensión (V)</th><th title="Solo si quieres fijar la fase; si no, la asigna el balanceo Square D">Fase</th>
              <th>Carga (VA)</th><th title="Opera 3 horas o más de forma continua">Continua</th><th>Longitud (m)</th><th title="Conductores portadores de corriente en la misma canalización">Cond. canal.</th>
              <th>Material</th><th title="Solo si difiere de la del sitio">Amb. (°C)</th><th>Notas</th><th></th>
            </tr></thead>
            <tbody>${filas}</tbody>
            <tfoot><tr><td colspan="14">${totales || "Sin cargas todavía."}</td></tr></tfoot>
          </table>
        </div>
      </section>
      <p class="nota">Las cargas bifásicas (2 polos) se reparten mitad y mitad en sus dos fases según el arreglo de barras Square D.
        Si dejas <em>Fase</em> en auto, el balanceo la asigna. <em>Continua</em> se pregunta caso por caso: no se deduce del nombre del equipo.
        Motores: por ahora se dimensionan como carga general; el art. 430 lo revisa Claude.</p>`;
  }

  // ---------- 5. Red de tierras
  function renderTierras() {
    const t = E.modelo.tierras;
    const toggle = `<label class="toggle"><input type="checkbox" data-accion="toggle-tierras" ${t ? "checked" : ""}> La instalación tiene subestación propia y se diseña su malla de tierras</label>`;
    const intro = "Entrada separada del resto del proyecto. IEEE Std 80, suelo uniforme. Con la resistividad medida y la potencia de cortocircuito del suministrador.";
    if (!t) {
      return cab("Red de tierras", intro) + `<section class="tarjeta">${toggle}
        <p class="nota">Sin subestación propia no se diseña malla. El GEC y el EGC se dimensionan igual con el resto del proyecto.</p></section>`;
    }
    const b = "tierras.";
    const kv = num(obtener(b + "suministrador.tension_kV"));
    const mats = ((E.inicio && E.inicio.catalogos.materiales_malla) || []).map((m) => [m.clave, m.descripcion]);
    const calOps = [["", "— (4/0)"], ...((E.inicio && E.inicio.catalogos.calibres) || []).map((c) => [c, c])];
    return cab("Red de tierras", intro) + cajaHallazgos("tierras") + `
      <section class="tarjeta">${toggle}
        <div class="rejilla" style="margin-top:12px">${campo(b + "subestacion", "Subestación", { ph: "Subestación 300 kVA, 13.8 kV" })}</div></section>
      <section class="tarjeta"><h2>Terreno</h2><div class="rejilla">
        ${n_(b + "terreno.resistividad_ohm_m", "Resistividad del terreno", "Ω·m", { req: true, ayuda: "Medida con el método de Wenner (IEEE Std 81). Modelo de suelo uniforme." })}
        ${campo(b + "terreno.fuente", "Fuente", { ph: "Informe de medición, fecha" })}
      </div></section>
      <section class="tarjeta"><h2>Suministrador</h2><p class="sub">Del oficio de CFE o de la utility, en el punto de entrega.</p><div class="rejilla">
        ${n_(b + "suministrador.tension_kV", "Tensión de suministro", "kV", { req: true, rerender: true })}
        ${n_(b + "suministrador.mva_cc_3f", "Potencia de cortocircuito trifásica", "MVA", { req: true })}
        ${n_(b + "suministrador.mva_cc_1f", "Potencia de cortocircuito monofásica", "MVA", { ayuda: "Sin ella se usa la trifásica." })}
        ${n_(b + "suministrador.x_r", "Relación X/R", "", { ayuda: "Sin ella Df = 1." })}
        ${n_(b + "suministrador.frecuencia_Hz", "Frecuencia", "Hz", { ph: "60" })}
        ${campo(b + "suministrador.fuente", "Fuente", { ph: "Oficio CFE núm. …, fecha" })}
      </div>
      <div class="nota">¿Te dieron la corriente en kA? MVA = √3 × kV × kA.
        <span style="display:inline-flex;gap:6px;align-items:center;margin-left:6px">
          <input id="ka-convertir" inputmode="decimal" placeholder="kA" style="width:90px">
          <button class="btn chico" data-accion="ka-mva" data-destino="${b}suministrador.mva_cc_3f" ${kv ? "" : "disabled"}>→ trifásica</button>
          <button class="btn chico" data-accion="ka-mva" data-destino="${b}suministrador.mva_cc_1f" ${kv ? "" : "disabled"}>→ monofásica</button>
        </span>${kv ? "" : " (primero la tensión en kV)"}</div></section>
      <section class="tarjeta"><h2>Falla <span class="etiqueta-criterio">CRITERIO</span></h2><div class="rejilla">
        ${n_(b + "falla.tiempo_choque_s", "Tiempo de liberación (ts)", "s", { ayuda: "Define las tensiones tolerables." })}
        ${n_(b + "falla.tiempo_conductor_s", "Tiempo para el conductor (tc)", "s", { ayuda: "Usar el de la protección de respaldo." })}
        ${n_(b + "falla.factor_division_Sf", "Factor de división Sf", "", { ayuda: "1.0 es conservador. Menor que 1 requiere estudio." })}
      </div></section>
      <section class="tarjeta"><h2>Malla</h2><div class="rejilla">
        ${n_(b + "malla.largo_m", "Largo", "m", { req: true })}
        ${n_(b + "malla.ancho_m", "Ancho", "m", { req: true })}
        ${n_(b + "malla.separacion_m", "Separación entre conductores", "m", { req: true })}
        ${n_(b + "malla.profundidad_m", "Profundidad", "m")}
        ${campo(b + "malla.calibre", "Calibre del conductor", { opciones: calOps })}
        ${campo(b + "malla.material", "Material", { opciones: mats.length ? mats : [["cobre_duro", "cobre_duro"]] })}
        ${n_(b + "malla.temperatura_ambiente_C", "Temperatura ambiente", "°C")}
        ${n_(b + "malla.temperatura_maxima_C", "Temperatura máxima del conductor", "°C", { ayuda: "Vacío = fusión del material (uniones exotérmicas). Con conectores mecánicos, dato del fabricante." })}
      </div></section>
      <section class="tarjeta"><h2>Varillas, capa superficial y persona</h2><div class="rejilla">
        ${n_(b + "varillas.cantidad", "Cantidad de varillas", "")}
        ${n_(b + "varillas.longitud_m", "Longitud de varilla", "m")}
        ${campo(b + "varillas.en_perimetro", "Varillas en el perímetro o en las esquinas", { tipo: "checkbox" })}
        ${n_(b + "capa_superficial.resistividad_ohm_m", "Resistividad de la capa superficial", "Ω·m", { ayuda: "Grava triturada ≈ 3000. Vacío con espesor vacío = sin capa." })}
        ${n_(b + "capa_superficial.espesor_m", "Espesor de la capa", "m")}
        ${campo(b + "persona.peso_kg", "Peso de la persona", { unidad: "kg", opciones: [["50", "50 kg (más conservador)"], ["70", "70 kg"]] })}
        ${n_(b + "resistencia_objetivo_ohm", "Resistencia objetivo", "Ω", { ayuda: "La que exija la norma o el suministrador. Vacío = no se verifica." })}
      </div></section>`;
  }

  // ---------- 6. Resultados
  function resumenPrevio() {
    const hs = E.hallazgos;
    const b = hs.filter((h) => h.nivel === "bloquea");
    const p = hs.filter((h) => h.nivel === "pendiente");
    const a = hs.filter((h) => h.nivel === "aviso");
    const porSec = (lista) => SECCIONES.filter((s) => lista.some((h) => h.seccion === s.clave)).map((s) =>
      `<h3>${s.titulo}</h3>${listaHallazgos(lista.filter((h) => h.seccion === s.clave))}`).join("");
    return `<div class="cifras">
        <div class="cifra"><div class="v" style="color:var(--bloquea)">${b.length}</div><div class="l">bloquean algún paso</div></div>
        <div class="cifra"><div class="v" style="color:var(--pendiente)">${p.length}</div><div class="l">pendientes</div></div>
        <div class="cifra"><div class="v">${a.length}</div><div class="l">avisos</div></div></div>
      ${b.length ? `<details open><summary><strong>Bloquean</strong></summary>${porSec(b)}</details>` : ""}
      ${p.length ? `<details ${b.length ? "" : "open"}><summary><strong>Pendientes</strong></summary>${porSec(p)}</details>` : ""}
      ${a.length ? `<details><summary><strong>Avisos</strong></summary>${porSec(a)}</details>` : ""}`;
  }
  const chip = (txt, clase) => `<span class="chip ${clase}">${esc(txt)}</span>`;
  const tabla = (cabeza, filas, numericas = []) => `<div class="tabla-envoltura"><table><thead><tr>${cabeza.map((c, k) =>
    `<th class="${numericas.includes(k) ? "num" : ""}">${c}</th>`).join("")}</tr></thead><tbody>${filas.map((f) =>
    `<tr>${f.map((c, k) => `<td class="${numericas.includes(k) ? "num" : ""}">${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;

  function renderResultados() {
    const s = E.salidas || {};
    const bit = s.bitacora;
    const acciones = `<button class="btn primario" data-accion="calcular">${E.calculando ? '<span class="cargando"></span> Calculando…' : "Calcular"}</button>`;
    let html = cab("Resultados", "Cada número sale de un script y se puede reproducir con los comandos de la bitácora. La interfaz no calcula.", acciones);
    html += `<section class="tarjeta" id="res-previa"><h2>Revisión de datos</h2><p class="sub">Se actualiza mientras capturas. Lo que bloquea un paso impide correrlo; lo pendiente deja el resultado incompleto.</p>
      <div id="lista-previa">${resumenPrevio()}</div></section>`;
    if (!bit) {
      return html + `<section class="tarjeta vacio"><h2>Todavía no hay cálculo</h2><p>Cuando los datos estén listos, presiona <strong>Calcular</strong>.
        Se corre cada paso que tenga sus datos completos.</p></section>`;
    }
    if (s.desactualizado) {
      html += `<div class="banner alerta"><div><strong>Resultados desactualizados.</strong> Cambiaste datos después del último cálculo (${esc(bit.fecha.replace("T", " "))}).</div>
        <div class="acciones"><button class="btn primario" data-accion="calcular">Volver a calcular</button></div></div>`;
    }
    html += `<section class="tarjeta" id="res-pasos"><h2>Pasos del cálculo</h2><p class="sub">Última corrida: ${esc(bit.fecha.replace("T", " "))}</p>
      <ul class="pasos-lista">${bit.pasos.map((p) => {
        const [ico, etq] = ESTADO_PASO[p.estado] || ["?", p.estado];
        return `<li class="e-${p.estado}"><span class="ico">${ico}</span><div><div class="t">${esc(p.titulo)} · <span style="font-weight:500">${etq}</span></div>
          <div class="m">${esc(p.mensaje)}</div>
          ${p.detalle && p.detalle.length ? `<details><summary>Qué falta (${p.detalle.length})</summary><ul>${p.detalle.map((d) => `<li>${esc(d)}</li>`).join("")}</ul></details>` : ""}
          ${p.comando ? `<details><summary>Comando</summary><pre>${esc(p.comando)}</pre></details>` : ""}</div></li>`;
      }).join("")}</ul></section>`;
    html += resCortocircuito(s) + resValidacion(s) + resCircuitos(s) + resBalanceo(s) + resSquared(s) + resTierras(s) + resMemoria(s) + resClaude(s);
    return html;
  }
  function resCortocircuito(s) {
    const cc = s.cortocircuito;
    if (!cc) return "";
    const ver = (v) => !v ? "" : v === "CUMPLE" ? chip("Cumple", "ok") : v === "NO CUMPLE" ? chip("No cumple", "mal") : v === "AL LIMITE" ? chip("Al límite", "medio") : chip(v.toLowerCase(), "gris");
    const filas = cc.nodos.map((n) => [esc(n.id), esc((TIPO[n.tipo] || {}).nombre || n.tipo), esc(n.sistema), fmt(n.tension_sistema_V),
      fmt(n.icc_simetrica_kA, 2), fmt(n.aporte_kA, 2), `<strong>${n.icc_total_kA === null ? "∞" : fmt(n.icc_total_kA, 2)}</strong>`,
      fmt(n.capacidad_minima_estandar_kA), n.sccr_kA !== undefined ? fmt(n.sccr_kA) : "—", ver(n.verificacion)]);
    return `<section class="tarjeta" id="res-cortocircuito"><h2>Cortocircuito por bus infinito</h2><p class="sub">${esc(cc.formula || "")}</p>
      ${tabla(["Nodo", "Tipo", "Sistema", "V", "Icc sim. (kA)", "Aporte (kA)", "Icc total (kA)", "Cap. mín. (kA)", "SCCR (kA)", "Verificación"], filas, [3, 4, 5, 6, 7, 8])}
      ${cc.avisos && cc.avisos.length ? `<h3>Avisos</h3><ul>${cc.avisos.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : ""}
      <details><summary>Supuestos del método</summary><ul>${(cc.supuestos || []).map((a) => `<li>${esc(a)}</li>`).join("")}</ul></details></section>`;
  }
  function resValidacion(s) {
    const v = s.validacion;
    if (!v) return "";
    const filas = (v.hallazgos || []).map((h) => [h.severidad === "ERROR" ? chip("Error", "mal") : chip("Advertencia", "medio"), esc(h.nodo), esc(h.hallazgo), esc(h.referencia || "")]);
    return `<section class="tarjeta" id="res-validacion"><h2>Validación del unifilar</h2><p class="sub">${v.etapa === "completa" ? "Con el SCCR verificado contra la Icc calculada en cada nodo." : "Solo estructura: el SCCR no se verificó porque el cortocircuito no corrió."}
      Un error bloquea la emisión; las advertencias se corrigen o se justifican en las notas del nodo.</p>
      ${filas.length ? tabla(["", "Nodo", "Hallazgo", "Referencia"], filas) : `<p>${chip("Sin hallazgos", "ok")}</p>`}</section>`;
  }
  function resCircuitos(s) {
    const r = s.resultados;
    if (!r) return "";
    const filas = r.circuitos.map((c) => {
      const dvFinal = c.calibre_por_caida ? c.calibre_por_caida.caida_pct : c.caida_tension ? c.caida_tension.caida_pct : null;
      const uso = c.conductor && c.conductor.ampacidad_utilizable_A ? c.corriente_diseno_A / c.conductor.ampacidad_utilizable_A : 0;
      const notas = [c.alerta, c.alerta_tension, c.alerta_longitud].filter(Boolean).map((a) => `<div>${esc(a)}</div>`).join("");
      return [esc(c.id), esc(c.nombre), esc(c.tablero), esc(c.conexion), fmt(c.tension_V), fmt(c.va), fmt(c.corriente_carga_A, 1),
        fmt(c.corriente_diseno_A, 1) + (uso > 0.9 && !c.calibre_por_caida ? " " + chip("al límite", "medio") : ""),
        `<strong>${esc(c.calibre_final)}</strong> ${esc((c.conductor || {}).material || "")}${c.calibre_por_caida ? " " + chip("por caída", "medio") : ""}`,
        fmt((c.proteccion || {}).capacidad_nominal_A), esc((c.egc || {}).egc_calibre || ""),
        dvFinal === null ? chip("sin longitud", "medio") : fmt(dvFinal, 2) + (dvFinal > 2.5 ? " " + chip("al límite", "medio") : ""), notas];
    });
    return `<section class="tarjeta" id="res-circuitos"><h2>Circuitos</h2><p class="sub">Conductor por ampacidad, terminales y caída de tensión; protección por 240.6; EGC por 250.122.</p>
      ${tabla(["ID", "Descripción", "Tablero", "Conexión", "V", "VA", "I carga (A)", "I diseño (A)", "Conductor", "Protección (A)", "EGC", "Caída (%)", "Alertas"], filas, [4, 5, 6, 7, 9, 11])}
      <p class="nota">Cuando el conductor sube por caída de tensión, el EGC debe subir en la misma proporción (250.122(B)); el script solo lo avisa. Claude lo aplica en la revisión.</p></section>`;
  }
  function resBalanceo(s) {
    const r = s.resultados;
    if (!r || !r.balanceo) return "";
    const lim = num(E.modelo.jurisdiccion.criterios.desbalance_maximo_pct);
    return `<section class="tarjeta" id="res-balanceo"><h2>Balanceo por tablero</h2><p class="sub">${esc(r.balanceo.arreglo || "")}</p>
      ${r.balanceo.tableros.map((t) => {
        const fases = Object.entries(t.va_por_fase || {});
        const malo = lim !== null && !Number.isNaN(lim) && t.desbalance_pct > lim;
        return `<h3>${esc(t.tablero)} ${chip(fmt(t.desbalance_pct, 1) + " % de desbalance", malo ? "mal" : "ok")}</h3>
          <div class="cifras">${fases.map(([f, va]) => `<div class="cifra"><div class="v">${fmt(va)}</div><div class="l">VA en fase ${esc(f)}</div></div>`).join("")}
            <div class="cifra"><div class="v">${fmt(t.va_total)}</div><div class="l">VA total · ${t.espacios_usados} espacios</div></div></div>
          ${tabla(["Posiciones", "Circuito", "Descripción", "Polos", "Fases", "VA"], (t.cedula || []).map((c) => [esc((c.posiciones || []).join(", ")), esc(c.circuito), esc(c.nombre), c.polos, esc((c.fases || []).join("")), fmt(c.va)]), [3, 5])}
          ${(t.avisos || []).length ? `<ul>${t.avisos.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : ""}`;
      }).join("")}
      ${lim !== null ? `<p class="nota">Criterio de proyecto: desbalance máximo ${fmt(lim, 1)} %. Arriba de eso conviene redistribuir cargas.</p>` : ""}</section>`;
  }
  function resSquared(s) {
    const q = s.squared;
    if (!q) return "";
    return `<section class="tarjeta" id="res-squared"><h2>Tableros e interruptores Square D</h2><p class="sub">${esc(q.advertencia || "")}</p>
      ${q.tableros.map((t) => `
        <h3>${esc(t.id)} — ${esc(t.descripcion || "")}</h3>
        <p>${chip(t.sistema, "gris")} ${chip("Icc " + fmt(t.icc_kA, 2) + " kA", "gris")} ${t.familia ? chip(t.familia, "ok") : chip("Sin familia", "mal")}</p>
        ${tabla(["Concepto", "Sugerencia"], [["Tablero", esc(t.tablero_sugerido || "")], ["Principal", esc((t.principal || {}).descripcion || "—")],
          ["Barras mínimas", t.barras_minimas_A ? fmt(t.barras_minimas_A) + " A" : "—"], ["Espacios mínimos", t.espacios_minimos ?? "—"],
          ["SCCR resultante", t.sccr_resultante_kA ? fmt(t.sccr_resultante_kA) + " kA" : "—"], ["Envolvente", esc(t.envolvente || "—")]])}
        ${(t.interruptores || []).length ? tabla(["Pos.", "Circuito", "Descripción", "Polos", "A", "Tipo", "kA", "Catálogo"],
          t.interruptores.map((x) => [esc((x.posiciones || []).join(", ")), esc(x.circuito), esc(x.descripcion || ""), x.polos, fmt(x.amperes), esc(x.tipo || ""), fmt(x.kA), `<span class="mono">${esc(x.catalogo || "")}</span>`]), [3, 4, 6]) : ""}
        ${(t.avisos || []).length ? `<ul>${t.avisos.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : ""}
        ${(t.motivos_descarte || []).length ? `<details><summary>Familias descartadas</summary><ul>${t.motivos_descarte.map((a) => `<li>${esc(a)}</li>`).join("")}</ul></details>` : ""}`).join("")}
      <p class="nota">Confirma números de catálogo y datos marcados para verificar con el distribuidor antes de cotizar.
        <a href="/api/archivo?id=${encodeURIComponent(E.id)}&nombre=squared.md&descargar=1">Descargar squared.md</a></p></section>`;
  }
  function resTierras(s) {
    const t = s.tierras;
    if (!t) return "";
    const m = t.malla || {};
    const tol = t.tolerables || {};
    const sug = t.sugerencia;
    return `<section class="tarjeta" id="res-tierras"><h2>Red de tierras ${t.cumple ? chip("Cumple", "ok") : chip("No cumple", "mal")}</h2><p class="sub">${esc(t.norma || "")}</p>
      <div class="cifras">
        <div class="cifra"><div class="v">${fmt(m.Rg_ohm, 2)} Ω</div><div class="l">Resistencia de la malla</div></div>
        <div class="cifra"><div class="v">${fmt(m.GPR_V)} V</div><div class="l">GPR</div></div>
        <div class="cifra"><div class="v">${fmt(m.Em_V)} V</div><div class="l">Tensión de malla · tolerable ${fmt(tol.E_toque_V)} V</div></div>
        <div class="cifra"><div class="v">${fmt(m.Es_V)} V</div><div class="l">Tensión de paso · tolerable ${fmt(tol.E_paso_V)} V</div></div>
        <div class="cifra"><div class="v">${fmt((t.corriente_falla || {}).IG_A)} A</div><div class="l">Corriente de malla IG</div></div>
        <div class="cifra"><div class="v">${esc((t.conductor || {}).calibre_elegido || "—")}</div><div class="l">Conductor (mínimo ${esc((t.conductor || {}).calibre_minimo || "—")})</div></div>
      </div>
      ${tabla(["Criterio", "Calculado", "Límite", "Resultado"], (t.verificacion || []).map((v) => [esc(v.criterio), esc(v.calculado), esc(v.limite), v.resultado === "CUMPLE" ? chip("Cumple", "ok") : chip(v.resultado, "mal")]))}
      ${sug ? `<h3>Configuración que cumple</h3>${tabla(["Concepto", "Valor"], [["Conductores", `${sug.conductores_largo} × ${sug.conductores_ancho}`], ["Separación efectiva", fmt(sug.separacion_m, 2) + " m"], ["Varillas", `${sug.varillas}${sug.varillas_en_perimetro ? " en el perímetro" : ""}`], ["Rg", fmt(sug.Rg_ohm, 2) + " Ω"], ["Em / Es", `${fmt(sug.Em_V)} V / ${fmt(sug.Es_V)} V`]])}` : ""}
      ${(t.recomendaciones || []).length ? `<h3>Recomendaciones</h3><ul>${t.recomendaciones.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : ""}
      ${[...(t.criterios || []), ...(t.avisos || [])].length ? `<h3>Supuestos y avisos</h3><ul>${[...(t.criterios || []), ...(t.avisos || [])].map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : ""}
      <p class="nota">La resistencia real se mide en campo. <a href="/api/archivo?id=${encodeURIComponent(E.id)}&nombre=red-tierras.md&descargar=1">Descargar la memoria de la red de tierras</a></p></section>`;
  }
  function resMemoria(s) {
    if (!s.memoria) return "";
    const pend = (s.memoria.match(/\[(COMPLETAR|VERIFICAR|FALTA|SUPUESTO)/g) || []).length;
    return `<section class="tarjeta" id="res-memoria"><h2>Memoria de cálculo ${pend ? chip(pend + " por completar", "medio") : chip("Sin marcadores", "ok")}</h2>
      <p class="sub">Borrador preliminar. Los marcadores resaltados los completa Claude contigo; nada se inventa.</p>
      <p style="display:flex;gap:8px;flex-wrap:wrap">
        <a class="btn" href="/api/archivo?id=${encodeURIComponent(E.id)}&nombre=memoria-de-calculo.md&descargar=1">Descargar .md</a>
        <button class="btn" data-accion="abrir-carpeta">Abrir la carpeta del proyecto</button></p>
      <div class="memoria-vista">${markdown(s.memoria)}</div></section>`;
  }
  function resClaude(s) {
    const prompt = textoClaude(s);
    return `<section class="tarjeta" id="res-claude"><h2>Siguiente paso: revisión con Claude</h2>
      <p class="sub">Los scripts no aplican juicio de ingeniería. Pega esto en Claude Code, en esta misma carpeta:</p>
      <div class="prompt-claude" id="prompt-claude">${esc(prompt)}</div>
      <button class="btn primario" data-accion="copiar-prompt">Copiar</button>
      ${(s.bitacora && s.bitacora.comandos && s.bitacora.comandos.length) ? `<details style="margin-top:12px"><summary>Comandos para reproducir el cálculo</summary><pre class="prompt-claude">${esc(s.bitacora.comandos.join("\n"))}</pre></details>` : ""}
    </section>`;
  }
  function textoClaude() {
    const dir = `proyectos/${E.id}`;
    return `Revisa el proyecto eléctrico en ${dir}/. Lo capturé en la interfaz y ya corrí los cálculos; la bitácora con los pasos, los datos pendientes y los comandos está en ${dir}/bitacora.json.
1. Revisa los avisos y los datos pendientes de la bitácora y de los resultados.
2. Aplica lo que los scripts no hacen: factores de demanda (art. 220), motores (art. 430), aumento proporcional del EGC por caída de tensión (250.122(B)), alimentadores y acometida, GEC.
3. Completa los marcadores [COMPLETAR] de ${dir}/memoria-de-calculo.md sin inventar datos: lo que falte, pregúntamelo.
Usa los archivos de ${dir}/ (jurisdiccion.yaml, proyecto.yaml, cargas.csv, unifilar.json${E.modelo.tierras ? ", red-de-tierras.yaml" : ""}) en lugar de los de config/.`;
  }

  // ------------------------------------------------------------ Markdown mínimo (vista de la memoria)
  function markdown(md) {
    const L = md.replace(/\r/g, "").split("\n");
    const inline = (s) => esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\[(COMPLETAR|VERIFICAR|FALTA|SUPUESTO)([^\]]*)\]/g, '<span class="marcador">[$1$2]</span>');
    const celdas = (l) => l.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map((c) => c.replace(/\\\|/g, "|").trim());
    const esSep = (l) => /^[\s|:-]+$/.test(l) && l.includes("-");
    const bloque = /^(#{1,4}\s|\s*\||\s*>|\s*[-*]\s|\s*\d+\.\s)/;
    let html = "";
    let i = 0;
    while (i < L.length) {
      const l = L[i];
      let m;
      if (!l.trim()) { i++; continue; }
      if ((m = l.match(/^(#{1,4})\s+(.*)$/))) { const n = m[1].length; html += `<h${n}>${inline(m[2])}</h${n}>`; i++; continue; }
      if (/^\s*\|/.test(l)) {
        const filas = [];
        while (i < L.length && /^\s*\|/.test(L[i])) filas.push(L[i++]);
        const cabeza = celdas(filas[0]);
        const cuerpo = filas.slice(1).filter((f) => !esSep(f));
        html += `<div class="tabla-envoltura"><table><thead><tr>${cabeza.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${cuerpo.map((f) => `<tr>${celdas(f).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
        continue;
      }
      if (/^\s*>/.test(l)) {
        const b = [];
        while (i < L.length && /^\s*>/.test(L[i])) b.push(L[i++].replace(/^\s*>\s?/, ""));
        html += `<blockquote>${inline(b.join(" "))}</blockquote>`;
        continue;
      }
      if (/^\s*[-*]\s+/.test(l)) {
        const it = [];
        while (i < L.length && /^\s*[-*]\s+/.test(L[i])) it.push(L[i++].replace(/^\s*[-*]\s+/, ""));
        html += `<ul>${it.map((x) => `<li>${inline(x)}</li>`).join("")}</ul>`;
        continue;
      }
      if (/^\s*\d+\.\s+/.test(l)) {
        const it = [];
        while (i < L.length && /^\s*\d+\.\s+/.test(L[i])) it.push(L[i++].replace(/^\s*\d+\.\s+/, ""));
        html += `<ol>${it.map((x) => `<li>${inline(x)}</li>`).join("")}</ol>`;
        continue;
      }
      const p = [];
      while (i < L.length && L[i].trim() && !bloque.test(L[i])) p.push(L[i++]);
      if (!p.length) { p.push(L[i++]); }
      html += `<p>${p.map(inline).join("<br>")}</p>`;
    }
    return html;
  }

  // ------------------------------------------------------------ acciones
  const ACCIONES = {
    seccion: (el) => irSeccion(el.dataset.seccion),
    ir: (el) => irA(el.dataset.ref),
    "sel-nodo": (el) => { E.nodoSel = Number(el.dataset.i); render(); },
    "agregar-raiz": () => {
      nodos().push(nodoNuevo(nodos().some((n) => texto(n.tipo) === "acometida") ? "generador" : "acometida", ""));
      E.nodoSel = nodos().length - 1; marcarSucio(); render();
    },
    "agregar-hijo": (el) => {
      const padre = texto(nodos()[Number(el.dataset.i)].id);
      if (!padre) { toast("Primero ponle identificador a este nodo."); return; }
      nodos().push(nodoNuevo($("#tipo-hijo").value, padre));
      E.nodoSel = nodos().length - 1; marcarSucio(); render();
      const id = principal.querySelector(`[data-bind="unifilar.nodos.${E.nodoSel}.descripcion"]`);
      if (id) id.focus();
    },
    "borrar-nodo": (el) => {
      const i = Number(el.dataset.i);
      const lista = nodos();
      const id = texto(lista[i].id);
      const borrar = new Set([i]);
      let cambio = true;
      while (cambio) {
        cambio = false;
        lista.forEach((n, k) => {
          if (!borrar.has(k) && [...borrar].some((b) => texto(lista[b].id) && texto(n.padre) === texto(lista[b].id))) { borrar.add(k); cambio = true; }
        });
      }
      const extra = borrar.size - 1;
      if (!confirm(`¿Borrar ${id || "este nodo"}${extra ? ` y ${extra} nodo(s) que cuelgan de él` : ""}?`)) return;
      const padre = texto(lista[i].padre);
      E.modelo.unifilar.nodos = lista.filter((_, k) => !borrar.has(k));
      E.nodoSel = Math.max(0, nodos().findIndex((n) => texto(n.id) === padre));
      marcarSucio(); render();
    },
    "inicio-mt": () => {
      E.modelo.unifilar.nodos = [
        { id: "ACOM", tipo: "acometida", padre: "", descripcion: "Acometida en media tensión", tension_V: "", fases: "3", hilos: "3", notas: [] },
        { id: "TR-1", tipo: "transformador", padre: "ACOM", descripcion: "Transformador", tension_V: "", fases: "3", hilos: "4", kva: "", z_pct: "", conexion: "", notas: [] },
        { id: "TG-1", tipo: "tablero", padre: "TR-1", descripcion: "Tablero general", tension_V: "", fases: "3", hilos: "4", notas: [] },
      ];
      E.nodoSel = 0; marcarSucio(); render();
    },
    "inicio-bt": () => {
      E.modelo.unifilar.nodos = [
        { id: "ACOM", tipo: "acometida", padre: "", descripcion: "Acometida en baja tensión (CFE)", tension_V: "", fases: "3", hilos: "4", notas: [] },
        { id: "TG-1", tipo: "tablero", padre: "ACOM", descripcion: "Tablero general", tension_V: "", fases: "3", hilos: "4", notas: [] },
      ];
      E.nodoSel = 0; marcarSucio(); render();
    },
    "usar-suma": (el) => { fijar(`unifilar.nodos.${el.dataset.i}.carga_va`, el.dataset.valor); marcarSucio(); render(); },
    "agregar-carga": () => {
      E.modelo.cargas.push(cargaNueva()); marcarSucio(); render();
      const f = principal.querySelector(`[data-bind="cargas.${E.modelo.cargas.length - 1}.nombre"]`);
      if (f) f.focus();
    },
    "dup-carga": (el) => {
      const i = Number(el.dataset.i);
      const copia = { ...E.modelo.cargas[i], id: cargaNueva().id };
      E.modelo.cargas.splice(i + 1, 0, copia); marcarSucio(); render();
    },
    "borrar-carga": (el) => {
      const i = Number(el.dataset.i);
      const c = E.modelo.cargas[i];
      if ((texto(c.nombre) || texto(c.va)) && !confirm(`¿Borrar ${texto(c.id) || "la fila"}${texto(c.nombre) ? " — " + texto(c.nombre) : ""}?`)) return;
      E.modelo.cargas.splice(i, 1);
      if (!E.modelo.cargas.length) E.modelo.cargas.push(cargaNueva());
      marcarSucio(); render();
    },
    "rellenar-tensiones": () => {
      let n = 0;
      for (const c of E.modelo.cargas) {
        const s = tensionSugerida(c);
        if (s && !texto(c.tension)) { c.tension = String(s); n++; }
      }
      toast(n ? `${n} tensión(es) llenadas según el tablero y la conexión. Revísalas.` : "No hay tensiones vacías con tablero y conexión declarados.");
      if (n) { marcarSucio(); render(); }
    },
    pegar: () => { $("#texto-pegar").value = ""; $("#vista-pegar").textContent = ""; $("#dlg-pegar").showModal(); },
    "toggle-tierras": (el) => {
      if (el.checked) {
        const t = JSON.parse(JSON.stringify((E.inicio && E.inicio.tierras_plantilla) || {}));
        t.proyecto = texto(E.modelo.proyecto.proyecto);
        const acom = nodos().find((n) => texto(n.tipo) === "acometida" && num(n.tension_V) > 1000);
        if (acom) { t.suministrador = t.suministrador || {}; t.suministrador.tension_kV = String(num(acom.tension_V) / 1000); }
        E.modelo.tierras = t;
      } else {
        if (!confirm("¿Quitar la red de tierras? Se borra red-de-tierras.yaml del proyecto.")) { el.checked = true; return; }
        E.modelo.tierras = null;
      }
      marcarSucio(); render();
    },
    "ka-mva": (el) => {
      const ka = num($("#ka-convertir").value);
      const kv = num(obtener("tierras.suministrador.tension_kV"));
      if (!ka || !kv || Number.isNaN(ka) || Number.isNaN(kv)) { toast("Escribe los kA y la tensión en kV."); return; }
      fijar(el.dataset.destino, String(Math.round(Math.sqrt(3) * kv * ka * 10) / 10));
      marcarSucio(); render();
    },
    calcular: () => calcular(),
    "copiar-prompt": async () => {
      try { await navigator.clipboard.writeText(textoClaude()); toast("Copiado. Pégalo en Claude Code."); }
      catch { toast("No se pudo copiar; selecciona el texto y cópialo."); }
    },
    "abrir-carpeta": () => abrirCarpeta(),
    recargar: () => cargarProyecto(E.id),
    forzar: () => { E.conflicto = null; guardar({ forzar: true }); },
  };

  document.addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-accion]");
    if (el && ACCIONES[el.dataset.accion]) {
      if (el.tagName === "A" || el.tagName === "LI") ev.preventDefault();
      if (el.type === "checkbox") { ACCIONES[el.dataset.accion](el); return; }
      ev.preventDefault();
      ACCIONES[el.dataset.accion](el);
      return;
    }
    const s = ev.target.closest("[data-seccion]");
    if (s && nav.contains(s)) irSeccion(s.dataset.seccion);
  });
  document.addEventListener("keydown", (ev) => {
    if ((ev.key === "Enter" || ev.key === " ") && ev.target.matches && ev.target.matches("li[data-accion]")) {
      ev.preventDefault();
      ACCIONES[ev.target.dataset.accion](ev.target);
    }
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "s") { ev.preventDefault(); guardarAhora(); }
  });

  principal.addEventListener("input", (ev) => {
    const t = ev.target;
    const ruta = t.dataset && t.dataset.bind;
    if (!ruta || !E.modelo) return;
    let v;
    if (t.type === "radio") { if (!t.checked) return; v = t.value; }
    else if (t.type === "checkbox") v = t.checked;
    else if (t.dataset.lista) v = t.value.split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
    else v = t.value;
    fijar(ruta, v);
    marcarSucio();
    if (t.dataset.vivo === "tension") {
      const i = ruta.split(".")[1];
      const p = principal.querySelector(`[data-pista="${i}"]`);
      if (p) p.textContent = pistaTension(E.modelo.cargas[i]);
    }
  });
  principal.addEventListener("change", (ev) => {
    const t = ev.target;
    if (!t.dataset) return;
    if (t.dataset.idNodo !== undefined) {
      const anterior = t.dataset.anterior;
      const nuevo = texto(t.value);
      if (anterior && nuevo && anterior !== nuevo) {
        for (const n of nodos()) if (texto(n.padre) === anterior) n.padre = nuevo;
        for (const c of E.modelo.cargas) if (texto(c.tablero) === anterior) c.tablero = nuevo;
        marcarSucio();
      }
    }
    if (t.dataset.rerender) render();
  });

  // ------------------------------------------------------------ pegar desde Excel
  const SINONIMOS = {
    id: "id", circuito: "id", clave: "id", nombre: "nombre", descripcion: "nombre", equipo: "nombre",
    va: "va", carga: "va", "carga va": "va", potencia: "va", tension: "tension", voltaje: "tension", v: "tension",
    fases: "fases", conexion: "fases", polos: "fases", fase: "fase", continua: "continua", longitud: "longitud_m",
    longitud_m: "longitud_m", "longitud m": "longitud_m", distancia: "longitud_m", n_conductores: "n_conductores",
    conductores: "n_conductores", material: "material", ambiente: "ambiente_c", ambiente_c: "ambiente_c",
    tablero: "tablero", notas: "notas", observaciones: "notas",
  };
  const ORDEN_PEGAR = ["id", "nombre", "tablero", "fases", "tension", "va", "continua", "longitud_m"];
  const sinAcentos = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\(.*?\)/g, "").trim();
  function interpretarPegado(txt) {
    const lineas = txt.replace(/\r/g, "").split("\n").filter((l) => l.trim());
    if (!lineas.length) return [];
    const sep = lineas[0].includes("\t") ? "\t" : lineas[0].includes(";") ? ";" : ",";
    const partir = (l) => l.split(sep).map((x) => x.trim());
    let columnas = ORDEN_PEGAR;
    const primera = partir(lineas[0]).map(sinAcentos);
    if (primera.filter((c) => SINONIMOS[c]).length >= 2) { columnas = primera.map((c) => SINONIMOS[c] || null); lineas.shift(); }
    return lineas.map((l) => {
      const f = cargaNueva();
      f.tablero = "";
      partir(l).forEach((v, k) => {
        const col = columnas[k];
        if (!col) return;
        let x = v;
        if (["va", "tension", "longitud_m", "n_conductores", "ambiente_c"].includes(col)) {
          if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(x)) x = x.replace(/,/g, "");
          x = x.replace(/\s*(va|v|m|°c)$/i, "");
        }
        if (col === "continua") x = /^(s|si|sí|x|yes|1|true)$/i.test(x) ? "si" : /^(n|no|0|false)$/i.test(x) ? "no" : "";
        if (col === "fases") { const m = x.match(/[123]/); x = m ? m[0] : ""; }
        if (col === "material") x = /^al/i.test(x) ? "aluminio" : /^(cu|co)/i.test(x) ? "cobre" : "";
        if (col === "fase") x = x.toUpperCase().replace(/[^ABC]/g, "");
        f[col] = x;
      });
      return f;
    });
  }
  $("#texto-pegar").addEventListener("input", () => {
    const filas = interpretarPegado($("#texto-pegar").value);
    $("#vista-pegar").textContent = filas.length ? `${filas.length} fila(s): ${filas.slice(0, 3).map((f) => `${f.id} ${f.nombre}`.trim()).join(" · ")}${filas.length > 3 ? " …" : ""}` : "";
  });
  $("#dlg-pegar").addEventListener("close", () => {
    if ($("#dlg-pegar").returnValue !== "pegar") return;
    const filas = interpretarPegado($("#texto-pegar").value);
    if (!filas.length) return;
    const usados = new Set(E.modelo.cargas.map((c) => texto(c.id)));
    E.modelo.cargas = E.modelo.cargas.filter((c) => Object.values(c).some((v) => texto(v)) && !(Object.keys(c).length && !texto(c.nombre) && !texto(c.va) && !texto(c.tension)));
    for (const f of filas) {
      if (!texto(f.id) || usados.has(texto(f.id))) f.id = cargaNueva().id;
      usados.add(texto(f.id));
      E.modelo.cargas.push(f);
    }
    toast(`${filas.length} fila(s) agregadas. Revisa las marcadas en rojo.`);
    marcarSucio(); render();
  });

  // ------------------------------------------------------------ proyecto, cálculo
  function botonCalcular() {
    const b = $("#btn-calcular");
    b.disabled = !E.id || E.calculando;
    b.innerHTML = E.calculando ? '<span class="cargando"></span> Calculando…' : "Calcular";
  }
  async function calcular() {
    if (!E.id || E.calculando) return;
    await guardarAhora();
    if (E.conflicto) { toast("Primero resuelve el conflicto de versiones."); return; }
    if (E.sucio) { toast("No se pudieron guardar tus cambios; no se calcula con datos viejos."); return; }
    E.calculando = true;
    botonCalcular();
    if (E.seccion === "resultados") render();
    try {
      const r = await api("/api/calcular", { id: E.id });
      E.salidas = r.salidas;
      E.version = r.version;
      E.seccion = "resultados";
      try { history.replaceState(null, "", "#resultados"); } catch { /* sin historial */ }
    } catch (e) {
      toast("No se pudo calcular: " + e.message);
    } finally {
      E.calculando = false;
      render();
      window.scrollTo(0, 0);
    }
  }
  async function abrirCarpeta() {
    if (!E.id) return;
    try { await api("/api/abrir", { id: E.id }); } catch (e) { toast("No se pudo abrir: " + e.message); }
  }
  function renderSelector() {
    const sel = $("#sel-proyecto");
    const lista = (E.inicio && E.inicio.proyectos) || [];
    sel.innerHTML = lista.map((p) => `<option value="${esc(p.id)}" ${p.id === E.id ? "selected" : ""}>${esc(p.nombre)}</option>`).join("");
    sel.disabled = !lista.length;
  }
  async function cargarProyecto(id) {
    const r = await api("/api/proyecto?id=" + encodeURIComponent(id));
    Object.assign(E, { id: r.id, modelo: r.modelo, version: r.version, hallazgos: r.hallazgos, salidas: r.salidas,
      carpeta: r.carpeta || "", conflicto: null, sucio: false, nodoSel: 0 });
    normalizarModelo();
    pref.guardar("ultimo", id);
    renderSelector();
    render();
    estadoGuardado("Guardado");
  }
  async function refrescarLista() {
    E.inicio = await api("/api/inicio");
    renderSelector();
  }
  function renderBienvenida() {
    nav.innerHTML = "";
    principal.innerHTML = `<section class="tarjeta vacio" style="max-width:720px;margin:40px auto">
      <h2>Empecemos un proyecto</h2>
      <p>Capturas los datos una vez; la interfaz escribe los archivos que usan los scripts del agente, los corre y te muestra los resultados.</p>
      <ol style="text-align:left;display:inline-block;margin:10px auto 18px">
        <li>Proyecto y alcance</li><li>Norma, edición y datos del sitio</li><li>Unifilar: acometida, transformadores y tableros</li>
        <li>Cuadro de cargas</li><li>Red de tierras, si hay subestación propia</li><li>Calcular y revisar con Claude</li></ol>
      <div><button class="btn primario" id="btn-bienvenida">Crear proyecto</button></div></section>`;
    $("#btn-bienvenida").addEventListener("click", () => $("#dlg-nuevo").showModal());
    botonCalcular();
  }

  $("#sel-proyecto").addEventListener("change", async (ev) => {
    const id = ev.target.value;
    await guardarAhora();
    await cargarProyecto(id);
  });
  $("#btn-nuevo").addEventListener("click", () => { $("#nuevo-nombre").value = ""; $("#dlg-nuevo").showModal(); });
  // Enter en el nombre crea el proyecto (el botón por omisión del formulario sería Cancelar).
  $("#nuevo-nombre").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") { ev.preventDefault(); $("#btn-crear").click(); }
  });
  $("#btn-calcular").addEventListener("click", () => calcular());
  $("#btn-carpeta").addEventListener("click", () => abrirCarpeta());
  $("#dlg-nuevo").addEventListener("close", async () => {
    if ($("#dlg-nuevo").returnValue !== "crear") return;
    const nombre = $("#nuevo-nombre").value.trim();
    if (!nombre) return;
    const origen = ($("#form-nuevo").querySelector("input[name=origen]:checked") || {}).value || "vacio";
    try {
      await guardarAhora();
      const r = await api("/api/nuevo", { nombre, origen });
      await refrescarLista();
      E.seccion = "proyecto";
      await cargarProyecto(r.id);
      toast(origen === "demo" ? "Proyecto creado desde el demo. Completa Norma y sitio para calcular." : "Proyecto creado.");
    } catch (e) { toast("No se pudo crear: " + e.message); }
  });
  window.addEventListener("beforeunload", (ev) => {
    if (E.sucio || E.guardando) { guardar(); ev.preventDefault(); ev.returnValue = ""; }
  });

  async function inicio() {
    const [hash, ancla] = location.hash.replace("#", "").split("/");
    if (SECCIONES.some((s) => s.clave === hash)) E.seccion = hash;
    E.inicio = await api("/api/inicio");
    const lista = E.inicio.proyectos;
    if (!lista.length) { renderSelector(); renderBienvenida(); return; }
    const pedido = new URLSearchParams(location.search).get("p");
    const ultimo = pref.leer("ultimo");
    const id = lista.some((p) => p.id === pedido) ? pedido : lista.some((p) => p.id === ultimo) ? ultimo : lista[0].id;
    await cargarProyecto(id);
    const destino = ancla && document.getElementById("res-" + ancla);
    if (destino) destino.scrollIntoView();
  }
  inicio().catch((e) => {
    principal.innerHTML = `<div class="banner error">No se pudo conectar con el servidor local: ${esc(e.message)}. ¿Sigue corriendo <span class="mono">python scripts/interfaz.py</span>?</div>`;
  });
})();
