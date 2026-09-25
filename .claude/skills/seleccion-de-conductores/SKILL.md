---
name: seleccion-de-conductores
description: Selecciona calibre de conductores por ampacidad y por caída de tensión, aplicando corrección por temperatura ambiente, ajuste por agrupamiento, límite de temperatura de terminales y conductores en paralelo. Úsala siempre que el usuario pregunte qué calibre usar, qué cable necesita, cuánto cable, qué sección en mm², si un conductor "aguanta", por caída de tensión, por ampacidad, por corridas largas, o cuando dé una carga y una distancia. También para verificar si un conductor existente es adecuado. No adivines calibres: siempre corre scripts/ec.py.
---

# Selección de conductores

Un conductor debe pasar **cuatro filtros independientes**. Fallar uno lo
descalifica aunque pase los otros tres.

## Los cuatro filtros

**1. Ampacidad corregida.** Ampacidad de tabla × factor de temperatura ×
factor de agrupamiento ≥ corriente de diseño. Ambos factores se multiplican
entre sí; no se toma "el peor".

**2. Temperatura de terminales.** Aunque el aislamiento sea 90 °C, la ampacidad
utilizable se limita a la columna correspondiente a la temperatura de los
terminales del equipo real. En la práctica casi todo equipo comercial está
listado a 75 °C, y por debajo de 100 A a veces a 60 °C. El aislamiento a 90 °C
sirve para *aplicar los factores de corrección desde una base más alta*, no
para cargar el conductor a 90 °C.

Esta es la causa número uno de conductores subdimensionados en proyectos
hechos con calculadora de internet. `scripts/ec.py` la aplica y reporta qué
regla gobernó (`regla_gobernante`).

**3. Caída de tensión.** Criterio de proyecto, no requisito obligatorio en NEC
(son notas informativas), pero sí criterio de aceptación habitual en proyectos
mexicanos y en especificaciones de cliente. Referencia usual: 3 % en circuito
derivado, 2 % en alimentador, 5 % total.

**4. Calibre mínimo por artículo específico.** Algunos circuitos tienen mínimos
propios independientes del cálculo (circuitos derivados de uso general,
conductores en paralelo que exigen 1/0 mínimo, circuitos de motores, EVSE).
Verificar el artículo aplicable.

## Comandos

```bash
# Por ampacidad (aplica los cuatro criterios salvo caída)
python3 scripts/ec.py conductor --carga-va 45000 --tension 480 --fases 3 \
        --continua --ambiente-c 40 --n-conductores 6 --material cobre

# Caída de tensión de un calibre concreto
python3 scripts/ec.py caida --calibre 2/0 --corriente 150 --longitud-m 85 \
        --tension 480 --fases 3

# Todo el cuadro de cargas de una vez (incluye reajuste automático por caída)
python3 scripts/ec.py circuito --archivo cargas.csv --salida resultados.json
```

El script ya escala el calibre cuando la caída excede el límite y emite la
alerta correspondiente.

`--fases` (y la columna `fases` del CSV): 1 = fase-neutro, 2 = fase-fase,
3 = trifásica. Con 1 o 2 la corriente es VA / V y la caída se calcula con ida y
vuelta del conductor; la tensión es la fase-neutro (p. ej. 277 V) o la de
entre fases (480 V) según corresponda.

## Datos que hay que pedir, no suponer

- **Temperatura ambiente real.** En un entrepiso de nave industrial en
  Monterrey o en una azotea en Texas puede superar los 45 °C. Asumir 30 °C ahí
  es un error de dimensionamiento, no un redondeo.
- **Número de portadores de corriente en la misma canalización.** El neutro
  cuenta cuando lleva corriente armónica de cargas no lineales o corriente
  desbalanceada. En instalaciones con muchos variadores, fuentes conmutadas o
  LED, preguntarlo explícitamente.
- **Longitud real del recorrido**, no la distancia en línea recta del plano.
- **Temperatura de terminales del equipo específico** que se va a instalar.

## Conductores en paralelo

Permitidos a partir de 1/0. Todos los conductores en paralelo de la misma fase
deben ser del mismo material, calibre, longitud, tipo de aislamiento y terminar
de la misma forma. En canalización metálica, todas las fases y el neutro deben
ir en la misma canalización o la reactancia induce desbalance. Cuando se usan
paralelos, el EGC de cada canalización se dimensiona por el interruptor
completo, no por la fracción.

## Nota para trabajo en México

La NOM designa conductores en mm². `datos/propiedades_conductores.json` incluye
la equivalencia AWG↔mm². Presentar ambas designaciones en los entregables
mexicanos; el instalador compra en mm² y el catálogo del fabricante suele traer
las dos.

## Al reportar

Indicar siempre: calibre, material, aislamiento, conductores por fase,
ampacidad de tabla, factores aplicados, ampacidad resultante, cuál de los
cuatro filtros gobernó, y la caída de tensión calculada. Si algún dato fue
supuesto, marcarlo.
