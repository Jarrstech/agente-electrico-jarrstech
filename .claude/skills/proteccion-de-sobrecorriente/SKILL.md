---
name: proteccion-de-sobrecorriente
description: Especifica y verifica protecciones contra sobrecorriente — capacidad de interruptores y fusibles, regla del siguiente tamaño superior, protección de conductores, protección de motores, transformadores, coordinación selectiva y verificación de SCCR contra la corriente de cortocircuito disponible. Úsala siempre que el usuario mencione interruptor, ITM, termomagnético, breaker, fusible, pastilla, capacidad interruptiva, kA, cortocircuito, coordinación, selectividad, o pregunte de cuántos amperes va una protección. También cuando revise un tablero existente buscando protecciones mal dimensionadas.
---

# Protección de sobrecorriente

## Principio

El dispositivo protege al **conductor**, no a la carga. La carga la protege su
propio dispositivo de sobrecarga. Confundirlos lleva a interruptores que
"aguantan la carga" pero dejan el cable sin protección.

```bash
python3 scripts/ec.py proteccion --corriente 150 --continua
```

## Reglas de dimensionamiento

**Caso general.** El dispositivo se dimensiona a ≥125 % de la carga continua +
100 % de la no continua, y no debe exceder la ampacidad del conductor, con las
excepciones siguientes.

**Siguiente tamaño superior.** Cuando la ampacidad del conductor no coincide con
una capacidad estándar, se permite el siguiente dispositivo estándar hacia
arriba, con condiciones: no aplica a circuitos derivados multisalida ni por
encima de ciertos umbrales de corriente. Verificar el artículo antes de usarla
como comodín.

**Conductores pequeños.** Los calibres 14, 12 y 10 AWG tienen topes absolutos de
protección independientes de su ampacidad de tabla. Están en
`datos/ampacidad_310_16.json` bajo `limite_240_4_D_cobre` y el script los aplica
automáticamente.

**Motores.** La protección de cortocircuito del circuito derivado del motor se
determina por tabla según el tipo de dispositivo (fusible de acción retardada,
interruptor de tiempo inverso, protector instantáneo) y el tipo de motor. **No
existe un "250 % universal".** Va aparte de la protección de sobrecarga, que se
dimensiona sobre la corriente de placa y el factor de servicio. Los circuitos de
motores admiten protección de cortocircuito muy por encima de la ampacidad del
conductor precisamente porque la sobrecarga se protege por separado.

**Transformadores.** Protección de primario y de secundario según el artículo
aplicable, con reglas distintas según haya o no protección secundaria y según la
tensión. Un transformador con protección solo en primario tiene límites más
estrictos.

**Tomas de conductores (taps).** Las reglas de 3 m, 7.5 m y 25 pies permiten
conductores sin protección en su origen bajo condiciones estrictas de longitud,
ampacidad mínima y terminación. Cada condición debe verificarse y documentarse;
un tap mal aplicado es un hallazgo grave.

## SCCR — la verificación que más se omite

**La capacidad interruptiva del dispositivo y el SCCR del tablero deben ser
mayores o iguales a la corriente de cortocircuito disponible en ese punto.**

Esto exige un dato externo: la Icc disponible en el punto de entrega, que da la
compañía suministradora (CFE en México, la utility correspondiente en Texas), o
que se calcula desde la impedancia del transformador y la contribución de la
red. **Nunca asumirla.** Si no está, pedirla y no cerrar el diseño sin ella.

Puntos donde el SCCR suele fallar:
- Tableros de servicios alimentados desde un transformador seco cercano: la Icc
  es más alta de lo que la gente supone.
- Equipo industrial ensamblado (tableros de control, skids) cuyo SCCR compuesto
  lo fija el componente más débil, no el interruptor principal.
- Instalaciones con BESS o generación en sitio: el almacenamiento **aporta
  corriente de falla** y cambia la Icc respecto al cálculo original de la
  instalación. Recalcular al integrar un BESS, siempre.

### Cálculo por bus infinito

Cuando se necesita la Icc en cada tablero, calcularla con el método del bus
infinito: la red del suministrador se toma con impedancia cero y la corriente
la limitan el transformador y los conductores.

```bash
python3 scripts/ec.py cortocircuito --json unifilar.json --salida cortocircuito.json
python3 scripts/ec.py cortocircuito --kva 300 --z-pct 5.75 --tension 480   # solo el secundario
```

- En el secundario: Icc = kVA × 1000 / (√3 × V × Z%/100). Aguas abajo se suma
  la resistencia de los conductores a 25 °C.
- Requiere **kVA y Z% de placa** de cada transformador (`kva`, `z_pct` en el
  unifilar). No suponerlos.
- Suma el aporte de motores (4 × corriente nominal, Eaton Bussmann) y el de
  BESS, fotovoltaico, generador o UPS declarado en `aporte_icc_kA`, que es dato
  del fabricante. Si falta, el script avisa: pedirlo.
- Es una cota superior conservadora: sirve para capacidad interruptiva y SCCR,
  no para coordinación ni arco eléctrico.

`scripts/unifilar.py validar --cortocircuito cortocircuito.json` compara el
SCCR de cada tablero contra la Icc de su punto y marca ERROR si es
insuficiente. Sin `--cortocircuito`, compara contra `icc_disponible_kA` del
diagrama.

## Coordinación selectiva

Objetivo: que ante una falla dispare únicamente el dispositivo más cercano,
aguas arriba de ella. Requiere superponer curvas tiempo-corriente reales de los
fabricantes específicos.

**El agente no fabrica curvas de coordinación.** Lo que sí hace:
- Verificar que ninguna protección aguas abajo tenga capacidad mayor que la de
  aguas arriba (el validador de unifilares lo detecta).
- Identificar dónde la coordinación selectiva es obligatoria por norma o crítica
  por operación (sistemas de emergencia, sistemas legalmente exigidos, cargas de
  proceso continuo).
- Listar los datos necesarios para el estudio: marcas, modelos, curvas,
  ajustes disponibles, Icc en cada nivel.
- Recomendar el estudio formal en software especializado cuando corresponda.

## Al reportar

Por cada protección: capacidad nominal, número de polos, tipo, capacidad
interruptiva, artículo que gobierna el dimensionamiento, y la verificación
explícita de que la ampacidad del conductor y el SCCR del equipo son
suficientes. Cuando se aplique una excepción (siguiente tamaño superior, tap,
motor), citarla nominalmente.
