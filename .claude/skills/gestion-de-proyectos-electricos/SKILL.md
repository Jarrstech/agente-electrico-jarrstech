---
name: gestion-de-proyectos-electricos
description: Gestiona proyectos de instalaciones eléctricas de punta a punta — alcance y EDT, programa y ruta crítica, estimación y control de costos, submittals y RFI, procura de equipo con tiempos de entrega largos, gestión de permisos e inspecciones, control de cambios, matriz de riesgos y cierre con dossier. Úsala siempre que el usuario mencione programa, cronograma, presupuesto, cotización, alcance, submittal, RFI, orden de cambio, permiso, inspección, entrega, dossier, contratista, subcontratista, o pregunte cómo organizar o cotizar un proyecto eléctrico. También al planear la ejecución de un diseño ya terminado.
---

# Gestión de proyectos eléctricos

En instalaciones eléctricas los proyectos se atrasan casi siempre por las mismas
tres causas: **tiempos de entrega de equipo**, **ciclos de inspección**, y
**cambios de alcance no controlados**. La gestión se organiza alrededor de esas
tres.

## Estructura de alcance (EDT)

Estructura base que se adapta al proyecto:

1. Ingeniería — levantamiento, cálculos, planos, memoria, permisos
2. Procura — cotización, orden, seguimiento, recepción, almacenaje
3. Obra civil asociada — trincheras, bases, registros, penetraciones
4. Instalación — canalización, cableado, equipo, conexionado
5. Pruebas y puesta en marcha — continuidad, aislamiento, resistencia de tierra,
   secuencia de fases, termografía, energización
6. Cierre — dictamen/inspección, dossier, planos as-built, capacitación

**El alcance negativo se escribe.** Lo que no está incluido (obra civil,
albañilería de resane, suministro eléctrico del cliente, permisos de terceros)
va listado en el contrato. Es donde nacen la mayoría de las disputas.

## Programa: partir desde los tiempos de entrega

El error clásico es programar hacia adelante desde el inicio de obra. Programar
**hacia atrás** desde las entregas de equipo largo:

| Elemento | Tiempo de entrega típico | Riesgo |
|---|---|---|
| Tablero de distribución / switchgear a la medida | Largo, muy variable | Alto — suele ser la ruta crítica real |
| Transformador seco o de pedestal | Largo | Alto |
| Interruptores de marco grande | Medio-largo | Medio |
| Sistema BESS e inversores | Largo, más aduana si es importado | Alto |
| Cargadores de VE | Medio | Medio |
| Cable de calibre grande | Medio, sensible al precio del cobre | Medio |
| Canalización, herrajes, accesorios | Corto | Bajo |

**Confirmar tiempos con el proveedor específico en cada proyecto.** Han variado
mucho y siguen variando. Un programa con tiempos de entrega supuestos es un
programa ficticio.

Para equipo importado (p. ej. proveedores coreanos de BESS o cargadores), sumar
al tiempo de fábrica: tránsito, aduana, certificación/listado aceptable para el
AHJ, y transporte interno. La certificación es la que más sorprende: un equipo
sin listado reconocido puede ser rechazado en inspección aunque esté instalado.

## Submittals y RFI

**Submittals** — el contratista somete a aprobación antes de comprar: hojas de
datos, certificados de listado, planos de taller, curvas de protección, cartas
de conformidad de SCCR. Registro en `plantillas/submittal-log.csv`.

Someter temprano lo que tiene entrega larga, aunque la ingeniería de detalle no
esté cerrada. Un submittal aprobado tarde arrastra todo el programa.

**RFI** — toda ambigüedad se resuelve por escrito, no en la obra. Registro en
`plantillas/rfi-log.csv`. Un RFI sin responder más de una semana es un riesgo
activo, no un pendiente administrativo.

## Permisos e inspecciones

**Texas:** el trabajo eléctrico no exento requiere contratista con licencia de
TDLR. El permiso y la inspección los administra el municipio, que puede tener
enmiendas locales al código adoptado. Confirmar con el AHJ **antes** de cerrar
el diseño: los ciclos de inspección y la disponibilidad de inspector marcan
fechas que no se pueden comprimir.

**México:** la verificación la realiza una Unidad de Verificación acreditada. El
expediente incluye la memoria técnica, planos y evidencia de pruebas. La
contratación de la UVIE y la disponibilidad de fecha se agendan con
anticipación, no al final.

**Programar los hitos de inspección como actividades con duración**, no como
eventos instantáneos. Y contemplar el reproceso: una inspección rechazada
consume el mismo tiempo dos veces.

## Control de cambios

Todo cambio pasa por: descripción, impacto en costo, impacto en programa,
impacto en **cumplimiento normativo**, aprobación escrita. La cuarta columna es
la que se olvida y la que puede invalidar el dictamen.

Cambios que suelen entrar "de gratis" y no lo son: agregar cargas después del
cálculo, mover un tablero (cambia longitudes, caída y espacio de trabajo),
sustituir marca de equipo (cambia SCCR y curvas), agregar un cargador de VE.
Cada uno obliga a recalcular.

## Matriz de riesgos

Plantilla en `plantillas/matriz-de-riesgos.md`. Riesgos recurrentes en este
tipo de proyecto:

- Icc real distinta de la supuesta → SCCR insuficiente → equipo devuelto
- Equipo importado sin listado aceptable para el AHJ → rechazo en inspección
- Espacio de trabajo insuficiente descubierto en obra → reubicación de tablero
- Interferencia con otras especialidades en trayectorias
- Ventana de paro para energización no disponible en operación continua
- Variación del precio del cobre entre cotización y compra
- Rotación de personal con licencia
- Cambio de edición normativa entre diseño y ejecución (relevante en Texas con
  la transición del NEC 2023 al 2026)

## Cierre

Dossier de entrega: planos as-built, memoria de cálculo final, certificados de
listado, protocolos de prueba firmados, dictamen o acta de inspección, manuales,
garantías, y directorio de tableros actualizado. Capacitación al personal de
operación y mantenimiento.

**Un proyecto sin dossier no está cerrado**, aunque esté energizado y facturado.
Y es lo primero que pide el cliente cuando hay una falla o una aseguradora
cuando hay un siniestro.
