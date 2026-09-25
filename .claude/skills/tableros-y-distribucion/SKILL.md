---
name: tableros-y-distribucion
description: Especifica tableros y arquitectura de distribución — capacidad de barras, número de espacios, balanceo de cargas entre fases, tipo de envolvente NEMA, SCCR del conjunto, espacios de trabajo, arquitectura de tensiones y ubicación de transformadores. Úsala siempre que el usuario mencione tablero, centro de carga, panel, board, switchgear, CCM, barras, espacios, NEMA, balanceo de fases, distribución, o pregunte cómo repartir circuitos o qué tablero comprar. También al revisar un tablero existente antes de ampliarlo.
---

# Tableros y distribución

## Balanceo de fases

```bash
python3 scripts/ec.py balanceo --archivo cargas.csv --unifilar unifilar.json
```

El script balancea cada tablero con el arreglo de barras de los tableros
Square D NQ y NF: circuitos nones a la izquierda y pares a la derecha;
renglones 1-2 fase A, 3-4 fase B, 5-6 fase C (NEC 408.3(E)).

- **1 polo (fase-neutro):** toda la carga en su fase.
- **2 polos (fase-fase):** ocupa dos renglones seguidos del mismo lado (A-B,
  B-C o C-A) y carga la **mitad en cada fase**.
- **3 polos:** un tercio en cada fase.

Respeta la fase pedida en la columna `fase` y asigna las demás para dejar el
tablero lo más parejo posible. Entrega la cédula: posición, polos y fases de
cada circuito, VA por fase y desbalance. Criterios de proyecto: ≤5 % aceptable,
>10 % obliga a redistribuir.

El desbalance no es cosmético. Produce corriente por el neutro, calentamiento,
pérdidas y — en sistemas con motores trifásicos aguas arriba — desbalance de
tensión que degrada el motor de forma acelerada. En instalaciones con muchas
cargas monofásicas grandes (cargadores de VE nivel 2, aires acondicionados
mini-split, alumbrado por circuito) el balanceo debe revisarse cada vez que se
agrega carga, no solo al diseñar.

## Especificación de un tablero

Definir siempre, sin dejar campos abiertos:

1. **Tensión y configuración** — p. ej. 480Y/277 V, 3F-4H, o 208Y/120 V 3F-4H.
2. **Capacidad de barras (A)** — no menor a la demanda calculada, con margen de
   crecimiento declarado.
3. **Interruptor principal o solo zapatas** — si es principal, su capacidad y
   número de polos; si es solo zapatas, verificar la regla de número máximo de
   dispositivos y la protección aguas arriba.
4. **SCCR del conjunto (kA)** — ≥ Icc disponible en ese punto. Es la
   especificación que más se omite al cotizar y la que obliga a devolver equipo.
5. **Espacios/polos** — instalados y de reserva. Reserva típica de proyecto:
   20–25 %.
6. **Envolvente NEMA** según ambiente:
   - NEMA 1: interior seco
   - NEMA 3R: intemperie, lluvia
   - NEMA 4/4X: chorro de agua, lavado; 4X además resistente a corrosión
   - NEMA 12: interior industrial con polvo y goteo no corrosivo
   - Áreas clasificadas: envolvente conforme a la clasificación del área,
     no un NEMA genérico
   En panificadoras, plantas de alimentos y áreas de lavado, NEMA 4X es la
   respuesta usual; NEMA 1 ahí es un hallazgo.
7. **Barra de tierra y barra de neutro** — neutro **aislado** en todo tablero
   derivado.
8. **Directorio de circuitos** — obligatorio, con descripción específica; "luces"
   no es una descripción aceptable.

## Espacios de trabajo — se diseñan, no se improvisan

Las distancias mínimas de trabajo frente al equipo energizado, la altura libre y
la iluminación son requisitos, no recomendaciones, y dependen de la tensión y de
las condiciones de las superficies enfrentadas. También lo son el número y la
dirección de las vías de salida en equipo grande.

**Este es el punto donde más choca la ingeniería con la arquitectura.**
Verificarlo *antes* de fijar la ubicación del tablero en el plano, no cuando el
inspector llegue. Cuando el usuario proponga una ubicación, preguntar por el
espacio libre disponible al frente y por lo que hay enfrente.

## Arquitectura de tensiones

Decisión temprana con impacto en todo el costo del proyecto.

- **480Y/277 V** para carga industrial y de motores: menos corriente, conductor
  más pequeño, menor caída en corridas largas. Requiere transformador para
  cargas de 120 V.
- **208Y/120 V** para servicios, oficinas y contactos.
- Un transformador seco cercano a la carga de servicios reduce cobre, pero
  **eleva la Icc local** y crea un sistema derivado separadamente con su propia
  puesta a tierra. Ambas consecuencias hay que atenderlas explícitamente.
- Para cargas de VE y BESS, evaluar alimentar a la tensión más alta disponible;
  reduce dramáticamente el conductor en corridas de estacionamiento.

## Al ampliar un tablero existente

Verificar, en este orden: capacidad de barras vs carga total nueva; espacios
físicos disponibles; SCCR del tablero vs Icc actual (que pudo cambiar si la
utility reforzó la red o si se agregó generación); estado del directorio; y
balanceo resultante. Un tablero con espacios libres pero barras al límite no
admite la ampliación.

## Equipo sugerido Square D

```bash
python3 scripts/ec.py cortocircuito --json unifilar.json --salida cortocircuito.json
python3 scripts/squared.py --unifilar unifilar.json --cortocircuito cortocircuito.json \
        --resultados resultados.json --salida squared.json --reporte squared.md
```

Por cada tablero del unifilar el script propone:

- **Familia:** NQ hasta 240 V; NF en estrella con neutro (480Y/277 V) con
  derivados de hasta 125 A; I-Line hasta 600 V y 1200 A; arriba de eso,
  switchboard (consultar).
- **Interruptores:** QOB, QOB-VH o QHB en NQ; EDB, EGB o EJB en NF; PowerPact
  H, J o L en I-Line. Elige el marco y el nivel más bajos cuya capacidad
  interruptiva sea **≥ Icc del tablero** (totalmente clasificados, sin
  combinaciones en serie), con número de catálogo de referencia.
- **Tablero:** barras mínimas, interruptor principal, espacios con 25 % de
  reserva, SCCR resultante y la cédula con posiciones y fases.

Los datos salen de `datos/catalogo_squared.json`, con sus fuentes. Lo marcado
`_verificar` viene de fuentes secundarias: confirmar número de catálogo y
disponibilidad con el distribuidor antes de cotizar. La envolvente NEMA se
define por ambiente; el script no la elige.
