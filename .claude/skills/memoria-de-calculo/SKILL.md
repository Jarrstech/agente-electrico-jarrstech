---
name: memoria-de-calculo
description: Redacta la memoria de cálculo eléctrico completa y firmable — datos del proyecto, bases normativas, criterios y supuestos, cuadro de cargas, cálculo de conductores, protecciones, puesta a tierra, caída de tensión, tableros, anexos y hoja de firmas. Úsala siempre que el usuario pida memoria de cálculo, memoria técnica, memoria descriptiva, cálculo justificativo, documento para UVIE, expediente de verificación, o entregable para revisión/permiso. También cuando ya se hicieron cálculos y toca documentarlos. Es el paso 8 del flujo maestro.
---

# Memoria de cálculo

Es el entregable que se firma y el que revisa el verificador. Un cálculo
correcto sin memoria trazable no se aprueba; una memoria bien estructurada
sobrevive al cambio de personal y a la auditoría.

Plantilla base: `plantillas/memoria-de-calculo.md`.

## Estructura obligatoria

1. **Portada y datos del proyecto** — cliente, ubicación, tipo de instalación,
   número de revisión, fecha, responsable técnico.
2. **Objeto y alcance** — qué cubre y, explícitamente, **qué no cubre**. El
   alcance negativo protege tanto como el positivo.
3. **Bases normativas** — norma y **edición exacta**, más normas concurrentes.
   Se toma de `config/jurisdiccion.yaml`.
4. **Criterios y supuestos de diseño** — sección crítica. Aquí van: temperatura
   ambiente, temperatura de terminales, material y aislamiento, límites de caída
   de tensión, factores de demanda aplicados y su justificación, margen de
   crecimiento, Icc de diseño y su origen. **Todo supuesto se marca como tal y
   se identifica quién debe confirmarlo.**
5. **Descripción de la instalación** — acometida, arquitectura de tensiones,
   jerarquía de tableros, referencia al unifilar.
6. **Cuadro de cargas** — por tablero: carga instalada, demanda máxima,
   balanceo, factores aplicados.
7. **Cálculo de conductores** — por circuito, mostrando el procedimiento
   completo, no solo el resultado. Incluir al menos un cálculo desarrollado paso
   a paso como ejemplo y el resto en tabla.
8. **Cálculo de protecciones** — capacidad, tipo, capacidad interruptiva, y la
   verificación de SCCR contra Icc.
9. **Caída de tensión** — por circuito y acumulada hasta la carga más lejana.
10. **Puesta a tierra** — GEC, EGC, sistema de electrodos, punto de unión, y
    resistencia objetivo con el método de medición.
11. **Especificación de tableros** — la ficha completa de cada uno.
12. **Conclusiones** — cumplimiento, limitaciones, y qué queda pendiente de
    verificar en campo.
13. **Anexos** — CSV de cargas, JSON y SVG del unifilar, salida cruda de
    `ec.py`, catálogos.
14. **Hoja de firmas** — responsable del cálculo, revisor, y el espacio del
    responsable técnico con licencia.

## Reglas de redacción

**Mostrar el procedimiento.** El verificador necesita reproducir el número. Un
cálculo desarrollado se ve así:

> **Circuito C-01 — Horno rotatorio, 45 000 VA, 480 V, 3F, carga continua**
>
> Corriente de carga: I = 45 000 / (√3 × 480) = 54.1 A
> Corriente de diseño (continua, ×1.25): 67.7 A
> Conductor 4 AWG Cu, aislamiento 90 °C, ambiente 40 °C, 3 conductores:
> ampacidad de tabla 95 A × 0.91 (temp.) × 1.00 (agrup.) = 86.5 A
> Límite por terminal a 75 °C: 85 A → **gobierna el terminal** (110.14(C))
> Ampacidad utilizable 85 A ≥ 67.7 A → **cumple**
> Caída de tensión, 62 m: 1.22 % ≤ 3 % → **cumple**
> Protección: 70 A. EGC: 8 AWG Cu (Tabla 250.122).

**Citar artículo y edición en cada criterio.** "Según la norma" no es una cita.

**Separar requisito de criterio.** Marcar visiblemente cuáles límites son
obligatorios y cuáles son decisiones de proyecto.

**No maquillar los supuestos.** Si la temperatura ambiente se asumió, la memoria
lo dice. Un verificador que descubre un supuesto oculto desconfía de todo el
documento.

## Generación

```bash
python3 scripts/ec.py circuito --archivo cargas.csv --unifilar unifilar.json --salida resultados.json
python3 scripts/ec.py cortocircuito --json unifilar.json --salida cortocircuito.json
python3 scripts/squared.py --unifilar unifilar.json --cortocircuito cortocircuito.json \
        --resultados resultados.json --salida squared.json --reporte squared.md
python3 scripts/red_tierras.py --entrada config/red-de-tierras.yaml \
        --salida red-tierras.json --reporte red-tierras.md
python3 scripts/memoria.py --proyecto config/proyecto.yaml --jurisdiccion config/jurisdiccion.yaml \
        --resultados resultados.json --cortocircuito cortocircuito.json \
        --squared squared.json --tierras red-tierras.json --salida memoria.md
```

Con esas entradas la memoria llena, además del cuadro de cargas y los
conductores: la cédula y el balanceo por tablero, la Icc por bus infinito y la
verificación de SCCR (sección 7), el resumen de la red de tierras (sección 8,
con su memoria separada como anexo) y el equipo Square D (sección 9).

Luego revisar y completar a mano las secciones de criterio, descripción y
conclusiones — esas requieren juicio de ingeniería, no plantilla.

Para entregar en Word o PDF, convertir el markdown resultante (pandoc, o la
skill `docx` si está disponible en el entorno).

## Control de revisiones

Cada emisión lleva letra o número de revisión, fecha y una tabla de cambios
respecto a la anterior. Los cálculos se rehacen y se vuelven a correr; **no se
editan a mano los resultados de una revisión previa**. Si cambia un dato de
entrada, se corre el script de nuevo y se compara el diff.

## Antes de entregar

- [ ] Todo número trazable a un script o a una tabla citada
- [ ] Edición normativa declarada y consistente en todo el documento
- [ ] Supuestos listados, marcados, y con responsable de confirmación
- [ ] Unifilar validado sin errores y coincidente con el cuadro de cargas
- [ ] Identificadores consistentes entre unifilar, cuadro y memoria
- [ ] SCCR verificado contra Icc en cada nivel
- [ ] Alcance negativo escrito
- [ ] Nota de que el documento requiere revisión y firma de responsable con
      licencia vigente
