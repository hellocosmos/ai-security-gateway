# Separación del plano de control y el plano de datos (0.47)

[English](../en/plane-separation.md) · [한국어](../ko/plane-separation.md) · [简体中文](../zh-CN/plane-separation.md) · [日本語](../ja/plane-separation.md) · [Español](../es/plane-separation.md) · [Français](../fr/plane-separation.md)

**Garantía:** si la consola (plano de control) se detiene o falla, o si su base de datos está bloqueada o dañada, el plano de datos sigue aplicando su **última instantánea de política verificada**. Si la inspección o el almacenamiento de evidencias no están disponibles, el plano de datos sigue fallando en modo cerrado. Ninguna solicitud llega al destino sin un veredicto de inspección.

Se trata de una separación de dominios de fallo en un único host Docker. No es HA multinodo.

## Servicios

| Servicio Compose | Función | Escucha | Contiene |
|---|---|---|---|
| `app` | Plano de control: consola, publicación de políticas, CLI (`init`, `client-key`, `activate-config`) | 18080 (publicado) | `console.sqlite`, clave Ed25519 de **firma** de políticas (volumen `control-keys`) |
| `dataplane` | Gateway, inspector (o grupo de inspectores), spool de evidencias | 18084 (publicado), 18081 y 18085 (internos) | Solo la clave de **verificación** de políticas (`policy-trust`, solo lectura), nonces, estado del broker |
| `envoy` | Proxy privado de inspección | 18082 (interno) | Configuración generada |

El plano de datos nunca abre `console.sqlite` ni lee `deployment.yaml`. La política y la configuración de conexión llegan únicamente como una instantánea firmada. Envoy arranca cuando el plano de datos está listo, no cuando lo está la consola.

## Instantáneas de política

- Cada política aplicada, y cada arranque, publica una instantánea inmutable en `/state/policy/` (`history/` y un `current.json` que se reemplaza de forma atómica). Si el contenido no cambia, no se vuelve a publicar.
- El plano de datos busca una instantánea nueva cada 0,25 segundos y verifica la firma, el formato, el esquema y el orden de revisión. Las solicitudes nuevas usan la política nueva; las que están en curso conservan la política con la que empezaron.
- **Aplicar responde cuando la política ya está en vigor.** Al aplicar una política, la consola espera hasta 5 segundos a que el plano de datos, y cada inspector del grupo, informe de la nueva revisión. Si no llega la confirmación, la política se guarda y se audita `policy.dataplane_pending`.
- Una instantánea rechazada nunca sustituye a la política en ejecución. El rechazo aparece en el estado del plano de datos, en Conexiones, y se audita como `dataplane.snapshot_rejected`.

| Motivo de rechazo | Significado |
|---|---|
| `policy_snapshot_signature_invalid` | El contenido cambió después de firmarse, o lo firmó otra clave |
| `policy_snapshot_malformed` / `policy_snapshot_invalid` | Archivo incompleto, ilegible o que no cumple el esquema |
| `policy_snapshot_revision_regressed` | Más antigua que la revisión en ejecución |
| `connection_changed_restart_required` | Cambiaron las rutas, el destino o la autenticación; reinicie el plano de datos |
| `policy_snapshot_missing` / `policy_trust_key_unavailable` | No hay nada verificable; al arrancar, el plano de datos permanece cerrado |

## Evidencias

Los registros de decisión se añaden a un spool por proceso en `/state/dataplane/events/`, con `fsync` para cada registro. La consola los importa a su base de datos. Confirma los eventos y la posición de lectura en una sola transacción, de modo que un reinicio de la consola no pierde ni duplica registros. Los registros generados mientras la consola estaba detenida aparecen cuando vuelve. Las API de eventos y de resumen importan los registros pendientes antes de responder.

Si no se puede escribir un registro en modo **inline**, esa solicitud falla en modo cerrado. Las solicitudes nuevas se rechazan con HTTP 503 `dataplane_unavailable` hasta que el almacenamiento vuelva a ser escribible. El modo mirror continúa e informa del fallo de almacenamiento. El motivo exacto aparece solo en el estado para operadores, nunca en las respuestas al cliente.

## Comportamiento ante fallos (verificado)

| Fallo | Comportamiento | Evidencia |
|---|---|---|
| Proceso de la consola terminado a la fuerza | Las decisiones de permitir y bloquear continúan; las evidencias se importan tras el reinicio | `tests/runtime/test_plane_faults_runtime.py` F1 |
| `console.sqlite` bloqueada en exclusiva | Sin retraso adicional en la inspección | F2 (Docker) y `tests/test_plane_isolation.py` |
| `console.sqlite` dañada o eliminada | El plano de datos no se ve afectado | `tests/test_plane_isolation.py` |
| Instantánea manipulada, incompleta, de otra clave o más antigua | Se conserva la última política válida; el rechazo se audita | F4 (Docker) y pruebas unitarias |
| Sin instantánea al arrancar el plano de datos | No se atiende ninguna solicitud | F5 |
| Worker del inspector terminado a la fuerza | Esa solicitud falla; el worker se sustituye | Prueba de grupo en `test_selfhost_runtime.py` |
| Envoy detenido | HTTP 503, sin acceso directo de respaldo | F10 |
| Falla la escritura de evidencias (inline) | La solicitud falla en modo cerrado; la admisión se cierra hasta que el almacenamiento se recupere | Pruebas unitarias |

Ejecute la batería de inyección de fallos en Docker con `TD_FAULT_E2E=1 python -m pytest tests/runtime/test_plane_faults_runtime.py -q`.

## Operación

```bash
docker compose ps
docker compose logs --tail=100 app dataplane envoy
# Disponibilidad y estado del plano de datos (puerto interno, no publicado):
docker compose exec -T dataplane python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:18085/_trapdefense/status').read().decode())"
```

Para activar ajustes de conexión preparados hay que detener los tres servicios. `activate-config` se niega a ejecutarse mientras la consola, el plano de datos o Envoy estén en marcha.

```bash
docker compose stop app dataplane envoy
docker compose run --rm app activate-config
docker compose up -d app dataplane envoy
```

Monte las credenciales fijas de destino (`static_bearer` y `static_api_key`) en **ambos** servicios: `dataplane` (las usa) y `app` (la activación las valida). Reinicie `dataplane` después de rotarlas.

Copia de seguridad: `state` y `generated` son imprescindibles. Si se pierde `control-keys` o `policy-trust`, la consola crea un par de claves nuevo en su siguiente arranque y vuelve a publicar la instantánea.

## Actualización desde 0.46

1. Haga una copia de seguridad como se describe en [autoalojamiento](self-hosting.md) y detenga la pila.
2. Actualice el código fuente y ejecute `docker compose build app`.
3. Traslade los overrides privados de Compose: los cambios del puerto publicado del gateway y el montaje de secretos de destino van en `dataplane` (los montajes de secretos, también en `app`).
4. Ejecute `docker compose up -d`. La consola publica la primera instantánea firmada a partir de la política guardada; el plano de datos la espera y después pasa a estar listo.

El comando predeterminado de la imagen, `serve`, ejecuta ambos planos como procesos supervisados independientes dentro de un contenedor. Si la consola termina, solo se reinicia la consola; si termina el plano de datos, el contenedor se detiene. Use los servicios Compose separados para obtener el aislamiento descrito arriba.

## Rendimiento

p95 del primer contenido del gateway, en milisegundos, con el mismo benchmark sintético y el mismo host que en [latencia](latency.md) (2026-10-01, Docker ARM64, 14 CPU). Las diferencias están dentro de la variación de una sola ejecución. Los límites de ráfaga, PII, tamaño, tiempo de espera y credenciales no cambian. El proceso separado de la consola añade unos 110 MiB de memoria (pico muestreado: plano de datos 149,5 MiB y 85,6 % de CPU, consola 109,4 MiB). [JSON](../evidence/latency-047-synthetic.json)

| Escenario · concurrencia | 0.46 | 0.47 |
|---|---:|---:|
| short · 1 / 8 / 32 | 232 / 420 / 1253 | 224 / 430 / 1232 |
| long · 1 / 8 / 32 | 822 / 1164 / 3014 | 810 / 1183 / 3112 |

## Límites

- Un solo host. Las aprobaciones, el registro de agentes y la emisión de credenciales requieren la consola; las aprobaciones y credenciales ya emitidas siguen funcionando mientras está detenida.
- La clave de firma protege el canal de instantáneas solo si el acceso de escritura a `policy-trust` y `control-keys` está restringido. Quien pueda escribir en ambos volúmenes puede firmar políticas.
- El orden de revisión se aplica mientras el proceso del plano de datos está en ejecución. Tras un reinicio, el plano de datos acepta la instantánea firmada actual.
- El estado del broker y las credenciales locales de agentes siguen siendo archivos compartidos en el volumen `state`.
