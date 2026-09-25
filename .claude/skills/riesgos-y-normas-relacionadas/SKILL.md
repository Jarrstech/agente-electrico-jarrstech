---
name: riesgos-y-normas-relacionadas
description: Identifica riesgos eléctricos y las normas concurrentes que aplican además del NEC/NOM-001-SEDE — seguridad en el trabajo y arco eléctrico (NFPA 70E, NOM-029-STPS, OSHA), mantenimiento (NFPA 70B), áreas clasificadas, protección contra incendio, listado de equipo (UL/NOM/ANCE), eficiencia energética e interconexión. Úsala siempre que el usuario mencione riesgo, seguridad, arco eléctrico, arc flash, EPP, LOTO, bloqueo y etiquetado, área clasificada, atmósfera explosiva, NFPA 70E, 70B, STPS, OSHA, UL, listado, certificación, o pregunte qué más aplica además del código eléctrico. También al revisar una instalación existente para detectar riesgos.
---

# Riesgos y normas concurrentes

El código eléctrico regula **cómo se instala**. No cubre cómo se trabaja sobre
la instalación, cómo se mantiene, ni cómo se certifica el equipo. Un proyecto
que solo cumple el código eléctrico deja huecos serios.

## Mapa de normas concurrentes

| Ámbito | Estados Unidos / Texas | México |
|---|---|---|
| Instalación | NFPA 70 (NEC), adoptado por TDLR | NOM-001-SEDE |
| Seguridad del trabajador | NFPA 70E, OSHA 29 CFR 1910 Subparte S | NOM-029-STPS (mantenimiento de instalaciones eléctricas), NOM-017-STPS (EPP) |
| Mantenimiento | NFPA 70B | Criterio de NOM-029-STPS y buenas prácticas |
| Cálculo de arco eléctrico | IEEE 1584 | IEEE 1584 (referencia técnica) |
| Listado de equipo | UL, ETL — listado por NRTL | NOM aplicables, certificación ANCE |
| Áreas clasificadas | NEC Cap. 5, NFPA 497/499 | NOM-001-SEDE Cap. 5 |
| Protección contra incendio | NFPA 72, NFPA 101 | NOM-002-STPS y reglamentos locales |
| Fotovoltaico e interconexión | NEC Art. 690/705, IEEE 1547 | NOM-001-SEDE + disposiciones de generación distribuida |
| Almacenamiento en baterías | NEC Art. 706, UL 9540/9540A, NFPA 855 | NOM-001-SEDE + criterios de la CNE |
| Eficiencia energética | ASHRAE 90.1, códigos locales | NOM de eficiencia energética, ISO 50001 |

Confirmar vigencia y edición de cada una en cada proyecto.

## Arco eléctrico — el riesgo que el código no dimensiona

El NEC exige el **etiquetado de advertencia**, pero el cálculo de la energía
incidente y la selección de EPP vienen de NFPA 70E e IEEE 1584.

**El agente no calcula energía incidente.** Requiere el estudio de cortocircuito,
las curvas reales de los dispositivos, los tiempos de despeje y la geometría del
equipo. Lo que sí hace:

- Identificar dónde es obligatorio el estudio y el etiquetado
- Listar los insumos necesarios para contratarlo
- Señalar decisiones de diseño que **reducen** la energía incidente: ajustes de
  disparo instantáneo, interruptores con mantenimiento de energía reducida,
  relevadores de arco, seccionamiento remoto, aumentar la distancia de trabajo
- Detectar el caso contrapuesto: un dispositivo con retardo largo mejora la
  selectividad y **empeora** el arco eléctrico. Es un compromiso explícito de
  diseño, no un detalle.

Buena práctica de proyecto: pedir el estudio de arco eléctrico **durante el
diseño**, no después de energizar, cuando los ajustes ya no se pueden cambiar
sin paro.

## Trabajo seguro

Establecer condición de trabajo eléctricamente seguro antes de intervenir:
desconexión, bloqueo y etiquetado, verificación de ausencia de tensión con
instrumento probado antes y después, y puesta a tierra temporal cuando aplique.

El trabajo energizado requiere justificación documentada, permiso, análisis de
riesgo y EPP acorde a la energía incidente calculada. "Es rápido" no es
justificación.

En proyectos con BESS o fotovoltaico hay una trampa específica: **el lado de CD
no se desenergiza abriendo el interruptor de CA.** Los paneles producen con luz
y las baterías están permanentemente energizadas. Los procedimientos de bloqueo
deben contemplarlo explícitamente.

## Áreas clasificadas

En panificadoras, molinos, plantas de alimentos y manejo de granos hay riesgo de
**polvo combustible** que a menudo se pasa por alto porque no huele a gas. La
clasificación del área la define un estudio, y determina el tipo de envolvente,
canalización, sellos y equipo. Instalar equipo de propósito general en un área
clasificada es un riesgo de explosión y un hallazgo inmediato de verificación.

Cuando el usuario describa una instalación con harinas, azúcares, granos,
solventes, pintura o carga de baterías de plomo, **preguntar por la
clasificación del área antes de especificar equipo.**

## Listado y certificación

El equipo debe estar listado/certificado y usarse conforme a su listado. Dos
consecuencias prácticas:

- **Equipo importado sin listado reconocido puede ser rechazado en inspección**,
  aunque sea de buena calidad. Verificarlo *antes* de comprar es una actividad de
  procura, no un trámite posterior. Aplica de lleno a BESS, inversores y
  cargadores de VE de origen no norteamericano.
- Usar equipo fuera de su listado (un tablero interior en intemperie, un
  dispositivo con conductor de temperatura distinta a la marcada) anula la
  certificación y la cobertura del seguro.

## Revisión de riesgos de una instalación existente

Al inspeccionar, buscar en este orden — ordenado por frecuencia real de
hallazgo:

1. Neutro y tierra unidos en tableros derivados
2. SCCR insuficiente o desconocido
3. Espacios de trabajo obstruidos o insuficientes
4. Conductores subdimensionados por no aplicar temperatura de terminal
5. Directorio de circuitos ausente, ilegible o falso
6. Espacios abiertos sin tapa ciega en tableros
7. Canalización sin continuidad de tierra
8. Equipo de propósito general en área clasificada
9. Ausencia de etiquetado de arco eléctrico donde se requiere
10. Modificaciones sin actualizar unifilar ni memoria

Clasificar cada hallazgo por severidad (riesgo a la vida, riesgo al equipo,
incumplimiento documental) y proponer solución con su impacto en costo y paro.
