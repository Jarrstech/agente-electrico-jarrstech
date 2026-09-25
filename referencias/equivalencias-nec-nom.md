# Equivalencias NEC ↔ NOM-001-SEDE

La NOM-001-SEDE es una adaptación mexicana del NEC. La estructura de capítulos y
la numeración de artículos son en gran medida paralelas, lo que permite mover
criterios entre ambos marcos con cuidado.

**Cuidado, precisamente.** Las equivalencias de abajo son de estructura, no de
contenido idéntico. La NOM introduce cambios propios, y cada edición se basa en
una edición específica del NEC que suele ir varios ciclos por detrás. **Verificar
el texto de la edición declarada en `config/jurisdiccion.yaml` antes de citar.**

## Estructura de capítulos

| Cap. | Contenido | Comentario |
|---|---|---|
| 1 | Generalidades, definiciones, requisitos de instalación | Espacios de trabajo, marcado, temperatura de terminales |
| 2 | Alambrado y protección | Circuitos derivados, alimentadores, cálculo de cargas, sobrecorriente, puesta a tierra |
| 3 | Métodos de alambrado y materiales | Conductores, canalizaciones, cajas, ampacidad |
| 4 | Equipo de uso general | Cordones, luminarias, motores, transformadores, capacitores |
| 5 | Ambientes especiales | Áreas clasificadas, lugares peligrosos |
| 6 | Equipos especiales | Letreros, grúas, elevadores, soldadoras, fotovoltaico, vehículos eléctricos |
| 7 | Condiciones especiales | Sistemas de emergencia, legalmente exigidos, en espera, almacenamiento de energía |
| 8 | Sistemas de comunicaciones | |
| 9 | Tablas | Propiedades de conductores, llenado de canalización |

## Artículos de uso frecuente

| Tema | Ubicación habitual |
|---|---|
| Espacios de trabajo | Cap. 1, art. 110 |
| Temperatura de terminales | Cap. 1, art. 110 |
| Circuitos derivados | Cap. 2, art. 210 |
| Alimentadores | Cap. 2, art. 215 |
| Cálculo de cargas | Cap. 2, art. 220 |
| Protección contra sobrecorriente | Cap. 2, art. 240 |
| Puesta a tierra y unión | Cap. 2, art. 250 |
| Ampacidad de conductores | Cap. 3, art. 310 |
| Motores | Cap. 4, art. 430 |
| Transformadores | Cap. 4, art. 450 |
| Fotovoltaico | Cap. 6 |
| Vehículos eléctricos | Cap. 6 |
| Almacenamiento de energía | Cap. 7 |

## Diferencias prácticas que importan

**Unidades.** La NOM designa conductores en mm² (con AWG como referencia
paralela) y usa el sistema métrico. Los entregables mexicanos deben presentar
mm²; el instalador y el catálogo del fabricante trabajan en esa unidad.

**Verificación.** En México el dictamen lo emite una Unidad de Verificación
acreditada, con un procedimiento de evaluación de la conformidad definido en la
propia norma. En Texas la inspección la hace el AHJ municipal. Los entregables y
los tiempos son distintos.

**Desfase de edición.** Una edición de la NOM se basa en una edición del NEC
anterior. Un criterio nuevo del NEC vigente puede no existir todavía en la NOM
aplicable — y al revés, la NOM puede tener requisitos propios sin equivalente.
Nunca trasladar un artículo de un marco al otro sin verificar el texto.

**Ámbito de aplicación.** La NOM-001-SEDE cubre instalaciones de utilización. Las
redes de transmisión y distribución se rigen por otra normativa. En proyectos de
interconexión, generación distribuida o BESS conectado a la red, hay
disposiciones adicionales del regulador que se suman a la NOM.
