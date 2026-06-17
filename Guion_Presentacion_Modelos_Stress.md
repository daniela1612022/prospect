# Guión de Presentación
## Modelos de Simulación para Stress Testing Prospectivo
### Evaluación comparativa de alternativas al GBM y calibración dinámica de pesos

---

> **Cómo usar este guión:**  
> Cada sección corresponde a un slide de la presentación.  
> El texto en *cursiva* son notas para el presentador (no se leen en voz alta).  
> El texto normal es lo que se dice al público.

---

## SLIDE 1 — Portada

*[Abrir el archivo. Esperar a que la audiencia esté atenta.]*

**Lo que se dice:**

"Hoy vamos a hablar de un problema concreto en el proceso de stress testing prospectivo: el modelo de simulación no estaba siendo suficientemente conservador. Vamos a ver por qué, qué alternativas evaluamos, y cómo resolvimos el problema de forma sistemática y replicable.

El tema tiene consecuencia directa sobre gestión y regulación: cuando el stress arroja una pérdida menor que el VaR, los límites y alertas calibrados contra ese stress quedan subestimados."

---

## SLIDE 2 — Agenda

*[Recorrer los ítems en 20 segundos.]*

**Lo que se dice:**

"La presentación tiene nueve bloques. Empezamos con las limitaciones del modelo actual. Luego presentamos los cuatro modelos candidatos y cómo los comparamos. La segunda mitad se enfoca en la calibración dinámica de pesos: por qué la necesitamos, cómo aprende del histórico de VaR y cómo se ejecuta."

---

## SLIDE 3 — Limitaciones del GBM

*[Núcleo del argumento. Tomar 3-4 minutos. El número −88.5B vs −113.4B es el anclaje emocional.]*

**Lo que se dice:**

"El modelo actual es el Movimiento Browniano Geométrico. La idea central: el precio de mañana es el precio de hoy multiplicado por un factor exponencial que tiene un drift y un ruido gaussiano.

Ese supuesto de Normalidad es el primer problema. Los retornos financieros —especialmente en mercados emergentes— tienen colas más pesadas que una Normal. Los eventos extremos ocurren con mayor frecuencia de lo que GBM predice.

El segundo problema: GBM tiene volatilidad constante. En una crisis la volatilidad se dispara y permanece alta durante semanas —volatility clustering— y el GBM es completamente ciego a eso.

Tercero: GBM es un proceso continuo. No puede generar un salto brusco de 200 pesos en el USDCOP en un solo día. Sin embargo, eso ocurre. El JD de Merton fue diseñado específicamente para esto.

El cuarto problema es el que generó la alarma práctica: el stress prospectivo arrojaba −88.5 billones de pesos, mientras el VaR histórico era de −113.4 billones. Una brecha del 22%. Eso no es aceptable."

---

## SLIDE 4 — Los Cuatro Modelos (overview)

*[Vista general. No entrar en detalle todavía. 90 segundos.]*

**Lo que se dice:**

"Para resolver esto evaluamos cuatro modelos. El GBM quedó como baseline.

**Jump-Diffusion de Merton**: GBM más una componente de saltos discretos modelados como proceso de Poisson. Candidato principal para factores con eventos extremos identificables.

**ARMA(1,1)**: modelo de series de tiempo que captura autocorrelación de retornos. Si el retorno de ayer fue negativo, hay cierta probabilidad de que el de hoy también lo sea. GBM ignora eso.

**ARMA-GARCH**: extensión del ARMA donde la varianza no es constante sino que evoluciona en el tiempo según sus propios valores pasados. Captura volatility clustering directamente."

---

## SLIDE 5 — GBM vs Jump-Diffusion de Merton

*[Slide técnico. Apoyarse en las dos columnas.]*

**Lo que se dice:**

"En GBM, el retorno acumulado es drift más difusión. Continuo. La volatilidad sigma es constante.

En JD, la ecuación tiene tres términos. Primero, un drift ajustado: se le resta `lambda × k_barra`, donde lambda es la frecuencia de saltos y k_barra es la corrección de Merton de 1976 para que el precio sea un martingala. Sin esta corrección, los saltos introducen un drift espúreo.

El segundo término es la difusión gaussiana de los días normales. El tercero es la suma de saltos donde cada J_i sigue una Normal con su propia media y varianza.

La calibración es automática: tomamos 250 días de retornos, calculamos la desviación estándar total, y clasificamos como salto cualquier retorno que supere 2.5 sigmas. La frecuencia histórica de esos eventos nos da lambda. Si hay menos de tres saltos, el modelo degrada a GBM automáticamente."

---

## SLIDE 6 — ARMA(1,1) y ARMA-GARCH

*[Si la audiencia no es técnica, pasar por encima de ecuaciones y enfocarse en la intuición.]*

**Lo que se dice:**

"ARMA dice que el retorno de hoy depende del retorno de ayer y del error de ayer. Se calibra por máxima verosimilitud y la simulación avanza día a día.

ARMA-GARCH agrega una ecuación para la varianza. La varianza de hoy es un promedio ponderado del término constante, del cuadrado del error de ayer —que captura si hubo un shock reciente— y de la varianza de ayer.

La intuición práctica: si hoy hay una caída fuerte del mercado, ARMA-GARCH predice que mañana la distribución de retornos tendrá colas más pesadas. GBM no tiene esa capacidad."

---

## SLIDE 7 — Metodología del Torneo

*[Énfasis en la semilla compartida como garantía de fairness.]*

**Lo que se dice:**

"Para comparar los modelos de forma objetiva diseñamos el Torneo de Modelos.

Primero, construimos la distribución empírica de referencia: retornos logarítmicos acumulados a 20 días usando ventanas solapadas con paso de 5 días sobre el histórico.

Segundo, calibramos cada modelo sobre los mismos 250 días. Tercero, simulamos 1,000 trayectorias de 20 días. El punto clave: **todos los modelos usan la misma semilla aleatoria**, para que las diferencias reflejen el modelo, no el azar.

Cuarto, calculamos cinco métricas de comparación. Quinto, el composite rank: promedio de las posiciones de cada modelo. El modelo con menor composite rank es el ganador.

Evaluamos 10 factores reales: cinco de FX, tres de renta variable local y dos internacional."

---

## SLIDE 8 — Las 5 Métricas de Evaluación

*[No hace falta leer las fórmulas. Explicar la lógica de cada una.]*

**Lo que se dice:**

"Las cinco métricas cubren aspectos distintos de la distribución. En todas, menor es mejor.

La **distancia KS** mide la máxima diferencia entre las distribuciones acumuladas simulada y empírica. Evalúa la forma completa.

Los **errores de percentil P05 y P95** son los más relevantes para riesgo: qué tan bien el modelo captura las colas. Si el modelo subestima el P05 empírico, está subestimando los peores escenarios.

El **error de volatilidad** mide si la dispersión total de los escenarios simulados coincide con la dispersión histórica a 20 días.

El **error de curtosis** captura las colas pesadas. Un modelo que genere retornos demasiado normales tendrá curtosis cercana a cero, mientras que la curtosis empírica de mercados emergentes suele estar entre 3 y 8."

---

## SLIDE 9 — Resultados del Torneo

*[Conclusión empírica más importante. Tomar tiempo con la tabla.]*

**Lo que se dice:**

"Para FX de mercados emergentes —USDCOP, USDCLP, USDBRL— el ganador es consistentemente Jump-Diffusion. La razón: estas divisas tienen saltos identificables que Poisson captura mucho mejor que una Normal.

Para divisas de mercados desarrollados —EURUSD, GBPUSD— gana ARMA-GARCH. No hay saltos tan pronunciados, pero sí episodios de alta volatilidad persistente que GARCH modela directamente.

Para renta variable local —ECOPETROL, ICOLCAP— gana JD. La asimetría y la correlación con el precio del petróleo generan colas izquierdas que JD captura bien.

Para renta variable internacional —SPY, XLF— gana ARMA-GARCH. Los crashes son rápidos y la recuperación también, y GARCH calibra esa persistencia mejor que Poisson.

**GBM queda en tercer o cuarto lugar en prácticamente todos los factores evaluados.**"

---

## SLIDE 10 — ¿Por Qué la Calibración Dinámica de Pesos?

*[Conectar el problema técnico con la consecuencia práctica.]*

**Lo que se dice:**

"Incluso con JD o ARMA-GARCH, podemos tener una brecha si la volatilidad calibrada no está correctamente escalada para cada factor.

El problema tiene cuatro causas. Primera: la reducción uniforme del 10% en sigma aplica igual a USDCOP que a GBPUSD, sin diferenciar por factor.

Segunda: en crisis las correlaciones entre activos aumentan. El modelo asume correlaciones estables.

Tercera: hay factores sub-representados. BAAA2, BAAA3, COUSD y CECUVR tienen pesos bajos por defecto pero el VaR muestra que son significativos.

Cuarta: antes los pesos se ajustaban manualmente mes a mes, sin criterio sistemático ni trazabilidad.

La calibración dinámica resuelve esto: **los pesos se aprenden del histórico de VaR del servidor**, no se definen a mano."

---

## SLIDE 11 — Cómo Funciona la Calibración Dinámica

*[Este es el slide más importante de esta sección. El mensaje central: aprende, no lee.]*

**Lo que se dice:**

"El mecanismo de calibración dinámica tiene cuatro etapas.

**Primera — Consulta al servidor de VaR histórico:**  
El sistema no toma un archivo estático. Consulta el historial de resultados de VaR almacenado en el servidor: todos los choques máximos que ha generado cada factor de riesgo a lo largo del tiempo.

**Segunda — Ponderación temporal (EWMA):**  
No todos los períodos tienen el mismo peso. Se aplica una ponderación exponencial que asigna mayor importancia a las observaciones más recientes. Un choque de hace tres meses pesa menos que uno de la semana pasada. Esto permite que el modelo se adapte rápidamente a cambios de régimen.

**Tercera — Normalización por clase de activo:**  
Dentro de cada grupo —Tasa de Cambio, Curva de Tasas, Renta Variable, Indicadores— se calcula la posición relativa de cada factor. El de mayor choque ponderado recibe el mayor peso de volatilidad.

**Cuarta — Actualización continua del JSON de configuración:**  
Los pesos resultantes sobrescriben el archivo de configuración. La próxima simulación hereda automáticamente la calibración más reciente sin intervención manual.

Esto convierte los pesos en una señal viva que aprende del mercado, no en un número que alguien ajustó la última vez que recordó hacerlo."

---

## SLIDE 12 — Ponderación Temporal: El Corazón del Sistema

*[Slide nuevo que explica el EWMA. Usar la analogía para hacerlo accesible.]*

**Lo que se dice:**

"La ponderación exponencial es el elemento diferenciador frente a tomar simplemente el choque máximo histórico.

La idea es intuitiva: si el USDCOP tuvo un salto fuerte hace 200 días pero los últimos 30 días han sido tranquilos, ¿debería ese salto antiguo dominar el peso de volatilidad hoy? La respuesta es no, no con el mismo peso que si hubiera ocurrido la semana pasada.

La fórmula asigna a cada observación un peso que decrece exponencialmente con el tiempo: w(t) = λ^t donde λ es el factor de decaimiento —por ejemplo 0.94, que es el estándar EWMA de RiskMetrics.

Con λ = 0.94:  
- Una observación de hace 1 día tiene peso 0.94  
- De hace 20 días: 0.94^20 ≈ 0.29  
- De hace 60 días: 0.94^60 ≈ 0.025  

El choque ponderado de cada factor es entonces el promedio de su historia con estos pesos. Factores que han sido volátiles recientemente reciben mayor peso de volatilidad en la próxima simulación. Factores que se han calmado reciben menor peso.

Esto es calibración adaptativa, no calibración retrospectiva fija."

---

## SLIDE 13 — Arquitectura del Sistema de Pesos

*[Slide de arquitectura. Explicar la jerarquía de tres niveles.]*

**Lo que se dice:**

"El peso resultante de la calibración dinámica actúa como multiplicador de volatilidad en cada modelo: en GBM es `sigma × 0.90 × peso_factor`, en HJM se aplica nodo a nodo, en JD afecta la componente de difusión.

La jerarquía tiene tres niveles de prioridad.

El más alto es el **override individual**: si el analista define explícitamente un peso para USDCOP, ese valor prevalece sobre cualquier calibración automática. Es el nivel de máxima granularidad para casos excepcionales.

El segundo es el **peso de categoría**: todos los factores de 'Divisas_Mayor_Impacto' heredan el peso de su categoría si no tienen un override.

El tercero es el **peso global por defecto**: aplica cuando un factor nuevo no está clasificado en ninguna categoría conocida.

Esta jerarquía permite que la calibración dinámica opere en modo automático la mayor parte del tiempo, con la posibilidad de intervención quirúrgica cuando el analista tiene información adicional que el historial no captura."

---

## SLIDE 14 — Métodos de Calibración: Min-Max vs Percentil

*[Slide comparativo. Usar los ejemplos numéricos para ilustrar la diferencia.]*

**Lo que se dice:**

"Una vez que el sistema tiene el choque ponderado de cada factor, necesita convertirlo en un peso entre un mínimo y un máximo configurados. Para esa conversión hay dos métodos.

El **método Min-Max** hace una escala lineal proporcional. El factor con el mayor choque ponderado dentro de su grupo recibe el peso máximo —digamos 2.0—. El de menor choque recibe el peso mínimo —0.6—. Los demás se interpolan linealmente según su magnitud relativa.

El **método Percentil** usa la posición ordinal dentro del grupo, no la magnitud absoluta. Si hay 10 factores de tasa de cambio, el quinto más alto recibe exactamente la mitad del rango disponible.

La diferencia práctica: si USDCOP tiene un choque de 500 y USDBRL uno de 490 —muy similares— Min-Max les asigna pesos casi idénticos, lo cual es correcto. Pero si hay un factor outlier con choque de 2,000, Min-Max comprime todos los demás hacia el mínimo. Ahí es donde Percentil es más robusto.

**Recomendación**: Min-Max por defecto. Percentil cuando hay un factor con choque claramente outlier."

---

## SLIDE 15 — Proceso Paso a Paso

*[Slide operativo. Leer los pasos como checklist. Aquí la audiencia operativa toma nota.]*

**Lo que se dice:**

"El proceso completo tiene seis pasos.

**Paso 1**: El servidor actualiza el histórico de VaR Zeros al cierre del período. No hay acción manual aquí.

**Paso 2**: El sistema consulta ese histórico y extrae para cada factor la serie temporal de choques. Aplica la ponderación EWMA para calcular el choque efectivo ponderado por período.

**Paso 3**: Dentro de cada clase de activo, normaliza los choques ponderados con el método elegido —Min-Max o Percentil— y obtiene el peso de volatilidad.

**Paso 4**: Mapea los nombres del servidor a las claves internas del modelo. El servidor puede usar 'USD/COP' donde el modelo usa 'USDCOP'. La tabla de mapeo cubre más de 45 factores incluyendo nodos de curva.

**Paso 5**: Actualiza el JSON de configuración con los nuevos pesos. El sistema imprime un diagnóstico completo: factor, choque ponderado, peso asignado.

**Paso 6**: La próxima ejecución de simulación usa automáticamente estos pesos. Se verifica en la pestaña 'Pesos_Aplicados' del Excel de resultados."

---

## SLIDE 16 — Comparativa de Enfoques

*[Slide de síntesis.]*

**Lo que se dice:**

"Comparemos los tres enfoques.

**Sin pesos**: sigma uniforme multiplicado por 0.90. El stress llega al 78% del VaR. Solo sirve como baseline.

**Pesos manuales** —versión 2.7—: el analista subió pesos de BAAA2, BAAA3, COUSD y CECUVR a 1.5 manualmente. El stress mejora al 88% del VaR, pero depende del criterio de una persona y no tiene trazabilidad directa con el VaR actual.

**Calibración dinámica**: los pesos se aprenden del histórico de VaR con ponderación temporal. El stress llega al 95-100% del VaR objetivo. El proceso es completamente auditable: cada peso tiene un choque histórico ponderado que lo justifica, y se actualiza automáticamente con cada nuevo dato del servidor.

La calibración dinámica no solo mejora el resultado: elimina la dependencia del criterio del analista y crea un proceso reproducible."

---

## SLIDE 17 — Código de Implementación

*[Para audiencia técnica. Si no, pasar rápido.]*

**Lo que se dice:**

"La implementación son tres bloques.

El primero llama a `calibrar_pesos_desde_var` apuntando al historial del servidor. El sistema aplica el EWMA, normaliza y actualiza el JSON.

El segundo es opcional: si hay factores que necesitan ajuste puntual por información no disponible en el historial, se puede sobrescribir ese factor específico sin tocar los demás.

El tercero corre la simulación completa con JD, que hereda automáticamente los pesos actualizados."

---

## SLIDE 18 — Conclusiones

*[Cerrar fuerte. Cinco conclusiones, cinco acciones.]*

**Lo que se dice:**

"Cinco conclusiones.

Primero: GBM ya no es el mejor modelo. Queda consistentemente en tercer o cuarto lugar en el torneo.

Segundo: Jump-Diffusion gana en FX emergente y renta variable local. La calibración es automática y la mejora en colas es significativa.

Tercero: ARMA-GARCH es superior para mercados desarrollados donde domina el volatility clustering.

Cuarto: la calibración dinámica elimina la brecha Stress-VaR, pasando del 78% al 95-100% de cobertura, con trazabilidad completa.

Quinto: el proceso deja de depender del criterio puntual del analista. Los pesos aprenden del histórico, ponderan lo reciente y se actualizan solos con cada nuevo dato del servidor."

---

## SLIDE 19 — Cierre

*[Abrir preguntas. Tener los archivos del torneo listos para mostrar en vivo.]*

**Lo que se dice:**

"Esto es todo. Los archivos de referencia están en el repositorio. Quedamos abiertos a preguntas."

---

---

# INSTRUCCIONES PARA DISEÑO DE SLIDES COMPARATIVOS

> Esta sección es una guía de diseño para quien elabore o actualice los slides de comparación de modelos y de calibración dinámica.

---

## INSTRUCCIÓN 1 — Slide comparativo de modelos (dos columnas)

**Cuándo usar este formato:** Para comparar GBM vs un modelo alternativo (JD, ARMA, ARMA-GARCH).

**Estructura:**
```
┌─────────────────────────┬─────────────────────────┐
│  MODELO BASE (GBM)      │  MODELO ALTERNATIVO      │
│  Color: azul medio      │  Color: verde            │
├─────────────────────────┼─────────────────────────┤
│  Título del modelo      │  Título del modelo       │
│  (negrita, blanco)      │  (negrita, blanco)       │
├─────────────────────────┼─────────────────────────┤
│  Ecuación               │  Ecuación completa       │
│  (fondo azul claro)     │  (fondo verde claro)     │
├─────────────────────────┼─────────────────────────┤
│  Calibración            │  Calibración             │
│  · μ = ...              │  · μ_d, σ_d = difusión   │
│  · σ = ...              │  · λ = frecuencia saltos │
├─────────────────────────┼─────────────────────────┤
│  Supuestos              │  Ventajas                │
│  (fondo gris claro)     │  (fondo verde muy claro) │
├─────────────────────────┼─────────────────────────┤
│  Limitación clave       │  Fallback si falla       │
│  (borde y texto rojo)   │  (texto gris)            │
└─────────────────────────┴─────────────────────────┘
```

**Reglas:**
- La columna izquierda siempre es el baseline (GBM) en azul.
- La columna derecha es el modelo nuevo en el color de su categoría.
- La ecuación debe ir en un recuadro con fondo diferenciado.
- Las limitaciones del GBM van con borde rojo o ícono ✗.
- Las ventajas del modelo nuevo van con borde verde o ícono ✓.
- La flecha `→` o `EXTIENDE` entre columnas indica la relación.

---

## INSTRUCCIÓN 2 — Slide de tabla de resultados del torneo

**Cuándo usar:** Para mostrar qué modelo ganó por categoría de factor.

**Estructura de la tabla:**
```
┌──────────────┬──────────────┬────────────────┬────────────┬─────────────────────────────────┐
│ Categoría    │ Característ. │ Ganador        │  2do lugar │ Por qué                         │
│ (negrita)    │ del factor   │ (fondo verde)  │ (azul)     │ (texto explicativo, 2 líneas)   │
├──────────────┼──────────────┼────────────────┼────────────┼─────────────────────────────────┤
│ FX Emergente │ Alta vol.    │ 🥇 JD (Merton) │🥈 ARMA-G   │ Saltos identificables λ alta... │
│ FX Desarrolld│ Clustering   │ 🥇 ARMA-GARCH  │🥈 JD       │ Volatility clustering...        │
│ RV Local     │ Cola izq.    │ 🥇 JD (Merton) │🥈 ARMA-G   │ Alta curtosis, petróleo...      │
│ RV Internac. │ Crash asim.  │ 🥇 ARMA-GARCH  │🥈 JD       │ GARCH captura asimetría...      │
└──────────────┴──────────────┴────────────────┴────────────┴─────────────────────────────────┘
```

**Reglas:**
- El encabezado en azul oscuro con texto blanco.
- Las filas alternan entre blanco y gris claro.
- La celda del ganador siempre tiene fondo verde claro y texto verde.
- La conclusión va en una barra azul oscura debajo de la tabla, texto amarillo.
- Nunca mostrar más de 5 filas en la tabla para mantener legibilidad.

---

## INSTRUCCIÓN 3 — Slide de métricas (cuadrícula 2×3 o 1×5)

**Cuándo usar:** Para explicar las cinco métricas del torneo.

**Estructura por tarjeta de métrica:**
```
┌──────────────────────┐
│  COLOR DE CATEGORÍA  │  ← Header de color sólido (altura: 0.55")
│  Nombre métrica      │  ← Texto blanco, negrita 14pt
├──────────────────────┤
│  Subtítulo           │  ← Negrita, color del header, 11pt
│                      │
│  Descripción         │  ← Texto gris oscuro, 10pt, 3 líneas max
│  (qué mide y cuándo  │
│   es crítico)        │
│                      │
│  ┌──────────────────┐│
│  │ fórmula          ││  ← Fondo muy claro, borde del color, negrita
│  └──────────────────┘│
└──────────────────────┘
```

**Reglas:**
- Cada métrica tiene su propio color. Sugerido: KS=azul, P05=rojo, P95=naranja, Vol=verde, Curtosis=púrpura.
- La fórmula va siempre en un sub-recuadro con fondo diferenciado.
- 6 tarjetas en cuadrícula 2×3 si se añade Composite Rank como sexta, 1×5 si no.

---

## INSTRUCCIÓN 4 — Slide de calibración dinámica (flujo vertical)

**Cuándo usar:** Para explicar el proceso de aprendizaje del histórico de VaR.

**Estructura:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│  SERVIDOR DE HISTÓRICO VaR                                              │
│  "Historial de choques por factor — actualización continua"             │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PONDERACIÓN TEMPORAL (EWMA   λ = 0.94)                                 │
│  "Lo reciente pesa más. Un choque de hace 60 días vale 2.5% de uno hoy" │
│  w(t) = λ^t    →    choque_efectivo = Σ w(t) × choque(t) / Σ w(t)     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  NORMALIZACIÓN POR CLASE DE ACTIVO                                      │
│  FX   |   Curvas   |   RV   |   Indicadores                            │
│  Min-Max o Percentil dentro de cada grupo                               │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PESO DE VOLATILIDAD POR FACTOR                                         │
│  peso_factor ∈ [p_min, p_max]   →   σ_sim = σ_hist × 0.90 × peso       │
│  Se guarda en pesos_factores_stress.json                                │
└─────────────────────────────────────────────────────────────────────────┘
```

**Reglas:**
- El flujo es **siempre vertical** (de arriba hacia abajo), con flechas entre bloques.
- Cada bloque tiene su propio color: servidor=azul oscuro, EWMA=verde, normalización=naranja, resultado=azul medio.
- El bloque EWMA es el más importante visualmente: debe ser más grande o tener un recuadro interior con la fórmula.
- Nunca llamar a esto "lee un Excel estático". El mensaje es: **consulta el servidor, aprende del histórico, pondera lo reciente**.

---

## INSTRUCCIÓN 5 — Slide comparativo de enfoques (tres columnas)

**Cuándo usar:** Para comparar Sin pesos / Pesos manuales / Calibración dinámica.

**Estructura:**
```
┌──────────────────┬──────────────────┬──────────────────┐
│  SIN PESOS       │  PESOS MANUALES  │  CALIB. DINÁMICA │
│  (header rojo)   │  (header naranja)│  (header verde)  │
├──────────────────┼──────────────────┼──────────────────┤
│  σ × 0.90        │  σ × 0.90 × k   │  σ × 0.90 × w(t) │
│  (fórmula)       │  (fórmula)       │  (fórmula)       │
├──────────────────┼──────────────────┼──────────────────┤
│  Bullets:        │  Bullets:        │  Bullets:        │
│  · Sin diferenc. │  · Ajuste ad-hoc │  · Aprendizaje   │
│  · Stress = 78%  │  · Stress = 88%  │  · Stress = 95%+ │
│  · No auditable  │  · No replicable │  · Trazable      │
├──────────────────┼──────────────────┼──────────────────┤
│  Cuándo usar:    │  Cuándo usar:    │  Cuándo usar:    │
│  Solo baseline   │  Sin historial   │  Estándar mensual│
└──────────────────┴──────────────────┴──────────────────┘
```

**Reglas:**
- El porcentaje de cobertura del VaR (78%, 88%, 95%+) debe ser el elemento más grande de cada columna.
- Las tres fórmulas deben estar alineadas horizontalmente para facilitar la comparación.
- Nunca usar el mismo color para dos columnas.
- La columna de calibración dinámica debe ser visualmente la más destacada (borde más grueso o color de fondo levemente diferente).

---

## INSTRUCCIÓN 6 — Normas generales de diseño para toda la presentación

| Elemento | Especificación |
|---|---|
| Fondo base | Gris muy claro (#F0F2F5) o blanco |
| Barra de título | Azul oscuro (#1A375E), texto blanco |
| Pie de página | Azul oscuro, texto azul claro, fuente 9pt |
| Fuente títulos | Sans-serif, 22pt, negrita, blanco |
| Fuente cuerpo | Sans-serif, 11-12pt, gris oscuro (#404040) |
| Fuente código | Monospace, 10pt, fondo #1E1E1E, texto claro |
| Color positivo | Verde (#1E7E4A) |
| Color alerta | Rojo (#C0202A) |
| Color neutro/énfasis | Naranja (#E07B10) |
| Color acento | Amarillo (#FFD700) solo sobre fondo oscuro |
| Máximo texto por slide | 80 palabras en cuerpo (excluye ecuaciones) |
| Máximo bullets | 5 por cuadro |
| Imágenes/íconos | Solo si añaden información; nunca decorativos |

---

## PREGUNTAS FRECUENTES Y RESPUESTAS PREPARADAS

### P: ¿Por qué umbral de 2.5 sigmas para clasificar saltos en JD?

**R:** Es el valor estándar en la literatura calibrado con mercados emergentes. Un retorno de 2.5 sigmas en el USDCOP equivale históricamente a movimientos de 180-200 pesos en un día, que corresponden a eventos como intervenciones del Banco de la República o shocks de commodities. El umbral es configurable por factor.

---

### P: ¿Cómo se determina el factor de decaimiento λ del EWMA?

**R:** El valor 0.94 es el estándar de RiskMetrics para datos diarios. Corresponde a una vida media de aproximadamente 12 días: los choques de hace 12 días tienen la mitad del peso que los de hoy. Para mercados más volátiles puede usarse 0.97 para dar más persistencia a los choques pasados. El sistema permite configurar este parámetro por tipo de activo.

---

### P: ¿ARMA-GARCH no es demasiado complejo para producción?

**R:** La calibración es completamente automática mediante el paquete `arch`. Si ARMA-GARCH falla, el sistema cae a ARMA; si ARMA falla, cae a GBM. Nunca hay un fallo silencioso. El tiempo adicional frente a GBM es del orden de 2-5 segundos por factor.

---

### P: ¿La calibración dinámica puede generar pesos extremos?

**R:** No. El JSON tiene parámetros `peso_minimo` y `peso_maximo` que actúan como límites duros —por defecto 0.6 y 2.0—. Ningún factor puede salir de ese rango independientemente de su choque ponderado. Esto protege contra outliers extremos en el historial.

---

### P: ¿Cómo validamos que el nuevo modelo es mejor?

**R:** El Torneo de Modelos es exactamente esa validación: corre los cuatro modelos sobre el histórico real y entrega el composite rank. Adicionalmente, `Razonabilidad_Estres_Prospectivo.py` compara el stress resultante contra el VaR para detectar brechas. Torneo + razonabilidad es el proceso de validación completo.

---

## TABLAS DE REFERENCIA TÉCNICA

### Parámetros del sistema

| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| `nSim` | 1,500 | Simulaciones Monte Carlo |
| `n_max_proyeccion` | 20 días | Horizonte de stress |
| `n_max_historia` | 250 días | Ventana de calibración |
| `nCPs` | 3 | Componentes principales (curvas) |
| `jump_threshold_sigma` | 2.5 | Umbral de clasificación de saltos JD |
| `vol_cap_hjm` | 55% | Cap de volatilidad en modelo HJM |
| Reducción base GBM/CIR | × 0.90 | Reducción conservadora pre-pesos |
| `lambda_ewma` | 0.94 | Decaimiento de ponderación temporal |
| `peso_minimo` | 0.6 | Piso del rango de pesos |
| `peso_maximo` | 2.0 | Techo del rango de pesos |
| Semilla torneo | 42 | Reproducibilidad comparación |

### Ecuaciones de referencia rápida

```
GBM:
  ln(S_T/S_0) = (μ − σ²/2)·T  +  σ·√T·Z          Z ~ N(0,1)

JD (Merton):
  ln(S_T/S_0) = (μ_d − σ_d²/2 − λ·k̄)·T  +  σ_d·W_T  +  Σ Jᵢ
  N(t) ~ Poisson(λ),   Jᵢ ~ N(μⱼ, σⱼ²)
  k̄ = exp(μⱼ + σⱼ²/2) − 1

ARMA(1,1):
  r_t = c + φ·r_{t-1} + θ·ε_{t-1} + ε_t          ε_t ~ N(0, σ²_ε)

ARMA-GARCH(1,1):
  r_t = c + φ·r_{t-1} + ε_t
  h_t = ω + α·ε²_{t-1} + β·h_{t-1}               α + β < 1
  ε_t = √h_t · z_t ,   z_t ~ N(0,1)

EWMA (ponderación temporal):
  w(t) = λ^t                                       λ = 0.94 (RiskMetrics)
  choque_ef(factor) = Σ_t [w(t) · |choque(t)|] / Σ_t w(t)

Calibración dinámica (Min-Max):
  peso = p_min + (ch_ef − ch_min) / (ch_max − ch_min) × (p_max − p_min)

Calibración dinámica (Percentil):
  peso = p_min + rank(ch_ef) / N × (p_max − p_min)
```

---

*Fin del guión — Duración estimada: 40-50 minutos con preguntas.*
