# Memoria de cálculo eléctrico

**Proyecto:** [COMPLETAR]  
**Cliente:** [COMPLETAR]  
**Ubicación:** [COMPLETAR]  
**Tipo de instalación:** [COMPLETAR]  
**Revisión:** A  
**Fecha:** 2026-09-23

> **Documento preliminar.** Requiere revisión, validación y firma de un responsable técnico con licencia vigente antes de su emisión o uso para permiso, construcción o verificación.

## 1. Objeto y alcance

[COMPLETAR: qué cubre esta memoria]

**No incluye:** [COMPLETAR — el alcance negativo es obligatorio]

## 2. Bases normativas

- Norma base: **NOM-001-SEDE, Instalaciones Electricas (utilizacion)**
- Edición aplicable: **[COMPLETAR — OBLIGATORIO]**
- Unidad de Verificación: [COMPLETAR]
- Edición confirmada el: [COMPLETAR]
- Fuente consultada: [COMPLETAR]
- Red de tierras: IEEE Std 80 (método de suelo uniforme)

- Normas concurrentes aplicables: [COMPLETAR según el proyecto]

## 3. Criterios y supuestos de diseño

Los criterios marcados como **[CRITERIO]** son decisiones de proyecto, no requisitos normativos. Los marcados **[SUPUESTO]** requieren confirmación antes de la firma.

| Parámetro | Valor | Tipo | Origen |
|---|---|---|---|
| Temperatura ambiente de diseño | [SUPUESTO 30 °C] | Dato de sitio | **Confirmar** |
| Temperatura de terminales | 75 °C | Dato de equipo | Placa del equipo real |
| Material del conductor | cobre | [CRITERIO] | Proyecto |
| Aislamiento | 90 °C | [CRITERIO] | Proyecto |
| Caída de tensión, derivado | 3.0 % | [CRITERIO] | Nota informativa de la norma |
| Caída de tensión, alimentador | 2.0 % | [CRITERIO] | Nota informativa de la norma |
| Margen de crecimiento | 25 % | [CRITERIO] | Proyecto |
| Desbalance máximo | 5 % | [CRITERIO] | Proyecto |
| Icc de diseño | Calculada por bus infinito en cada tablero (sección 7.1) | [CRITERIO] | kVA y Z% de placa de los transformadores |

## 4. Descripción de la instalación

[COMPLETAR: acometida, arquitectura de tensiones, jerarquía de tableros. Referir al diagrama unifilar del Anexo B.]

## 5. Cuadro de cargas

Conexión: F-N = fase-neutro (1 polo), F-F = fase-fase (2 polos), 3F = trifásica (3 polos).

| ID | Descripción | Tablero | VA | V | Conexión | Continua | I carga (A) | I diseño (A) |
|---|---|---|---|---|---|---|---|---|
| C-01 | Horno rotatorio principal | TD-1 | 45,000 | 480 | 3F | Sí | 54.1 | 67.7 |
| C-02 | Amasadora 15 HP | TD-1 | 14,000 | 480 | 3F | No | 16.8 | 16.8 |
| C-03 | Camara de fermentacion | TD-1 | 9,000 | 480 | 3F | Sí | 10.8 | 13.5 |
| C-04 | Alumbrado nave LED | TD-1 | 6,200 | 277 | F-N | Sí | 22.4 | 28.0 |
| C-05 | Contactos generales area produccion | TD-2 | 5,400 | 208 | F-F | No | 26.0 | 26.0 |
| C-06 | Compresor de aire 10 HP | TD-1 | 8,500 | 480 | 3F | No | 10.2 | 10.2 |
| C-07 | Cargador VE nivel 2 | TD-2 | 11,500 | 208 | F-F | Sí | 55.3 | 69.1 |
| C-08 | Aire acondicionado oficinas | TD-2 | 7,200 | 208 | F-F | Sí | 34.6 | 43.3 |

**Carga instalada total:** 106,800 VA
**Demanda máxima:** [COMPLETAR — aplicar factores de demanda y justificar cuáles]

### 5.1 Balanceo de fases por tablero

Barras Square D: nones a la izquierda, pares a la derecha; renglones 1-2 fase A, 3-4 fase B, 5-6 fase C y se repite (NEC 408.3(E)). 1 polo: toda la carga en su fase; 2 polos: mitad en cada fase; 3 polos: un tercio en cada fase.

**TD-1** — desbalance 22.49 % (criterio de proyecto: ≤ 5 %)

| Posición | Circuito | Polos | Conexión | Fases | VA A | VA B | VA C |
|---|---|---|---|---|---|---|---|
| 1 | C-04 | 1 | F-N | A | 6,200 |  |  |
| 2-4-6 | C-01 | 3 | 3F | A-B-C | 15,000 | 15,000 | 15,000 |
| 3-5-7 | C-02 | 3 | 3F | B-C-A | 4,667 | 4,667 | 4,667 |
| 8-10-12 | C-03 | 3 | 3F | A-B-C | 3,000 | 3,000 | 3,000 |
| 9-11-13 | C-06 | 3 | 3F | B-C-A | 2,833 | 2,833 | 2,833 |
|  | **Total** |  |  |  | **31,700** | **25,500** | **25,500** |

**TD-2** — desbalance 37.97 % (criterio de proyecto: ≤ 5 %)

| Posición | Circuito | Polos | Conexión | Fases | VA A | VA B | VA C |
|---|---|---|---|---|---|---|---|
| 2-4 | C-07 | 2 | F-F | A-B | 5,750 | 5,750 |  |
| 3-5 | C-05 | 2 | F-F | B-C |  | 2,700 | 2,700 |
| 6-8 | C-08 | 2 | F-F | C-A | 3,600 |  | 3,600 |
|  | **Total** |  |  |  | **9,350** | **8,450** | **6,300** |

## 6. Cálculo de conductores

### 6.1 Cálculo desarrollado (ejemplo)

**Circuito C-01 — Horno rotatorio principal**

```
Carga:                45,000 VA, 480.0 V, trifasica, continua
Corriente de carga:   54.1 A
Corriente de diseño:  67.7 A  (x1.25 por carga continua)
Conductor propuesto:  4 cobre, aislamiento 90 °C
Ampacidad de tabla:   95 A
Factor temperatura:   x 1.0
Factor agrupamiento:  x 1.0
Ampacidad corregida:  95.0 A
Límite por terminal:  85 A a 75 °C
Regla que gobierna:   110.14(C) terminal
Ampacidad utilizable: 85 A  ->  CUMPLE
Caída de tensión:     1.22 % en 62.0 m
Calibre final:        4
```

### 6.2 Resumen por circuito

| ID | Calibre | Material | EGC | Protección (A) | Long. (m) | Δ V (%) |  |
|---|---|---|---|---|---|---|---|
| C-01 | 4 | cobre | 8 | 70 | 62.0 | 1.22 |  |
| C-02 | 12 | cobre | 12 | 20 | 38.0 | 1.5 |  |
| C-03 | 14 | cobre | 14 | 15 | 25.0 | 1.01 |  |
| C-04 | 6 | cobre | 10 | 30 | 95.0 | 6.25 | ⚠ |
| C-05 | 8 | cobre | 10 | 30 | 45.0 | 4.57 | ⚠ |
| C-06 | 14 | cobre | 14 | 15 | 55.0 | 2.09 |  |
| C-07 | 2 | cobre | 8 | 70 | 72.0 | 3.87 | ⚠ |
| C-08 | 6 | cobre | 10 | 45 | 40.0 | 3.39 | ⚠ |

### 6.3 Observaciones

- **C-04:** Caida 6.25% > 3.0%. Se aumenta a 6 (2.47%). Aplicar 250.122(B): aumentar el EGC proporcionalmente.
- **C-05:** Caida 4.57% > 3.0%. Se aumenta a 8 (2.86%). Aplicar 250.122(B): aumentar el EGC proporcionalmente.
- **C-07:** Caida 3.87% > 3.0%. Se aumenta a 2 (2.43%). Aplicar 250.122(B): aumentar el EGC proporcionalmente.
- **C-08:** Caida 3.39% > 3.0%. Se aumenta a 6 (2.14%). Aplicar 250.122(B): aumentar el EGC proporcionalmente.

## 7. Protecciones

| ID | Capacidad (A) | Polos | Tipo | Cap. interruptiva (kA) |
|---|---|---|---|---|
| C-01 | 70 | 3 | EDB (EDB34070) | 18 |
| C-02 | 20 | 3 | EDB (EDB34020) | 18 |
| C-03 | 15 | 3 | EDB (EDB34015) | 18 |
| C-04 | 30 | 1 | EDB (EDB14030) | 18 |
| C-05 | 30 | 2 | QOB (QOB230) | 10 |
| C-06 | 15 | 3 | EDB (EDB34015) | 18 |
| C-07 | 70 | 2 | QOB (QOB270) | 10 |
| C-08 | 45 | 2 | QOB (QOB245) | 10 |

Tipo y capacidad interruptiva: sugerencia Square D de la sección 9.1.

### 7.1 Corriente de cortocircuito (método del bus infinito)

Icc secundario = kVA x 1000 / (raiz(3) x V x Z%/100); aguas abajo Icc = V / (raiz(3) x |Z acumulada|).

| Nodo | Tipo | V sistema | Z (Ω) | Icc sim. (kA) | Aporte (kA) | Icc total (kA) | SCCR (kA) | Verificación |
|---|---|---|---|---|---|---|---|---|
| ACOM | acometida | 13800 | 0.0 | ∞ | 0.0 | ∞ | — | BUS INFINITO (sin impedancia aguas arriba) |
| TR-1 | transformador | 480 | 0.0384 | 7.22 | 0.22 | 7.44 | 65 | CUMPLE |
| TG-1 | tablero | 480 | 0.038402 | 7.22 | 0.22 | 7.44 | 65 | CUMPLE |
| TD-1 | tablero | 480 | 0.039211 | 7.07 | 0.22 | 7.29 | 42 | CUMPLE |
| TR-2 | transformador | 208 | 0.027401 | 4.38 | 0.0 | 4.38 | 22 | CUMPLE |
| TD-2 | tablero | 208 | 0.027613 | 4.35 | 0.0 | 4.35 | 22 | CUMPLE |
| EVSE-1 | cargador_ve | 208 | 0.04999 | 2.4 | 0.0 | 2.4 | — |  |
| BESS-1 | bess | 480 | 0.039234 | 7.06 | 0.22 | 7.28 | 65 | CUMPLE |
| M-01 | motor | 480 | 0.071604 | 3.87 | 0.22 | 4.09 | — |  |

**Supuestos del cálculo:**

- La red del suministrador tiene potencia de cortocircuito infinita (impedancia cero).
- Resistencia de conductores a 25 C y reactancia cero, salvo 'reactancia_ohm_km' declarada en el nodo (resultado conservador).
- Transformador sin 'x_r' declarado: impedancia puramente reactiva (resultado conservador).
- Aporte de motores: 4 x corriente nominal, sumado a todo su sistema (Eaton Bussmann, metodo punto a punto).
- BESS, fotovoltaico, generador y UPS aportan lo que declare 'aporte_icc_kA' (dato del fabricante).
- Falla trifasica franca y simetrica; la falla fase-fase es 0.866 veces la trifasica.
- **Aviso:** icc_disponible_kA del diagrama no se usa: el metodo de bus infinito supone impedancia cero del suministrador.
- **Aviso:** BESS-1 (bess): falta 'aporte_icc_kA', la corriente de falla que aporta segun el fabricante. La Icc de su sistema no la incluye.

### 7.2 Verificación de SCCR

Todos los tableros y equipos con SCCR declarado cumplen contra la Icc calculada en su punto.

## 8. Puesta a tierra y unión

- Conductor del electrodo de puesta a tierra (GEC): [COMPLETAR — `ec.py gec`]
- Punto único de unión neutro-tierra: [COMPLETAR]
- EGC por circuito: ver tabla 6.2
- Red de tierras (memoria separada, Anexo E): malla de 20.0 × 15.0 m, conductor 4/0, 4 varillas; Rg = 1.503 Ω; Em = 969 V contra 735 V tolerables; Es = 661 V contra 2,447 V. Resultado: **NO CUMPLE**.
- Configuración que cumple: separación 3.17 m y 4 varillas (Rg = 1.415 Ω, Em = 664 V).
- Resistencia objetivo y método de medición: [COMPLETAR]

[Si algún conductor de fase se aumentó de calibre, verificar el aumento proporcional del EGC.]

## 9. Especificación de tableros

### 9.1 Equipo sugerido — Square D

> Datos de catalogo de referencia. Confirmar numero de catalogo, disponibilidad (Mexico / EE. UU.) y capacidades con el distribuidor o el catalogo vigente de Schneider Electric antes de cotizar. La seleccion usa interruptores totalmente clasificados (sin combinaciones en serie). Los valores marcados en '_verificar' vienen de fuentes secundarias.

| Tablero | Sistema | Icc (kA) | Familia | Barras (A) | Principal | Espacios mín. | SCCR (kA) |
|---|---|---|---|---|---|---|---|
| TG-1 | 480Y/277 V 3F-4H | 7.44 | I-Line | 400 | PowerPact L, nivel G, disparo electronico MicroLogic, 400 A, 3 polos, 35 kA a 480 V | — | 18 |
| TD-1 | 480Y/277 V 3F-4H | 7.29 | NF | 250 | PowerPact J, nivel D, 225 A, 3 polos, 18 kA a 480 V | 18 | 18 |
| TD-2 | 208Y/120 V 3F-4H | 4.35 | NQ | 225 | Interruptor principal NQ de 225 A | 8 | 10 |

Envolvente NEMA, barra de tierra, neutro aislado en tableros derivados y directorio: [COMPLETAR por tablero]. Interruptores por circuito: Anexo G.

## 10. Conclusiones

[COMPLETAR: cumplimiento, limitaciones, pendientes de verificación en campo.]

## 11. Supuestos pendientes de confirmación

| # | Supuesto | Valor usado | Quién confirma | Estatus |
|---|----------|-------------|----------------|---------|
| 1 | [COMPLETAR] | | | Pendiente |

## 12. Anexos

- Anexo A: cuadro de cargas (`cargas.csv`)
- Anexo B: diagrama unifilar (`unifilar.json` / `unifilar.svg`)
- Anexo C: salida de cálculo (`resultados.json`)
- Anexo D: hojas de datos y certificados de listado
- Anexo E: memoria de la red de tierras (`red-tierras.md`, `red-tierras.json`)
- Anexo F: cálculo de cortocircuito (`cortocircuito.json`)
- Anexo G: tableros e interruptores sugeridos Square D (`squared.md`, `squared.json`)

## 13. Firmas

| Rol | Nombre | Licencia/Cédula | Firma | Fecha |
|---|---|---|---|---|
| Elaboró |  |  |  |  |
| Revisó |  |  |  |  |
| Responsable técnico |  |  |  |  |