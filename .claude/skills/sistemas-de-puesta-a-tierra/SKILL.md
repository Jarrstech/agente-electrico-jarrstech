---
name: sistemas-de-puesta-a-tierra
description: Diseña y verifica puesta a tierra y unión — conductor del electrodo de puesta a tierra (GEC), conductor de puesta a tierra de equipos (EGC), puente de unión principal, sistema de electrodos, red de tierras, sistemas derivados separadamente y separación neutro-tierra. Úsala siempre que el usuario mencione tierra física, puesta a tierra, aterrizaje, varilla, electrodo, malla de tierras, PT, GND, unión, bonding, neutro flotante, o pregunte de qué calibre va el cable de tierra. También ante fallas de operación con corrientes parásitas, disparos espurios o problemas de referencia de tierra.
---

# Puesta a tierra y unión

Es el sistema que decide si una falla se convierte en un disparo o en una
electrocución. También el que más se improvisa en obra.

## Distinguir los tres conductores

Se confunden todo el tiempo y se dimensionan con tablas distintas:

| Conductor | Qué hace | Cómo se dimensiona |
|---|---|---|
| **GEC** — del electrodo de puesta a tierra | Conecta el sistema al planeta; referencia de tensión | Por el calibre del mayor conductor de acometida (Tabla 250.66) |
| **EGC** — de puesta a tierra de equipos | Ruta de retorno de falla; hace disparar la protección | Por la capacidad del dispositivo de sobrecorriente (Tabla 250.122) |
| **Puente de unión principal** | Une neutro y tierra en un único punto del servicio | Por 250.102(C), no por las tablas anteriores |

```bash
python3 scripts/ec.py gec --fase 4/0 --material cobre
python3 scripts/ec.py egc --ocpd 200 --material cobre
```

## Reglas críticas

**Aumento proporcional del EGC.** Si los conductores de fase se aumentaron de
calibre por cualquier razón — típicamente caída de tensión — el EGC debe
aumentarse en la misma proporción de área de sección transversal. Es omisión
frecuente: se sube el calibre de fase por la corrida larga y el EGC se queda en
el de tabla. `scripts/ec.py circuito` emite la alerta cuando escala un calibre.

**Un solo punto de unión neutro-tierra.** El neutro y la tierra se unen
únicamente en el servicio (o en el origen de un sistema derivado separadamente).
En todo tablero derivado, la barra de neutro va **aislada** de la envolvente.
Uniones múltiples generan corriente circulante por las canalizaciones, ruido,
disparos de protecciones diferenciales y riesgo real.

**Sistemas derivados separadamente.** Un transformador de aislamiento, un
generador con neutro conmutado o un UPS con transformador crean un sistema
nuevo que requiere su propio electrodo, su propio puente de unión y su propio
GEC. No basta con "traer la tierra del general".

**Electrodos.** El sistema debe usar todos los electrodos presentes en el
inmueble (acero estructural, tubería metálica de agua, electrodo embebido en
cimentación). Una varilla no puede ser el único electrodo si su resistencia
excede el umbral normativo; en ese caso se requiere otra. **La resistencia se
mide en campo, no se supone.** Pedir el dato o especificar la medición como
requisito de entrega.

**Continuidad de canalización.** El tubo metálico puede servir como EGC en
ciertas condiciones, pero cada acoplamiento, conector y caja rompe o mantiene la
continuidad. En instalaciones industriales con vibración, corrosión o mucha
intervención, especificar EGC de cobre dedicado además de la canalización.

## Casos donde hay que apretar más

- **BESS y fotovoltaico:** puesta a tierra del lado de CD, detección de falla a
  tierra, y coordinación entre la tierra del inversor y la del sistema de CA.
  Artículos propios que se suman a los del capítulo 2.
- **Equipo electrónico sensible:** la solución no es una "tierra aislada"
  separada del sistema — eso es peligroso y no cumple. Es unión adecuada más
  técnicas de canalización y separación de circuitos.
- **Cargadores de vehículo eléctrico:** EGC continuo hasta el equipo, sin
  depender solo de la canalización.
- **Áreas clasificadas:** requisitos de unión más estrictos; la canalización
  sola no basta.

## Red de tierras de la subestación (IEEE Std 80)

Se calcula aparte del resto del proyecto, con su propia entrada:
`config/red-de-tierras.yaml`.

```bash
python3 scripts/red_tierras.py --entrada config/red-de-tierras.yaml \
        --salida red-tierras.json --reporte red-tierras.md
```

**Datos que se piden y nunca se suponen:** resistividad del terreno (medición
Wenner, IEEE Std 81), tensión en el punto de entrega, potencia de cortocircuito
trifásica y monofásica del suministrador, relación X/R y dimensiones de la
malla. **Criterios con valor sugerido:** tiempo de liberación ts, tiempo para
el conductor tc, factor de división Sf (1.0 conservador), profundidad 0.6 m,
conductor 4/0 de cobre, grava de 3000 Ω·m y peso corporal de 50 kg.

El script calcula:

1. Corriente de falla a tierra desde la potencia monofásica del suministrador
   (Icc = MVA × 1000 / (√3 × kV)), factor de decremento Df y corriente de
   malla IG = Df × Sf × 3I0.
2. Sección mínima del conductor con las constantes de la Tabla 1 de IEEE 80.
3. Tensiones de toque y de paso tolerables, con la capa superficial (Cs).
4. Resistencia de la malla (Sverak), GPR, tensión de malla Em y de paso Es.
5. Si no cumple, busca la separación y las varillas en el perímetro que
   cumplen; si no hay, da recomendaciones.

Entrega su propia memoria en Markdown. Un Sf menor que 1 requiere estudio de
división de corriente. El modelo es de suelo uniforme: con resistividad que
cambia con la profundidad, pedir modelo de dos capas. La resistencia real se
mide en campo antes de energizar.

## Al reportar

Calibre y material del GEC y del EGC, artículo que los gobierna, descripción del
sistema de electrodos, ubicación del punto único de unión neutro-tierra, y —
cuando aplique — la nota expresa de que un EGC fue aumentado por escalamiento
del conductor de fase. Especificar la medición de resistencia como entregable de
obra cuando no exista dato.
