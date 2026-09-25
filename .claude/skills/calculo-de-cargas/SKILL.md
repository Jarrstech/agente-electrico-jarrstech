---
name: calculo-de-cargas
description: Levanta y calcula cargas eléctricas de una instalación — inventario, VA por circuito, cargas continuas vs no continuas, factores de demanda, cargas de motores, cálculo de alimentador y acometida. Úsala siempre que el usuario mencione cuadro de cargas, relación de cargas, demanda máxima, carga instalada, dimensionar acometida, capacidad de transformador, o cuando entregue una lista de equipos y pida saber qué necesita. También cuando pregunte "¿de cuánto me sale el tablero?" o similares. Es el paso 2 del flujo maestro y alimenta a todas las demás skills de cálculo.
---

# Cálculo de cargas

Todo el proyecto se apoya en este paso. Una carga mal levantada arruina el
dimensionamiento aguas abajo aunque cada fórmula posterior sea correcta.

## Entrada estándar: el CSV de cargas

Trabajar siempre sobre `plantillas/cuadro-de-cargas.csv`. Columnas:

| Columna | Contenido | Si falta |
|---|---|---|
| `id` | Identificador del circuito (C-01, M-03) | Generar secuencial |
| `nombre` | Descripción del equipo | Pedir |
| `va` | Carga aparente en VA | **Pedir. Nunca estimar.** |
| `tension` | Tensión de la carga: fase-neutro si `fases` = 1 (p. ej. 277 V en 480Y/277), entre fases si `fases` = 2 o 3 (480 V) | Pedir |
| `fases` | 1 = fase-neutro (1 polo), 2 = fase-fase o bifásica (2 polos), 3 = trifásica (3 polos) | Pedir |
| `fase` | A, B o C con 1 polo; AB, BC o CA con 2 polos | Dejar vacío; el balanceo lo asigna |
| `continua` | `si` si opera 3 h o más | **Preguntar explícitamente** |
| `longitud_m` | Recorrido real del conductor | **Pedir. Sin esto no hay caída de tensión.** |
| `n_conductores` | Portadores de corriente en la misma canalización | Asumir 3 y decirlo |
| `material` | cobre / aluminio | Asumir cobre y decirlo |
| `tablero` | Id del tablero que alimenta el circuito, igual que en el unifilar | Pedir: balanceo, verificación de tensión y equipo Square D van por tablero |

Si el usuario entrega la información en otro formato (foto de una placa, lista
en texto, plano), convertirla a este CSV primero. El CSV es el artefacto que se
versiona y se revisa.

## Reglas que se aplican siempre

**Carga continua (factor 1.25).** Una carga que opera 3 horas o más de forma
continua se dimensiona al 125 % para el conductor *y* para el dispositivo de
protección. Aplica a alumbrado comercial, cargadores de vehículo eléctrico,
procesos continuos, letreros. **Preguntar caso por caso**: el usuario suele
saberlo y el agente no puede deducirlo del nombre del equipo.

**Placa vs tabla en motores.** Para dimensionar conductores de motor se usa la
corriente a plena carga **de las tablas de la norma**, no la de la placa. La
placa se usa para la protección de sobrecarga. Confundirlas es uno de los
errores más frecuentes y más caros. Las tablas de FLC no están en `datos/`:
pedirlas o consultarlas en la norma vigente.

**Varios motores en un alimentador:** 125 % del motor de mayor corriente + suma
de las corrientes a plena carga de los demás.

**Factores de demanda.** Dependen del tipo de ocupación. Están parcialmente en
`datos/factores_demanda_220.json`. Si el tipo de ocupación no encaja limpiamente
en una categoría de la tabla, **aplicar 100 % y documentar el criterio**. Un
factor de demanda aplicado por analogía es un hallazgo de verificación.

**Cargas que se calculan aparte y no admiten factor de demanda por descuido:**
cargadores de vehículo eléctrico, equipo de cocina comercial, soldadoras,
sistemas de almacenamiento en baterías, aire acondicionado con compresor
hermético. Cada uno tiene su artículo propio.

## Procedimiento

1. Construir el CSV con el usuario, columna por columna. Preguntar por lo que
   falte en vez de rellenar.
2. Separar cargas continuas de no continuas; marcarlas en el CSV.
3. Correr `python3 scripts/ec.py circuito --archivo cargas.csv --unifilar unifilar.json --salida resultados.json`.
   Con `--unifilar`, cada circuito se verifica contra la tensión de su tablero
   (una carga de 277 V debe ir con `fases` = 1; una de 480 V, con `fases` = 2).
4. Revisar el balanceo por tablero que trae `resultados.json` (o correr
   `ec.py balanceo`). Sigue el arreglo de barras Square D: una carga fase-fase
   carga la mitad en cada una de sus dos fases. Objetivo ≤ 5 %; por encima de
   10 %, redistribuir.
5. Sumar por tablero, aplicar factores de demanda donde correspondan y
   documentar cuáles se aplicaron y por qué.
6. Definir **carga instalada** (suma bruta) y **demanda máxima** (con factores).
   El transformador y la acometida se dimensionan con demanda máxima; las
   barras del tablero, con lo que exija el artículo aplicable.
7. Reservar crecimiento futuro. Declararlo como criterio de proyecto, no como
   requisito normativo. En instalaciones industriales 20–25 % es común; en
   proyectos con BESS o carga de VE prevista, cuantificarlo explícitamente
   porque cambia la acometida.

## Salida esperada

Un cuadro de cargas con, por circuito: identificador, descripción, VA, tensión,
fases, corriente de carga, corriente de diseño, si es continua, y la fase
asignada. Más un resumen por tablero con carga instalada, demanda máxima,
desbalance y margen de crecimiento.

Al cerrar, listar de forma visible **todo supuesto que se haya tenido que hacer
por falta de dato**, para que el ingeniero responsable lo confirme antes de
firmar.
