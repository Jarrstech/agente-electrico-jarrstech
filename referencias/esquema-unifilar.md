# Esquema del modelo de diagrama unifilar

El diagrama es un JSON versionable. El SVG es una vista generada; no editarlo.

## Documento

```json
{
  "proyecto": "string",
  "cliente": "string",
  "ubicacion": "string",
  "norma": "string — norma y edición aplicable",
  "revision": "A",
  "fecha": "AAAA-MM-DD",
  "icc_disponible_kA": 22,
  "nodos": [ ... ]
}
```

`icc_disponible_kA` es obligatorio para que el validador pueda verificar SCCR.
Sin él, esa verificación queda abierta y el diagrama está incompleto.

## Nodo

| Campo | Tipo | Notas |
|---|---|---|
| `id` | string | Único. Convención: ACOM, TR-n, TG-n, TD-n, CCM-n, M-nn, C-nn, BESS-n, PV-n, EVSE-n, ATS-n |
| `tipo` | enum | Ver lista abajo |
| `padre` | string | `id` del nodo aguas arriba. Vacío = raíz |
| `descripcion` | string | Texto que aparece en el render |
| `tension_V` | number | Tensión nominal |
| `fases` | 1 \| 2 \| 3 | 1 = fase-neutro, 2 = fase-fase, 3 = trifásica. Por omisión 3 |
| `hilos` | 2 \| 3 \| 4 | |
| `interruptor_A` | number | Capacidad del dispositivo de protección |
| `sccr_kA` | number | Se compara contra `icc_disponible_kA` |
| `calibre` | string | AWG o kcmil: `"12"`, `"4/0"`, `"500"` |
| `conductores_por_fase` | number | Paralelos. Por omisión 1 |
| `material` | `cobre` \| `aluminio` | |
| `egc` | string | Calibre del conductor de puesta a tierra de equipos |
| `longitud_m` | number | Recorrido real |
| `carga_va` | number | Solo en nodos terminales o tableros con carga conocida |
| `conexion` | string | Solo transformadores: `"Dyn11"`, etc. |
| `proteccion_primario_A` | number | Solo transformadores |
| `proteccion_secundario_A` | number | Solo transformadores |
| `kva` | number | Solo transformadores: potencia de placa. Obligatorio para el cortocircuito |
| `z_pct` | number | Solo transformadores: impedancia de placa en %. Obligatorio para el cortocircuito |
| `x_r` | number | Solo transformadores, opcional. Sin él, la impedancia se toma reactiva (conservador) |
| `aporte_icc_kA` | number | BESS, fotovoltaico, generador, UPS: corriente de falla que aportan (dato del fabricante) |
| `reactancia_ohm_km` | number | Opcional: reactancia del conductor; sin ella se toma cero (conservador) |
| `notas` | array | Observaciones que se conservan entre revisiones |

## Tipos válidos

`acometida`, `medidor`, `transformador`, `interruptor_principal`, `tablero`,
`barra`, `carga`, `motor`, `generador`, `ups`, `bess`, `fotovoltaico`,
`cargador_ve`, `transferencia`, `capacitor`

## Validaciones automáticas

**ERROR** (bloquea la emisión): ID duplicado; padre inexistente; ciclo en la
jerarquía; tipo no reconocido; interruptor aguas abajo mayor que el de aguas
arriba; SCCR menor que la Icc disponible; carga conectada mayor que la
capacidad del interruptor principal.

**ADVERTENCIA** (resolver o justificar): carga entre 80 % y 100 % de capacidad;
nodo con protección pero sin EGC; tablero sin SCCR declarado; transformador sin
grupo de conexión o sin protección de primario/secundario; nodo de potencia sin
tensión.

## Flujo típico

```bash
python3 scripts/unifilar.py describir --json unifilar.json
python3 scripts/unifilar.py agregar --json unifilar.json --padre TG-1 --id BESS-2 \
        --tipo bess --descripcion "BESS 200 kWh" --tension 480 --fases 3 \
        --interruptor 200 --calibre 4/0 --egc 4 --sccr 65
python3 scripts/unifilar.py validar --json unifilar.json
python3 scripts/unifilar.py render  --json unifilar.json --svg unifilar.svg
python3 scripts/ec.py cortocircuito --json unifilar.json --salida cortocircuito.json
python3 scripts/unifilar.py validar --json unifilar.json --cortocircuito cortocircuito.json
```

`agregar` valida automáticamente después de escribir.
