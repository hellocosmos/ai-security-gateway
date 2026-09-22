# Línea base de rendimiento local

[English](../en/benchmark.md) · [한국어](../ko/benchmark.md) · [简体中文](../zh-CN/benchmark.md) · [日本語](../ja/benchmark.md) · [Español](../es/benchmark.md) · [Français](../fr/benchmark.md)

Este comando mide una **línea base local sintética** reproducible a través del listener Envoy instalado, el inspector gRPC ExtProc y el destino HTTP sintético. Sirve para comparar revisiones en el mismo equipo; no certifica capacidad de producción, HA ni tráfico de clientes.

## Ejecución

Instale una vez con `./scripts/install-console.sh` y detenga la consola, porque el benchmark usa los mismos puertos loopback.

```bash
.venv/bin/trapdefense-benchmark --scenario read --iterations 30
```

Los escenarios son `read`, `pii`, `secret` y `response`. Las iteraciones están limitadas a 5–500 y el calentamiento a 0–50; por defecto se miden 30 solicitudes después de 3 calentamientos. Cada solicitud atraviesa el proxy y genera evidencia depurada, sin destino empresarial externo ni API de modelos.

## Interpretación del JSON

Use `p50_ms`, `p95_ms`, `mean_ms` y `sequential_requests_per_second` solo como referencia de regresión local. Los recuentos de decisiones y estados HTTP confirman que el resultado esperado no cambió durante la medición. El informe incluye SO, arquitectura, Python y CPU lógicas, pero excluye el nombre del host y el contenido inspeccionado.

Compare solo con carga, Docker, modo de energía, escenario, iteraciones y política equivalentes. Ejecute al menos tres veces y conserve la ejecución mediana. La capacidad paralela, reutilización de conexiones, cuerpos grandes, SSE sostenido, recuperación y múltiples nodos requieren pruebas distintas.

Consulte [consola](console.md), [arquitectura](architecture.md), [ediciones](editions.md) y [seguridad](security.md).

## Grupo de inspectores AI Firewall

[Grupo de inspectores AI Firewall](inspector-pool.md)

## 0.44 · Buffered SSE

[Latencia de Buffered SSE y adecuación al despliegue](latency.md)

El gateway recopila e inspecciona toda la respuesta admitida antes de entregar contenido. La latencia del primer contenido incluye recopilación e inspección. Conviene a tareas que pueden esperar un resultado completo; el chat interactivo exige un presupuesto explícito de latencia.
