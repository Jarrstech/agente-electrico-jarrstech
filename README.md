# Agente experto en instalaciones eléctricas — NFPA 70 (NEC) / NOM-001-SEDE

Paquete de skills, datos y herramientas para Claude Code, orientado a operación
binacional: **Texas, EE. UU.** y **México**.

## Qué hace

- Calcula cargas y arma cuadros de carga desde una lista de equipos, con cada
  carga declarada como fase-neutro, fase-fase o trifásica
- Dimensiona conductores por ampacidad, temperatura de terminales, agrupamiento
  y caída de tensión
- Calcula la corriente de cortocircuito por el método del bus infinito en cada
  tablero y verifica capacidad interruptiva y SCCR
- Especifica protecciones de sobrecorriente
- Dimensiona GEC y EGC, y detecta el escalamiento proporcional obligatorio
- Diseña la red de tierras de la subestación con IEEE Std 80, con entrada propia
  (resistividad del terreno y potencia de cortocircuito del suministrador)
- Balancea cargas con el arreglo de barras Square D y sugiere tableros e
  interruptores Square D
- Lee, edita, valida y renderiza diagramas unifilares
- Redacta la memoria de cálculo firmable
- Gestiona el proyecto: programa, submittals, RFI, riesgos, inspecciones
- Cruza con normas concurrentes: NFPA 70E/70B, STPS, OSHA, UL/ANCE, áreas
  clasificadas, BESS y fotovoltaico

## Instalación en Claude Code

```bash
unzip agente-electrico-jarrstech.zip
cd agente-electrico-jarrstech
claude
```

Claude Code detecta automáticamente `.claude/skills/`. Para usar las skills en
todos los proyectos, copiarlas al perfil:

```bash
cp -r .claude/skills/* ~/.claude/skills/
```

Requisitos: Python 3 (biblioteca estándar únicamente, sin dependencias). En
Windows, usar `python` en lugar de `python3` en todos los comandos.

## Interfaz para capturar datos

La forma más directa de arrancar un proyecto:

```bash
python scripts/interfaz.py          # abre http://127.0.0.1:8765 en el navegador
```

La interfaz corre en tu computadora (solo escucha en 127.0.0.1) y guarda cada
proyecto en `proyectos/<id>/` con los mismos archivos que usan los scripts:
`proyecto.yaml`, `jurisdiccion.yaml`, `cargas.csv`, `unifilar.json` y, si hay
subestación propia, `red-de-tierras.yaml`. Se llena en seis pasos:

1. **Proyecto:** datos generales, alcance y alcance negativo, firmas.
2. **Norma y sitio:** jurisdicción y edición confirmada, temperatura ambiente,
   temperatura de terminales, Icc del suministrador y criterios de proyecto.
3. **Unifilar:** acometida, transformadores con kVA y Z% de placa, tableros y
   equipos, con el conductor que llega a cada uno.
4. **Cargas:** una fila por circuito, con su conexión fase-neutro, fase-fase o
   trifásica. Se puede pegar desde Excel.
5. **Red de tierras:** resistividad del terreno y potencia de cortocircuito del
   suministrador (IEEE 80).
6. **Resultados:** Calcular corre todos los scripts y muestra cortocircuito,
   circuitos, balanceo Square D, tableros e interruptores, malla de tierras y el
   borrador de la memoria.

Mientras capturas, la interfaz marca en rojo lo que bloquea un cálculo y en
ámbar lo pendiente. No calcula nada por su cuenta y no rellena datos que nunca
se asumen. Cada corrida deja `bitacora.json` con los comandos exactos para
reproducirla. Después se le pide a Claude la revisión de ingeniería; la
interfaz trae el texto listo para copiar.

## Primer uso sin interfaz

```bash
# 1. Declarar la jurisdicción — el agente no calcula sin esto
$EDITOR config/jurisdiccion.yaml

# 2. Cargar el cuadro de cargas
cp plantillas/cuadro-de-cargas.csv mi-proyecto/cargas.csv

# 3. Pedirle al agente lo que sigue
claude "Tengo el cuadro de cargas en mi-proyecto/cargas.csv. Dimensiona los
        circuitos, arma el unifilar y prepara la memoria de cálculo."
```

## Estructura

```
.claude/skills/     10 skills — el agente las carga solo cuando aplican
datos/              Tablas de referencia (ampacidad, factores, tierras, 240.6,
                    cortocircuito, IEEE 80, catálogo Square D)
scripts/            ec.py (cálculo y cortocircuito) · unifilar.py (diagramas) ·
                    red_tierras.py (malla IEEE 80) · squared.py (equipo Square D) ·
                    memoria.py · interfaz.py (captura de datos en el navegador)
interfaz/           Página de la interfaz (HTML, CSS y JS sin dependencias)
proyectos/          Un proyecto por carpeta, creado por la interfaz
plantillas/         Cuadro de cargas, matriz de riesgos, RFI, submittals
config/             jurisdiccion.yaml (obligatorio) · proyecto.yaml ·
                    red-de-tierras.yaml
ejemplos/           Proyecto demo funcional
referencias/        Esquema del unifilar, equivalencias NEC ↔ NOM
```

## Las diez skills

| Skill | Cuándo se activa |
|---|---|
| `ingenieria-electrica-core` | Siempre — reglas maestras y enrutamiento |
| `calculo-de-cargas` | Cuadros de carga, demanda, factores |
| `seleccion-de-conductores` | Calibres, ampacidad, caída de tensión |
| `proteccion-de-sobrecorriente` | Interruptores, fusibles, SCCR, coordinación |
| `sistemas-de-puesta-a-tierra` | GEC, EGC, electrodos, unión |
| `tableros-y-distribucion` | Balanceo, NEMA, barras, espacios de trabajo |
| `diagramas-unifilares` | Leer, editar, validar y renderizar unifilares |
| `memoria-de-calculo` | Documento firmable con trazabilidad |
| `gestion-de-proyectos-electricos` | Programa, submittals, RFI, riesgos |
| `riesgos-y-normas-relacionadas` | 70E, 70B, STPS, OSHA, UL, áreas clasificadas |

## Dos decisiones de diseño que conviene entender

**1. El agente no inventa valores normativos.** Toda ampacidad, factor y
capacidad sale de `datos/*.json` a través de `scripts/ec.py`. Cuando el dato no
está, el script devuelve `DATO_FALTANTE` y el agente pregunta en vez de estimar.
Ese comportamiento es el que hace utilizable la salida.

**2. El diagrama unifilar es un dato, no un dibujo.** Vive en JSON, se versiona
en git, se valida automáticamente y se diffea entre revisiones. El SVG es una
vista generada.

## Verificaciones obligatorias antes de usar en producción

Los archivos de `datos/` contienen valores de referencia de ingeniería. **Antes
de emitir cualquier entregable firmado, contrastarlos contra la edición vigente
de la norma aplicable al proyecto.** Este paquete no sustituye al código.

Dos puntos que hay que confirmar en cada proyecto nuevo:

- **Texas:** Texas ha operado bajo el NEC 2023 desde el 1 de septiembre de 2023,
  y TDLR anunció la adopción del NEC 2026 con efecto el 1 de septiembre de 2026.
  Un proyecto que inicia obra cerca de esa fecha puede regirse por una u otra
  edición. Confirmar con TDLR y con el AHJ municipal, que además puede tener
  enmiendas locales.
- **México:** hay fuentes públicas contradictorias sobre cuál es la edición
  vigente de la NOM-001-SEDE. Confirmarlo en el DOF y en el Catálogo Nacional de
  Normas, y registrar la fecha de consulta en `config/jurisdiccion.yaml`.

## Límites

El agente produce ingeniería preliminar y documentación. **No sustituye** al
ingeniero responsable, al PE registrado en Texas, al DRO ni a la Unidad de
Verificación; una persona con licencia vigente debe revisar y firmar.

No genera estudios que requieren software especializado y datos de campo:
cortocircuito detallado, coordinación con curvas reales y arco eléctrico (IEEE
1584). Para esos, estructura los insumos y define qué se necesita contratar. El
cortocircuito por bus infinito es una cota superior conservadora para elegir
capacidad interruptiva y SCCR; la red de tierras supone suelo uniforme y su
resistencia se mide en campo. Las sugerencias Square D se confirman con el
distribuidor antes de cotizar.
