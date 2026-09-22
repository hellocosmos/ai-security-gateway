# Espacio de operación (0.44)

La consola Docker incluye configuración, cambios pendientes, recuperación, diagnóstico y vista previa en Connections / System y Settings. Los cuatro perfiles de modelos generan rutas nativas. HTTP/MCP comienza bloqueado: revise acciones, recursos y campos de redacción. Las asignaciones avanzadas se editan como JSON.

Guardar no cambia el tráfico activo. Los secretos nuevos se guardan en archivos 0600 del volumen de estado y no se vuelven a mostrar. Vacío conserva la credencial existente. El origen de consola, autenticación del gateway y confianza del broker siguen en el archivo de despliegue.

```bash
docker compose stop app envoy
docker compose run --rm app activate-config
docker compose up -d app envoy
```

Detenga ambos servicios durante mantenimiento. La activación rechaza una aplicación activa, pero no comprueba un Envoy externo. Cambiar rutas reinicia sus políticas. Se conservan cuentas, claves y auditoría. Puede preparar la restauración de diez revisiones y su política cuando exista. Los archivos secretos se conservan para recuperar; los externos deben seguir montados. La conexión guardada prevalece sobre el archivo, salvo la confianza de identidad.

El diagnóstico muestra listeners y fase, estado, contador y fecha de solicitudes observadas. No evita el aislamiento ni demuestra autenticación de destino; los contadores se reinician con la aplicación. Correlacione con eventos. La vista previa usa JSON sintético de hasta 8 KiB y solo política local: no llama al destino, autoriza agentes, cambia políticas ni crea aprobaciones. Devuelve decisión, motivo y tipos de entidades.

Primera prueba: instalar con contraseña única → configurar credenciales separadas → solicitudes permitidas, PII sintética y bloqueo → revisar eventos → reiniciar y verificar persistencia → restaurar. Un MCP y cuenta reales de cliente requieren validación aparte.

[Docker](self-hosting.md) · [Workflow](agent-workflow.md)

## 0.44 · Buffered SSE

[Latencia de Buffered SSE y adecuación al despliegue](latency.md)

El gateway recopila e inspecciona toda la respuesta admitida antes de entregar contenido. La latencia del primer contenido incluye recopilación e inspección. Conviene a tareas que pueden esperar un resultado completo; el chat interactivo exige un presupuesto explícito de latencia.
