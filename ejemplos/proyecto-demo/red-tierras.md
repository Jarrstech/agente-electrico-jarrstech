# Memoria de cálculo — Red de tierras

**Proyecto:** Panificadora Demo - Ampliacion tablero general  
**Subestación:** Subestacion 300 kVA, 13.8 kV (TR-1)  
**Método:** IEEE Std 80-2000, suelo uniforme  
**Fecha:** 2026-09-23

> **Documento preliminar.** Requiere revisión, validación y firma de un responsable técnico con licencia vigente. La resistencia de la malla se mide en campo (IEEE Std 81) antes de energizar.

## 1. Datos de entrada

| Parámetro | Valor | Tipo | Origen |
|---|---|---|---|
| Resistividad del terreno | 50.0 Ω·m | Dato de sitio | Dato de ejemplo |
| Tensión en el punto de entrega | 13.8 kV | Dato del suministrador | Dato de ejemplo |
| Potencia de cortocircuito trifásica | 525.8 MVA | Dato del suministrador | Dato de ejemplo |
| Potencia de cortocircuito monofásica | 400 MVA | Dato del suministrador | Dato de ejemplo |
| Relación X/R | 10 | Dato del suministrador |  |
| Tiempo de choque ts | 0.5 s | [CRITERIO] | Protección |
| Tiempo para el conductor tc | 0.5 s | [CRITERIO] | Protección de respaldo |
| Factor de división Sf | 0.2 | [CRITERIO] | 1.0 = conservador |
| Conductor | 4/0 Cobre comercial, estirado duro | [CRITERIO] | Proyecto |
| Profundidad de la malla | 0.6 m | [CRITERIO] | Proyecto |
| Capa superficial | 3000.0 Ω·m | [CRITERIO] |  |
| Peso corporal | 50 kg | [CRITERIO] | IEEE Std 80 |

## 2. Corriente de falla

Icc = MVA × 1000 / (√3 × kV). Corriente de la malla: IG = Df × Sf × 3I0, con Df = √(1 + (Ta/tf)(1 − e^(−2tf/Ta))) y Ta = X/(ωR).

| Concepto | Valor |
|---|---|
| Icc trifásica | 21,998 A |
| Corriente de falla a tierra 3I0 (monofasica del suministrador) | 16,735 A |
| Df (ts) | 1.0262 |
| Sf | 0.2 |
| Corriente de la malla IG | 3,435 A |
| Corriente para el conductor (Df × 3I0) | 17,173 A |

## 3. Conductor de la malla

A = I / √[(TCAP × 10⁻⁴ / (tc αr ρr)) × ln((K0 + Tm)/(K0 + Ta))], con I en kA y A en mm² (IEEE Std 80, constantes de la Tabla 1).

| Concepto | Valor |
|---|---|
| Material | Cobre comercial, estirado duro |
| Tm / Ta / tc | 1084.0 °C / 40.0 °C / 0.5 s |
| Sección mínima | 43.5 mm² (1/0) |
| Conductor elegido | 4/0 (107.2 mm²) |

## 4. Tensiones tolerables

Cs = 1 − 0.09 (1 − ρ/ρs) / (2hs + 0.09) = 0.7731. Para 50 kg y ts = 0.5 s:

| Tensión | Tolerable |
|---|---|
| Toque: (1000 + 1.5 Cs ρs) k / √ts | 735 V |
| Paso: (1000 + 6 Cs ρs) k / √ts | 2,447 V |

## 5. Malla, resistencia y tensiones calculadas

| Concepto | Valor |
|---|---|
| Dimensiones | 20.0 × 15.0 m (300.0 m²) |
| Conductores | 4 a lo largo × 5 a lo ancho, separación 5.0 m |
| Varillas | 4 de 3.05 m en el perímetro |
| LC / LR / LT | 155.0 / 12.2 / 167.2 m |
| n / Ki / Km / Ks | 4.451 / 1.303 / 0.7612 / 0.3741 |
| Resistencia Rg (Sverak) | 1.503 Ω |
| GPR = IG × Rg | 5,164 V |
| Tensión de malla Em = ρ Km Ki IG / LM | 969 V |
| Tensión de paso Es = ρ Ks Ki IG / LS | 661 V |

## 6. Verificación

| Criterio | Calculado | Límite | Resultado |
|---|---|---|---|
| Sección del conductor | 107.2 mm² (4/0) | >= 43.5 mm² | CUMPLE |
| Tensión de malla Em contra toque tolerable | 969 V | <= 735 V | NO CUMPLE |
| Tensión de paso Es contra paso tolerable | 661 V | <= 2447 V | CUMPLE |
| Elevación de potencial GPR contra toque tolerable | 5164 V | <= 735 V | NO CUMPLE (revisar Em y Es) |

**Resultado:** NO CUMPLE.

## 7. Configuración que cumple

Con separación de 3.17 m (6 × 7 conductores) y 4 varillas de 3.05 m en el perímetro: Rg = 1.415 Ω, Em = 664 V ≤ 735 V y Es = 684 V ≤ 2,447 V.

## 8. Supuestos y avisos

- Sf = 0.2: requiere justificacion (estudio de division de corriente).

## 9. Límites del cálculo

- Modelo de suelo uniforme; con resistividad variable en profundidad se requiere un modelo de dos capas.
- No evalúa potenciales transferidos (tuberías, rieles, cercas) ni la zona fuera del perímetro de la malla.
- La resistencia real se mide en campo antes de energizar y se registra en el dossier.
