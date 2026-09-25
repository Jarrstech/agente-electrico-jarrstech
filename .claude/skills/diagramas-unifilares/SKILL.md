---
name: diagramas-unifilares
description: Lee, interpreta, edita, valida y renderiza diagramas unifilares eléctricos usando un modelo JSON versionable y un render SVG. Úsala siempre que el usuario mencione unifilar, diagrama unifilar, one-line, single-line, SLD, diagrama eléctrico, esquema de distribución, o suba/describa un diagrama para revisar, ampliar o corregir. También cuando pida agregar un tablero, un BESS, un cargador de VE o un transformador a una instalación existente, porque eso es una edición de unifilar. Detecta coordinación invertida, SCCR insuficiente, carga que excede capacidad y tierras faltantes.
---

# Diagramas unifilares

## Principio: el diagrama es un dato, no un dibujo

La fuente de verdad es un **JSON** (`unifilar.json`) que se versiona en git, se
valida automáticamente y se diffea. El SVG es una vista generada. **Nunca editar
el SVG a mano** — se regenera y se pierde el cambio.

Esto es lo que hace al diagrama auditable: cada revisión es un diff legible, y
cada cambio pasa por el validador antes de emitirse.

```bash
python3 scripts/unifilar.py describir --json unifilar.json   # jerarquía en texto
python3 scripts/unifilar.py validar   --json unifilar.json   # código 1 si hay ERROR
python3 scripts/unifilar.py validar   --json unifilar.json --cortocircuito cortocircuito.json
python3 scripts/unifilar.py render    --json unifilar.json --svg unifilar.svg
python3 scripts/unifilar.py agregar   --json unifilar.json --padre TG-1 --id TD-3 \
        --tipo tablero --descripcion "Tablero oficinas" --tension 208 --fases 3 \
        --interruptor 100 --calibre 3 --egc 8 --sccr 22
```

Esquema completo del modelo: `referencias/esquema-unifilar.md`.

## Leer un diagrama que da el usuario

Si llega como imagen o PDF, **transcribirlo al JSON primero**. Al transcribir,
extraer por cada elemento: identificador, tipo, padre, tensión, fases/hilos,
capacidad de interruptor, calibre y conductores por fase, EGC, SCCR, carga en VA
y longitud.

Lo que casi nunca viene en el dibujo y hay que preguntar:
- **Icc disponible** en el punto de entrega
- **SCCR** de cada tablero
- **Longitudes reales** de cada alimentador
- **Temperatura ambiente** de las canalizaciones
- Grupo de conexión de los transformadores
- **kVA y Z% de placa** de cada transformador (`kva`, `z_pct`): sin ellos no hay
  cortocircuito por bus infinito
- Conexión de cada carga: `fases` 1 = fase-neutro, 2 = fase-fase, 3 = trifásica

Sin Icc, el validador no puede verificar SCCR y el diagrama queda incompleto
para efectos de revisión.

## Qué revisa el validador automáticamente

| Chequeo | Severidad |
|---|---|
| IDs duplicados, padres inexistentes, ciclos en la jerarquía | ERROR |
| Interruptor aguas abajo con capacidad mayor que el de aguas arriba | ERROR |
| SCCR declarado < Icc del nodo (con `--cortocircuito`) o Icc disponible del proyecto | ERROR |
| Carga conectada > capacidad del interruptor principal del tablero | ERROR |
| Carga entre 80 % y 100 % de la capacidad (sin margen) | ADVERTENCIA |
| Nodo con protección pero sin EGC declarado | ADVERTENCIA |
| Tablero sin SCCR declarado | ADVERTENCIA |
| Transformador sin grupo de conexión o sin protección primario/secundario | ADVERTENCIA |
| Nodo de potencia sin tensión declarada | ADVERTENCIA |

**Correr `validar` después de toda edición.** El subcomando `agregar` lo hace
solo. Un ERROR bloquea la emisión del entregable; una ADVERTENCIA se resuelve o
se documenta con justificación.

## Revisión de ingeniería que el validador NO hace

El script verifica consistencia estructural. La revisión de criterio la hace el
agente:

- ¿La arquitectura de tensiones tiene sentido para el perfil de carga?
- ¿Los transformadores están ubicados donde reducen cobre sin crear problemas de
  Icc o de espacio de trabajo?
- ¿Hay un punto único de falla que deje sin energía un proceso crítico?
- ¿La instalación admite el crecimiento que el cliente anticipa?
- ¿Los sistemas derivados separadamente están correctamente identificados con su
  propia puesta a tierra?
- Al integrar BESS o generación: ¿se recalculó la Icc? ¿Hay transferencia? ¿El
  esquema de puesta a tierra cambia según el modo de operación?

## Convenciones de identificación

Consistentes en todo el proyecto y coincidentes con el cuadro de cargas y la
memoria: `ACOM` acometida, `TR-n` transformadores, `TG-n` tableros generales,
`TD-n` tableros derivados, `CCM-n` centros de control de motores, `M-nn`
motores, `C-nn` circuitos derivados, `BESS-n`, `PV-n`, `EVSE-n`, `ATS-n`.

El mismo identificador debe aparecer en el unifilar, en el cuadro de cargas, en
la memoria de cálculo y en el directorio del tablero. Si no coinciden, el
paquete no es revisable.

## Exportación a CAD

El SVG generado es para revisión y para insertar en la memoria. Para plano
ejecutivo, el dibujante lo redibuja en CAD con la simbología del proyecto. Si se
requiere DXF, `ezdxf` es la vía; no está incluido en el paquete para mantener
las dependencias en cero.
