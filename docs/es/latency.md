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
