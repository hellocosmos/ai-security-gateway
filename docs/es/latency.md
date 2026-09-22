# Latencia de Buffered SSE y adecuación al despliegue — 0.44

[en](../en/latency.md) · [ko](../ko/latency.md) · [zh-CN](../zh-CN/latency.md) · [ja](../ja/latency.md) · [es](../es/latency.md) · [fr](../fr/latency.md)

El gateway recopila e inspecciona toda la respuesta admitida antes de entregar contenido. La latencia del primer contenido incluye recopilación e inspección. Conviene a tareas que pueden esperar un resultado completo; el chat interactivo exige un presupuesto explícito de latencia.

## Reproducir

Requiere Docker, Python 3.11+ y las dependencias console del proyecto. Construye una pila temporal sin credenciales reales ni API de pago y elimina contenedores y volúmenes en finally. Repita al menos tres veces en un equipo sin otras cargas antes de decidir un despliegue.

```bash
python -m pip install -e ".[console,compat,llm-compat]"
python -m examples.latency.benchmark --output /tmp/latency.json
```

## Primer contenido p95 / finalización p95 (ms)

2026-09-22 · synthetic fixture · short: 8 × 65 bytes content; long: 32 × 515 bytes content · 20 ms/chunk.

| Scenario | Concurrency | Direct | Gateway |
|---|---:|---:|---:|
| short | 1 | 56 / 202 | 232 / 233 |
| short | 8 | 58 / 197 | 420 / 421 |
| short | 32 | 97 / 219 | 1253 / 1253 |
| long | 1 | 53 / 752 | 822 / 822 |
| long | 8 | 69 / 745 | 1164 / 1164 |
| long | 32 | 89 / 726 | 3014 / 3014 |

Una ejecución sintética en Docker ARM64, 14 CPU y 7.75 GiB: no son requisitos mínimos ni capacidad por número de usuarios. Cada celda contiene 12–64 muestras; p95 no es un SLA. La conexión directa usa TLS; el cliente local del gateway HTTP y su destino TLS. Sin credencial configurada, 0.44 no ejecutó un modelo real. La evidencia anterior conserva su fecha.

## Interpretación

La consola muestra las últimas 256 muestras por fase del proceso. El tiempo del gateway termina antes de la entrega al cliente. Envoy incluye inspección de solicitud, recopilación, inspección de respuesta y transporte. La inspección incluye espera en cola. Las distribuciones incluyen fallos, no están correlacionadas por solicitud, no pueden restarse y se reinician al arrancar. Sin muestras significa no medido, no cero.

## Límites

De 64 solicitudes concurrentes, 32 finalizaron y 32 recibieron HTTP 503; ninguna respuesta HTTP 200 SSE quedó incompleta. Se ocultó el correo PII dividido en fragmentos. Con el límite de prueba de 32 KiB, el exceso devolvió HTTP 500 y el timeout de 10 segundos devolvió 504, sin tokens de contenido. Las credenciales inválidas devolvieron 401. El estado no identifica por sí solo el componente; los valores predeterminados de producción difieren.

## Límites de la evidencia

[JSON](../evidence/latency-044-synthetic.json) · [Guía operativa](operator-workspace.md)


| Docker sampled resource | Peak CPU (100% = one core) | Peak memory (MiB) |
|---|---:|---:|
| App / Python inspector | 87.8% | 148.9 |
| Envoy | 3.91% | 37.38 |
| Synthetic fixture | 17.87% | 21.77 |

Los valores son picos muestreados de toda la ejecución, no reservas ni recomendaciones; pueden omitir picos breves. El origen sintético comparte el host Docker: no es una comparación de lenguajes. Más cola e inspección no demuestra que Python sea la causa ni que Go/Rust elimine el buffering. Evalúe tareas de fondo por p95 de finalización y errores; chat por p95 del primer contenido. Repita en el equipo destino con respuestas y políticas representativas, rechazo de ráfagas y recuperación. La generación puede continuar tras cancelar el cliente. Dimensione por concurrencia, tamaño, frecuencia y coste de política, no por empleados.

## 0.45 Cronologías por solicitud y admisión

La consola muestra las últimas 64 solicitudes completadas en el proceso actual. Cada fila solo conserva tiempos numéricos, estado HTTP e indicador de finalización. Un ID aleatorio firmado une internamente adaptador e inspector y no se muestra. No se guardan cuerpo, ruta, credencial ni identidad del agente. Los rechazos tempranos se ven en los resultados del gateway.

Se muestran por separado la espera de flujo, la cola de trabajadores y la ejecución. La espera del cuerpo va desde el fin de la inspección de metadatos hasta que llega el cuerpo almacenado; incluye generación, transporte y buffering de Envoy. Los intervalos se superponen o dejan huecos y no pueden sumarse ni atribuirse íntegramente al modelo. Se reinician con el proceso.

`gateway_max_inflight` acepta enteros 4–64; el valor predeterminado sigue siendo 32. Se aplica tras preparar el cambio y reiniciar en mantenimiento. El asistente conserva el valor. Las solicitudes excedentes reciben HTTP 503. Un valor menor sirve si se acepta más rechazo a cambio de menor latencia. En la prueba sintética, 48 no aumentó finalizaciones y produjo HTTP 500.

Una sola prueba sintética no determina un valor universal. Repita la tabla en el equipo destino con tamaños representativos, concurrencia, cuotas del proveedor y presupuesto para primer contenido y finalización.

[Decisión sobre streaming interactivo](interactive-streaming.md)

### Comparación sintética local (2026-09-22)

Se hicieron dos repeticiones por ajuste con un servicio SSE de 32 fragmentos retardados, límite de cuerpo de 32 KiB, 16 flujos de inspección y cuatro trabajadores. Cada repetición con concurrencia 32 envió 64 solicitudes; con concurrencia 64 envió 128. El rango p95 del primer contenido corresponde solo a respuestas HTTP 200 completas con concurrencia 32.

| Límite del gateway | Completadas con concurrencia 32 | p95 primer contenido | Completadas con concurrencia 64 | HTTP 500 con concurrencia 64 | Pico muestreado de CPU / memoria de la aplicación |
|---:|---:|---:|---:|---:|---:|
| 8 | 8/64 por repetición | 1.16–1.18 s | 8/128 por repetición | 0 | 62% / 116 MiB |
| 16 | 16/64 por repetición | 1.53–1.54 s | 16/128 por repetición | 0 | 110% / 127 MiB |
| **32 (predeterminado)** | **64/64 por repetición** | **3.02–3.10 s** | **32/128 por repetición** | **0** | **118% / 148 MiB** |
| 48 | 64/64 por repetición | 2.96–3.06 s | 32/128 por repetición | 13–16 | 124% / 161 MiB |

Con límites 8–32, todos los intentos distintos de 200 devolvieron 503. Todas las respuestas exitosas estuvieron completas y las cuatro solicitudes de recuperación por ajuste tuvieron éxito. El muestreo puede omitir picos breves. No se aisló la causa de los HTTP 500 con límite 48; no demuestra un cuello de botella de Python. El almacenamiento completo de la respuesta sigue siendo el principal compromiso para el primer contenido. [Datos brutos](../evidence/latency-045-synthetic.json) · Repetir: `.venv/bin/python -m examples.latency.sweep --output docs/evidence/latency-045-synthetic.json`.
