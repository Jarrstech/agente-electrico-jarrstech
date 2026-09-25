# Tableros e interruptores sugeridos — Square D

> Datos de catalogo de referencia. Confirmar numero de catalogo, disponibilidad (Mexico / EE. UU.) y capacidades con el distribuidor o el catalogo vigente de Schneider Electric antes de cotizar. La seleccion usa interruptores totalmente clasificados (sin combinaciones en serie). Los valores marcados en '_verificar' vienen de fuentes secundarias.

Capacidad interruptiva: Mayor o igual que la Icc del tablero (bus infinito, ec.py cortocircuito). Reserva de espacios: 25 %. Numeracion non-par: circuitos nones a la izquierda y pares a la derecha; renglones 1-2 fase A, 3-4 fase B, 5-6 fase C (NEC 408.3(E)).

## TG-1 — Tablero general 480V

- Sistema: 480Y/277 V 3F-4H · Icc: 7.44 kA
- Tablero: Square D I-Line: Tablero de distribucion de potencia I-Line (interior HCP)
- Barras mínimas: 400 A · Principal: PowerPact L, nivel G, disparo electronico MicroLogic, 400 A, 3 polos, 35 kA a 480 V (LGA36400U31X)
- SCCR resultante: 18 kA · Envolvente: [COMPLETAR según ambiente: NEMA 1 interior seco, 3R intemperie, 4X lavado o corrosivo, 12 polvo]

| Pos. | Circuito | Descripción | Polos | Fases | A | Interruptor | kA | Catálogo |
|---|---|---|---|---|---|---|---|---|
| — | TD-1 | Tablero produccion | 3 | — | 225 | JD | 18 | JDA36225 |
| — | TR-2 | Transformador seco 75 kVA | 3 | — | 125 | HD | 18 | HDA36125 |
| — | BESS-1 | BESS 100 kWh / 50 kW | 3 | — | 100 | HD | 18 | HDA36100 |

- El unifilar declara SCCR de 65 kA; con esta selección el tablero queda en 18 kA (Icc 7.44 kA). Actualizar el unifilar o subir el nivel.
- Descartado — NF: sin interruptor para 225 A 3P

## TD-1 — Tablero produccion

- Sistema: 480Y/277 V 3F-4H · Icc: 7.29 kA
- Tablero: Square D NF: Tablero de alumbrado y distribucion NF
- Barras mínimas: 250 A · Principal: PowerPact J, nivel D, 225 A, 3 polos, 18 kA a 480 V
- Espacios: 13 polos usados; mínimo 18 con reserva
- SCCR resultante: 18 kA · Envolvente: [COMPLETAR según ambiente: NEMA 1 interior seco, 3R intemperie, 4X lavado o corrosivo, 12 polvo]

| Pos. | Circuito | Descripción | Polos | Fases | A | Interruptor | kA | Catálogo |
|---|---|---|---|---|---|---|---|---|
| 1 | C-04 | Alumbrado nave LED | 1 | A | 30 | EDB | 18 | EDB14030 |
| 2-4-6 | C-01 | Horno rotatorio principal | 3 | A-B-C | 70 | EDB | 18 | EDB34070 |
| 3-5-7 | C-02 | Amasadora 15 HP | 3 | B-C-A | 20 | EDB | 18 | EDB34020 |
| 8-10-12 | C-03 | Camara de fermentacion | 3 | A-B-C | 15 | EDB | 18 | EDB34015 |
| 9-11-13 | C-06 | Compresor de aire 10 HP | 3 | B-C-A | 15 | EDB | 18 | EDB34015 |

- Circuitos tomados del cuadro de cargas; del unifilar solo los alimentadores a equipo de distribución (se omiten cargas repetidas).
- El unifilar declara SCCR de 42 kA; con esta selección el tablero queda en 18 kA (Icc 7.29 kA). Actualizar el unifilar o subir el nivel.

## TD-2 — Tablero servicios 208/120V

- Sistema: 208Y/120 V 3F-4H · Icc: 4.35 kA
- Tablero: Square D NQ: Tablero de alumbrado y distribucion NQ
- Barras mínimas: 225 A · Principal: Interruptor principal NQ de 225 A
- Espacios: 6 polos usados; mínimo 8 con reserva
- SCCR resultante: 10 kA · Envolvente: [COMPLETAR según ambiente: NEMA 1 interior seco, 3R intemperie, 4X lavado o corrosivo, 12 polvo]

| Pos. | Circuito | Descripción | Polos | Fases | A | Interruptor | kA | Catálogo |
|---|---|---|---|---|---|---|---|---|
| 2-4 | C-07 | Cargador VE nivel 2 | 2 | A-B | 70 | QOB | 10 | QOB270 (verificar rango de amperes con el distribuidor) |
| 3-5 | C-05 | Contactos generales area produccion | 2 | B-C | 30 | QOB | 10 | QOB230 (verificar rango de amperes con el distribuidor) |
| 6-8 | C-08 | Aire acondicionado oficinas | 2 | C-A | 45 | QOB | 10 | QOB245 (verificar rango de amperes con el distribuidor) |

- Circuitos tomados del cuadro de cargas; del unifilar solo los alimentadores a equipo de distribución (se omiten cargas repetidas).
- El unifilar declara SCCR de 22 kA; con esta selección el tablero queda en 10 kA (Icc 4.35 kA). Actualizar el unifilar o subir el nivel.

