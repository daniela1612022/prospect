# Guión de Presentación
## Modelos de Simulación para Stress Testing Prospectivo
### Evaluación comparativa de alternativas al GBM y calibración dinámica de pesos

---

> **Cómo usar este guión:**  
> Cada sección corresponde a un slide de la presentación. El texto en *cursiva* son notas para el presentador (no se leen en voz alta). El texto normal es lo que se dice al público.

---

## SLIDE 1 — Portada

*[Abrir el archivo. Esperar a que la audiencia esté atenta.]*

**Lo que se dice:**

"Hoy vamos a hablar de un problema concreto que teníamos en el proceso de stress testing prospectivo: el modelo de simulación que usábamos no estaba siendo suficientemente conservador, y vamos a ver tres cosas: por qué, qué alternativas evaluamos, y cómo resolvimos el problema de forma sistemática y auditable.

El tema no es solo técnico. Tiene una consecuencia regulatoria y de gestión: cuando el stress arroja una pérdida menor que el VaR, las alertas y los límites calibrados contra ese stress quedan subestimados."

---

## SLIDE 2 — Agenda

*[Recorrer los ítems brevemente, 20 segundos máximo.]*

**Lo que se dice:**

"La presentación tiene nueve bloques. Empezamos entendiendo las limitaciones del modelo actual, el GBM. Después presento los cuatro modelos que probamos. Explico cómo los comparamos de forma objetiva —con lo que llamamos el Torneo de Modelos— y qué resultados obtuvimos. La segunda mitad se enfoca en la calibración dinámica de pesos: por qué la necesitamos, cómo funciona y cómo se ejecuta paso a paso."

---

## SLIDE 3 — Limitaciones del GBM

*[Este slide es el núcleo del argumento de venta. Tomar 3-4 minutos.]*

**Lo que se dice:**

"El modelo que usábamos es el Movimiento Browniano Geométrico. La ecuación aparece arriba. La idea central es que el precio de mañana es el precio de hoy multiplicado por un factor exponencial que tiene un componente de tendencia —el drift— y un componente aleatorio —la difusión— que asumimos que es Normal.

Ese supuesto de Normalidad es el primer problema. Los retornos financieros reales, especialmente en mercados emergentes como el colombiano, tienen **colas más pesadas** que una Normal. Dicho de otra forma: los eventos extremos ocurren con más frecuencia de lo que el GBM predice.

El segundo problema es que GBM tiene **volatilidad constante**. En la realidad, cuando hay una crisis —una pandemia, una guerra, una decisión del Banco de la República— la volatilidad se dispara y se mantiene alta durante semanas. Esto se llama *volatility clustering*, y el GBM es completamente ciego a ese fenómeno.

Tercero: GBM es un proceso **continuo**. No puede generar un salto brusco de, digamos, 200 pesos en el USDCOP en un solo día. Sin embargo, eso ocurre. El JD de Merton, que veremos en un momento, fue diseñado específicamente para esto.

El cuarto problema es el que generó la alarma práctica: con la reducción ad-hoc de sigma al 90%, el stress prospectivo arrojaba consistentemente una pérdida menor que el VaR histórico. En números concretos: el stress daba −88.5 billones de pesos versus un VaR de −113.4 billones. Una brecha del 22%. Eso no es aceptable."

---

## SLIDE 4 — Los Cuatro Modelos Candidatos (overview)

*[Vista de pájaro. No entrar en detalle todavía. 90 segundos.]*

**Lo que se dice:**

"Para resolver esto, evaluamos cuatro modelos. El GBM quedó como baseline de referencia. Los tres candidatos para reemplazarlo o complementarlo son:

**Jump-Diffusion de Merton**: el GBM de siempre, pero con un componente adicional de saltos discretos modelados como proceso de Poisson. Es el candidato principal para factores que tienen eventos extremos identificables.

**ARMA(1,1)**: un modelo de series de tiempo clásico que captura la autocorrelación de los retornos. Si el retorno de ayer fue negativo, hay una probabilidad algo mayor de que el de hoy también lo sea. GBM ignora eso completamente.

**ARMA-GARCH**: la extensión natural del ARMA, donde además la varianza no es constante sino que evoluciona en el tiempo según sus propios valores pasados y los residuos pasados. Este es el modelo que mejor captura el *volatility clustering*."

---

## SLIDE 5 — GBM vs Jump-Diffusion de Merton

*[Slide técnico. El presentador puede apoyarse en la columna izquierda para comparar.]*

**Lo que se dice:**

"Comparemos GBM y JD lado a lado para entender exactamente qué cambia.

En GBM, el logaritmo del retorno acumulado a horizonte T es simplemente drift más difusión. Lineal. Continuo. La volatilidad sigma es constante.

En JD, la ecuación tiene tres términos. El primero es similar al GBM pero con un **drift ajustado**: se le resta `lambda × k_barra`, donde lambda es la frecuencia de saltos y k_barra es la corrección de Merton de 1976 para que el precio sea un martingala bajo la medida de riesgo neutral. Esto es importante: sin esta corrección, los saltos introducen un drift espúreo.

El segundo término es la difusión gaussiana de los días normales. El tercero es la suma de saltos, donde cada salto J_i sigue una Normal con su propia media y varianza.

¿Cómo calibramos los saltos? **Automáticamente**: tomamos los últimos 250 días de retornos, calculamos la desviación estándar total, y clasificamos como 'salto' cualquier retorno cuyo valor absoluto supere 2.5 sigmas. La frecuencia de estos eventos históricos nos da lambda. La media y la desviación estándar de esos retornos extremos nos dan mu_j y sigma_j.

Si hay menos de tres saltos detectados, el modelo degrada automáticamente a GBM para ese factor específico. Esto garantiza robustez."

---

## SLIDE 6 — ARMA(1,1) y ARMA-GARCH

*[Slide más técnico. Si la audiencia es no técnica, pasar por encima de las ecuaciones y enfocarse en la intuición.]*

**Lo que se dice:**

"El modelo ARMA(1,1) dice que el retorno de hoy depende linealmente del retorno de ayer —el término AR— y del error de ayer —el término MA— más un ruido blanco. Este ruido tiene varianza constante.

La calibración se hace por máxima verosimilitud usando la librería `statsmodels`. Una vez calibrado, la simulación hacia adelante es directa: partimos del último retorno observado y del último error observado, y avanzamos 20 pasos, día a día.

El ARMA-GARCH agrega una ecuación para la varianza. La varianza de hoy `h_t` es un promedio ponderado del término constante omega, del cuadrado del error de ayer —que captura si hubo un shock reciente— y de la varianza de ayer —que le da persistencia al régimen de alta o baja volatilidad.

La restricción de estacionariedad exige que `alfa + beta < 1`. Cuando alfa y beta son altos y suman cerca de 1, el modelo predice que los shocks de volatilidad son muy persistentes, lo cual es lo que ocurre en mercados financieros reales.

La intuición práctica: si hoy hay una caída fuerte del mercado, ARMA-GARCH predice que mañana la distribución de retornos va a tener colas más pesadas que en condiciones normales. GBM no tiene esa capacidad."

---

## SLIDE 7 — Metodología del Torneo

*[Explicar el diseño del experimento. Enfatizar la fairness de la semilla compartida.]*

**Lo que se dice:**

"Para comparar los modelos de forma objetiva, diseñamos lo que llamamos el **Torneo de Modelos**. El diseño tiene cinco pasos.

Primero, construimos la distribución empírica de referencia: calculamos los retornos logarítmicos acumulados a 20 días —nuestro horizonte de stress— usando ventanas solapadas con paso de 5 días sobre el histórico. Esto nos da entre 40 y 45 puntos de referencia empírica.

Segundo, calibramos cada modelo sobre los mismos 250 días de historia.

Tercero, simulamos 1,000 trayectorias de 20 días con cada modelo. El punto clave: **todos los modelos usan la misma semilla aleatoria**. Esto es fundamental para que las diferencias en los resultados reflejen el modelo y no el azar del muestreo.

Cuarto, calculamos cinco métricas de comparación entre la distribución simulada y la empírica.

Quinto, calculamos el *composite rank*: el promedio de las posiciones de cada modelo en cada métrica. El modelo con menor composite rank es el ganador.

Evaluamos 10 factores reales: cinco de tasa de cambio, tres de renta variable local y dos de renta variable internacional."

---

## SLIDE 8 — Las 5 Métricas de Evaluación

*[Slide de referencia. No hace falta leer todas las fórmulas. Explicar la lógica.]*

**Lo que se dice:**

"Las cinco métricas cubren aspectos distintos de la distribución. En todas, menor es mejor.

La **distancia KS** —Kolmogorov-Smirnov— mide la máxima diferencia entre las distribuciones acumuladas simulada y empírica. Es un test global de forma.

Los **errores de percentil P05 y P95** son los más relevantes para riesgo: miden qué tan bien el modelo captura las colas. Si el modelo subestima el P05 empírico, está subestimando los peores escenarios.

El **error de volatilidad** mide si la dispersión total de los escenarios simulados coincide con la dispersión histórica a 20 días. Un error alto aquí significa que el modelo está siendo demasiado conservador o demasiado laxo en términos de magnitud de los movimientos.

El **error de curtosis** captura las colas pesadas. Un modelo que genere retornos demasiado normales tendrá una curtosis cercana a cero, mientras que la curtosis empírica de mercados emergentes suele estar entre 3 y 8.

Con estas cinco métricas se calcula el composite rank y se elige el ganador por factor."

---

## SLIDE 9 — Resultados: ¿Qué Modelo Gana?

*[Este slide resume la conclusión empírica más importante. Tomar tiempo.]*

**Lo que se dice:**

"Estos son los resultados típicos que hemos observado.

Para las **tasas de cambio de mercados emergentes** —USDCOP, USDCLP, USDBRL— el ganador es consistentemente el Jump-Diffusion. La razón es clara: estas divisas tienen saltos identificables —intervenciones de bancos centrales, shocks de commodities, episodios de aversión al riesgo— que Poisson captura mucho mejor que una Normal.

Para las divisas de mercados desarrollados —EURUSD, GBPUSD— el ganador es ARMA-GARCH. Aquí no hay saltos tan pronunciados, pero sí hay episodios de alta volatilidad que persisten durante semanas. GARCH lo modela directamente.

Para renta variable local —ECOPETROL, ICOLCAP— gana JD. La asimetría de los retornos y la correlación con el precio del petróleo generan colas izquierdas pronunciadas que JD captura bien.

Para renta variable internacional —SPY, XLF— gana ARMA-GARCH. Los mercados de renta variable de EE.UU. tienen volatility clustering muy pronunciado: los crashes son rápidos pero la recuperación también es rápida, y GARCH calibra esa persistencia mejor que un proceso de Poisson.

La conclusión: **GBM queda en tercero o cuarto lugar en prácticamente todos los factores evaluados**. Ya no es la herramienta adecuada como modelo principal."

---

## SLIDE 10 — ¿Por Qué la Calibración Dinámica de Pesos?

*[Conectar el problema técnico con la consecuencia práctica.]*

**Lo que se dice:**

"Incluso con JD o ARMA-GARCH, podemos seguir teniendo una brecha entre el stress y el VaR si la volatilidad calibrada no está correctamente escalada para cada factor.

El problema que detectamos en la versión 2.7 del modelo fue el siguiente: el stress de Posición Propia arrojaba −88.5 billones de pesos, mientras que el VaR histórico era de −113.4 billones. Una diferencia de casi 25 billones, el 22%.

La brecha tiene cuatro causas. Primera: la reducción uniforme del 10% en sigma aplica igual a USDCOP —que tiene alta volatilidad— que a GBPUSD —que tiene baja volatilidad—. No diferencia.

Segunda: en crisis, las correlaciones entre activos aumentan. Si el modelo asume correlaciones estables, subestimará el riesgo del portafolio.

Tercera: hay factores sub-representados. BAAA2, BAAA3, COUSD y CECUVR tienen pesos bajos por defecto, pero el VaR muestra que son significativos.

Cuarta: el analista ajustaba los pesos manualmente cada mes, sin un criterio sistemático. Eso es propenso a errores y no es auditable.

La calibración dinámica resuelve exactamente esto: deriva los pesos directamente del Excel de VaR Zeros."

---

## SLIDE 11 — Sistema de Pesos: Arquitectura

*[Slide técnico de arquitectura. Explicar la jerarquía.]*

**Lo que se dice:**

"El sistema de pesos funciona como un multiplicador de volatilidad. En GBM, sigma es `std × 0.90 × peso_factor`. En CIR es similar. En HJM se aplica directamente a la volatilidad por nodo. En JD se aplica a la componente de difusión.

El `peso_factor` se determina siguiendo una jerarquía de tres niveles.

El nivel más alto de prioridad es el **override individual**: si especificamos un peso para 'USDCOP' directamente en el JSON, ese valor siempre gana. Es el nivel de mayor granularidad.

El segundo nivel es el **peso de categoría**: si USDCOP pertenece a la categoría 'Divisas_Mayor_Impacto' con peso 1.4, todos los factores de esa categoría usan ese peso, a menos que tengan un override individual.

El tercer nivel es el **peso global por defecto**, que aplica cuando un factor no está en ninguna categoría reconocida.

Esta jerarquía permite hacer ajustes quirúrgicos —por ejemplo, aumentar solo BAAA2— sin tocar el resto de los factores, o hacer ajustes masivos por categoría cuando toda una clase de activo está sub-calibrada."

---

## SLIDE 12 — Métodos de Calibración: Min-Max vs Percentil

*[Slide comparativo. Usar los dos ejemplos para ilustrar la diferencia práctica.]*

**Lo que se dice:**

"Cuando corremos la calibración dinámica, el sistema extrae el choque máximo histórico de cada factor desde el Excel de VaR Zeros, y convierte ese choque en un peso de volatilidad. Para esa conversión tenemos dos métodos.

El **método Min-Max** hace una escala lineal. El factor con el choque máximo dentro de su grupo recibe el peso máximo configurado —digamos 2.0—. El factor con el choque mínimo recibe el peso mínimo —digamos 0.6—. Los demás se interpolan linealmente.

La ventaja es que es intuitiva y reproducible. La limitación es que si hay un factor con un choque mucho más grande que los demás, todos los otros quedan comprimidos hacia el peso mínimo.

El **método Percentil** no usa la magnitud absoluta del choque, sino su posición ordinal dentro del grupo. Si hay 10 factores de tasa de cambio, el quinto más alto recibe el percentil 0.5, que se mapea al punto medio entre el peso mínimo y el máximo.

La ventaja es que es robusto a outliers: ningún factor puede 'monopolizar' el peso máximo. La limitación es que ignora la magnitud: si USDCOP tiene un choque de 500 puntos y USDBRL de 490, ambos pueden quedar con pesos casi idénticos aunque el primero sea 2% más grande.

**Recomendación práctica**: usar Min-Max como método por defecto y Percentil cuando hay un factor claramente outlier que distorsiona la escala."

---

## SLIDE 13 — Proceso Paso a Paso

*[Slide operativo. Leer los pasos como una checklist. Aquí la audiencia operativa toma nota.]*

**Lo que se dice:**

"El proceso completo de calibración dinámica tiene seis pasos.

**Paso 1**: Obtener el Excel de VaR Zeros del día de corte. El archivo se llama `Resultados_<fecha>_Zeros.xlsx` y debe tener la hoja `Factores_Zeros`.

**Paso 2**: Ejecutar la función `calibrar_pesos_desde_var` del módulo `CalibracionDinamica`. Esta función lee la hoja, identifica el choque máximo por factor, y lo clasifica por tipo de activo —Tasa Cambio, Curva, Acciones, Indicador—.

**Paso 3**: Normalización. Dentro de cada tipo de activo, aplica el método elegido —Min-Max o Percentil— para convertir el choque en un peso entre el mínimo y el máximo configurados.

**Paso 4**: Mapeo de nombres. El Excel usa nombres como `USD/COP` o `IBR 30d`, pero el JSON interno usa `USDCOP` o `C_IBR`. El módulo tiene una tabla de correspondencia para más de 45 factores incluyendo nodos de curva.

**Paso 5**: Si `guardar=True`, el JSON `pesos_factores_stress.json` se actualiza automáticamente. El sistema imprime un diagnóstico en consola: factor, choque, peso asignado.

**Paso 6**: Verificación. Después de correr la simulación, abrir `Simulation_statistics.xlsx` y revisar la pestaña `Pesos_Aplicados` para confirmar que los pesos se aplicaron correctamente y que el stress resultante se acerca al VaR objetivo."

---

## SLIDE 14 — Comparativa de Enfoques

*[Slide de síntesis. Conectar los tres enfoques con situaciones prácticas.]*

**Lo que se dice:**

"Para cerrar el tema de los pesos, comparemos los tres enfoques.

**Sin pesos**, el GBM usa `sigma × 0.90` uniforme. El stress típicamente llega al 78% del VaR. Esto solo sirve como baseline de referencia, no como cifra de gestión.

**Con pesos manuales** —como en la versión 2.7— el analista subió manualmente los pesos de BAAA2, BAAA3, COUSD y CECUVR a 1.5. Eso mejoró el stress al 88% del VaR. Es mejor, pero sigue dependiendo del criterio del analista y no tiene trazabilidad directa con el VaR real.

**Con calibración dinámica**, los pesos se derivan del Excel de VaR Zeros con un algoritmo reproducible. El stress llega al 95-100% del VaR objetivo dependiendo del factor y la fecha. Además, el proceso es completamente auditable: para cada peso hay un choque de VaR que lo justifica.

Mi recomendación es usar la calibración dinámica como proceso estándar al inicio de cada ejecución mensual, y reservar los ajustes manuales para casos específicos donde el analista tenga información adicional."

---

## SLIDE 15 — Implementación en Código

*[Slide para la audiencia técnica. Si el auditorio no es técnico, se puede omitir o pasar rápido.]*

**Lo que se dice:**

"La implementación completa son básicamente tres bloques de código.

En el primer bloque llamamos a `calibrar_dinamicamente` con la ruta del Excel de VaR, el nivel de agregación —Grupo Bancolombia en nuestro caso— y el método. Con `guardar=True`, el JSON se actualiza automáticamente.

El segundo bloque es opcional: si hay factores que queremos ajustar puntualmente después de la calibración dinámica, podemos sobrescribir el override individual o ajustar una categoría completa.

El tercer bloque corre la simulación completa con JD. El sistema leerá automáticamente los pesos del JSON actualizado en el paso anterior.

El total del proceso toma menos de 10 minutos en una máquina estándar para 1,500 simulaciones con horizonte de 20 días."

---

## SLIDE 16 — Conclusiones y Recomendaciones

*[Cerrar fuerte. Conectar cada conclusión con su acción.]*

**Lo que se dice:**

"Cinco conclusiones para llevarse.

Primero: GBM ya no es el mejor modelo. En el torneo consistentemente queda en tercer o cuarto lugar. Sus supuestos de Normalidad y volatilidad constante son demasiado restrictivos para los mercados donde operamos.

Segundo: Jump-Diffusion de Merton es el modelo recomendado para FX emergente y renta variable local. La calibración es automática y la mejora en la captura de colas es significativa.

Tercero: ARMA-GARCH es superior para mercados desarrollados. El volatility clustering de SPY, EURUSD o GBPUSD se modela mejor con un proceso GARCH que con saltos de Poisson.

Cuarto, y quizás el más importante desde el punto de vista de gestión: la calibración dinámica de pesos elimina la brecha entre stress y VaR. Pasamos del 78% de cobertura a más del 95%, con un proceso completamente auditable.

Y quinto: el proceso mensual recomendado es este: correr VaR Zeros, calibrar pesos con Min-Max, hacer ajustes manuales si hay outliers, simular con JD, y verificar en la pestaña de pesos. Es un ciclo de cinco pasos que toma menos de media jornada."

---

## SLIDE 17 — Cierre

*[Abrir a preguntas. Tener los archivos listos para mostrar en vivo si hay preguntas técnicas.]*

**Lo que se dice:**

"Esto es todo por nuestra parte. Los archivos de referencia están disponibles en el repositorio: `torneo_modelos.py` para correr el torneo sobre cualquier factor, `RiskModels.py` con las implementaciones de GBM, JD, CIR y HJM, `SimulationProspectivo_JD.py` para la simulación completa con JD, y `ajustar_pesos_stress.py` para la gestión de pesos.

Quedamos abiertos a preguntas."

---

## PREGUNTAS FRECUENTES Y RESPUESTAS PREPARADAS

### P: ¿Por qué umbral de 2.5 sigmas para clasificar saltos en JD?

**R:** Es el valor estándar en la literatura de Jump-Diffusion calibrado con datos históricos de mercados emergentes. En términos prácticos, un retorno de 2.5 sigmas en el USDCOP equivale a un movimiento de aproximadamente 180-200 pesos en un día, que históricamente corresponde a eventos como intervenciones del Banco de la República o shocks de commodities. El umbral es configurable en el parámetro `jump_threshold_sigma` si se quiere ajustar por factor.

---

### P: ¿ARMA-GARCH no es demasiado complejo para producción?

**R:** La calibración es automática mediante el paquete `arch`. La convergencia está garantizada por la restricción de estacionariedad. El tiempo de calibración adicional frente a GBM es del orden de 2-5 segundos por factor. Hay cadenas de fallback: si ARMA-GARCH falla, el sistema cae a ARMA; si ARMA falla, cae a GBM. En producción nunca habrá un fallo silencioso.

---

### P: ¿La calibración dinámica no puede generar pesos muy extremos?

**R:** No. El JSON de configuración tiene parámetros `peso_minimo` y `peso_maximo` que actúan como límites duros. Por defecto están en 0.6 y 2.0. Ningún factor puede recibir un peso fuera de ese rango, independientemente de su choque de VaR. Esto protege contra outliers extremos en el Excel de VaR.

---

### P: ¿Cómo se trata el problema de correlaciones en crisis?

**R:** En la versión 2 (`SimulationProspectivo_v2.py`) se implementaron dos mejoras: correlaciones con decay exponencial —que dan más peso a las observaciones recientes— y un factor de amplificación de correlaciones hacia ±1 para el escenario de estrés. Por defecto el `stress_factor_correlation` es 0.3, que amplifica las correlaciones un 30% hacia sus valores extremos. Esto no está en la versión actual de producción pero está disponible.

---

### P: ¿Cómo validamos que el nuevo modelo es mejor que el anterior?

**R:** El torneo es exactamente esa validación. Para cualquier factor podemos correr `torneo_modelos.py` con el histórico real y obtener el composite rank de los cuatro modelos. Adicionalmente, el archivo `Razonabilidad_Estres_Prospectivo.py` permite comparar los resultados de stress contra el VaR para detectar brechas. La combinación de torneo + razonabilidad es el proceso de validación completo.

---

## DATOS TÉCNICOS CLAVE PARA RESPONDER PREGUNTAS

| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| `nSim` | 1,500 | Número de simulaciones Monte Carlo |
| `n_max_proyeccion` | 20 días | Horizonte de stress |
| `n_max_historia` | 250 días | Ventana de calibración histórica |
| `nCPs` | 3 | Componentes principales (curvas) |
| `jump_threshold_sigma` | 2.5 | Umbral de clasificación de saltos JD |
| `vol_cap_hjm` | 55% | Cap de volatilidad en modelo HJM |
| Reducción base GBM/CIR | ×0.90 | Reducción conservadora pre-pesos |
| `peso_minimo` | 0.6 | Piso del rango de pesos dinámicos |
| `peso_maximo` | 2.0 | Techo del rango de pesos dinámicos |
| Semilla torneo | 42 | Reproducibilidad comparación |

---

## ECUACIONES DE REFERENCIA RÁPIDA

```
GBM:         ln(S_T/S_0) = (μ − σ²/2)·T  +  σ·√T·Z
                           Z ~ N(0,1)

JD (Merton): ln(S_T/S_0) = (μ_d − σ_d²/2 − λ·k̄)·T  +  σ_d·W_T  +  ΣJᵢ
                           N(t) ~ Poisson(λ), Jᵢ ~ N(μⱼ, σⱼ²)
                           k̄ = exp(μⱼ + σⱼ²/2) − 1

ARMA(1,1):   r_t = c + φ·r_{t-1} + θ·ε_{t-1} + ε_t
                   ε_t ~ N(0, σ²_ε)

ARMA-GARCH:  r_t = c + φ·r_{t-1} + ε_t
             h_t = ω + α·ε²_{t-1} + β·h_{t-1}
             ε_t = √h_t · z_t ,   z_t ~ N(0,1)
             Restricción: α + β < 1

CIR:         dr_t = α(μ − r_t)·dt  +  σ·√r_t·dW_t

HJM:         x_t = x_0 + ½·σ²·t·(2T − t)  +  σ·√t·Z

Calibración dinámica (Min-Max):
             peso = p_min + (ch − ch_min)/(ch_max − ch_min) × (p_max − p_min)

Calibración dinámica (Percentil):
             peso = p_min + rank(ch)/N × (p_max − p_min)
```

---

*Fin del guión — Duración estimada de la presentación: 35-45 minutos con preguntas.*
