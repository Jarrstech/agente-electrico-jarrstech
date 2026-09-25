# Reglas del repositorio

Este repositorio produce ingeniería eléctrica que se construye e inspecciona.

1. **Cargar siempre `ingenieria-electrica-core` antes de cualquier cálculo.**
2. **Nunca inventar un valor normativo.** Ampacidades, factores, capacidades y
   calibres de tierra salen de `datos/*.json` vía `scripts/ec.py`. Si el script
   devuelve `DATO_FALTANTE`, preguntar al usuario. No estimar, no interpolar,
   no decir "típicamente".
3. **Declarar la jurisdicción y la edición** (`config/jurisdiccion.yaml`) antes
   de calcular. Nunca mezclar NEC y NOM en un mismo entregable.
4. **Correr los scripts aunque el resultado parezca obvio.** El valor está en
   que el número sea reproducible.
5. **Distinguir requisito normativo de criterio de proyecto** en toda salida.
6. **Validar el unifilar después de cada edición**
   (`python3 scripts/unifilar.py validar`). Un ERROR bloquea la emisión.
7. **Listar los supuestos visiblemente.** Un supuesto oculto invalida la
   memoria completa ante un verificador.
8. **Recordar que el entregable requiere firma de un responsable con licencia.**
   Decirlo cuando el usuario esté por usar la salida como documento final.
9. **Declarar la conexión de cada carga** en la columna `fases`: 1 = fase-neutro
   (p. ej. 277 V en 480Y/277), 2 = fase-fase (480 V), 3 = trifásica. Pasar
   `--unifilar` a `ec.py circuito` para verificar la tensión contra su tablero.

10. **Proyectos capturados en la interfaz** (`python scripts/interfaz.py`) viven en
   `proyectos/<id>/`. Para ese proyecto, usar sus `jurisdiccion.yaml`,
   `proyecto.yaml`, `cargas.csv`, `unifilar.json` y `red-de-tierras.yaml` en vez
   de los de `config/`. `bitacora.json` trae los pasos corridos, los datos
   pendientes y los comandos exactos para reproducirlos.

Datos que nunca se asumen y siempre se piden: Icc disponible, temperatura
ambiente, longitudes reales, temperatura de terminales del equipo, resistencia
medida de tierra, clasificación del área, kVA y Z% de placa de cada
transformador, resistividad del terreno y potencia de cortocircuito del
suministrador.

En Windows, usar `python` en lugar de `python3`.
