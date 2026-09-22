# Autoalojamiento con Docker — 0.46 Open Source Preview

> **0.44:** [Espacio de operación (0.44)](operator-workspace.md)


> [Conexiones de proveedores de modelos](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

> **AISG:** [Conectar, identificar, controlar, verificar](aisg.md). El gateway autentica con una clave de despliegue o JWT verificado. agent_key identifica agentes registrados sin IAM externo. JWT identity_mode: agent usa los atributos verificados de tenant y agente; delegated también exige usuario, tarea y delegación. Los agentes existentes requieren delegación por defecto.

[English](../en/self-hosting.md) · [한국어](../ko/self-hosting.md) · [简体中文](../zh-CN/self-hosting.md) · [日本語](../ja/self-hosting.md) · [Español](../es/self-hosting.md) · [Français](../fr/self-hosting.md)

**Controles de capacidad 0.46:** `gateway_admission_wait_ms` (predeterminado 0, máximo 2000) permite una espera breve y acotada antes de admitir una llamada autenticada; `inspector_replicas` (predeterminado 1; opcional 2 o 4) ejecuta procesos de inspección supervisados en este host. Aplique los cambios con el procedimiento existente de preparación, activación y reinicio. Consulte [latencia y comportamiento ante fallos](latency.md) antes de cambiar los valores. No es HA ni habilita reintentos automáticos.

## Elija un punto de partida para 0.44

- **API de modelos:** use un [perfil de proveedor](providers.md) para OpenAI, Anthropic, Gemini u OpenRouter. Cambie la base URL del SDK y guarde la clave del proveedor en el gateway.
- **Herramientas HTTP / MCP:** siga el inicio Docker y sustituya el destino sintético por un servicio explícitamente mapeado.
- **Evaluación completa:** ejecute el [ejemplo modelo → MCP → modelo con dos agentes](agent-workflow.md). No necesita clave de pago por defecto; distingue evidencia real de OpenAI, pruebas sintéticas y límites medidos.

La autenticación admite `client_key`, `agent_key` y `jwt` externo. El registro local de agentes y sus permisos son opcionales y no sustituyen la autenticación del destino. Cada despliegue tiene un origen fijo; modelos y herramientas ejecutadas por separado necesitan sus propias rutas. El SSE de modelos se almacena completo y se inspecciona antes de entregarse; no es streaming de tokens en tiempo real.

0.44 ofrece adaptador, Envoy, inspector, consola y autenticación separada para gateway y destino. La imagen se compila localmente desde el código fuente. TrapDefense Cloud sigue previsto.

El cliente debe poder cambiar la URL MCP/API y usar `X-TD-Client-Key` o un JWT Bearer OAuth. Cada despliegue tiene un destino fijo y rutas/herramientas explícitas. Consulte la [matriz de compatibilidad](gateway-compatibility.md).

| Tipo | Contrato |
|---|---|
| HTTP API | JSON, method/path exactos, máximo 1 MiB, respuesta acotada |
| MCP | POST JSON sin estado, métodos de control y herramientas explícitos |
| Autenticación del gateway | Clave o JWT RS256 de IdP externo con issuer/audience/scope y metadatos RFC 9728 |
| Autenticación del destino | none, paso Bearer heredado, Bearer/API Key fijo desde archivo |
| No compatible | Emisión OAuth, login intermediado, DCR, OBO, cookies/sesiones, SSE prolongado, WebSocket, stdio, SaaS interno cerrado |

La contraseña administra la consola. La clave o JWT autentica el acceso a TrapDefense. El JWT se valida para el audience del gateway y no se reenvía al destino, que usa una credencial separada. Una clave o JWT no registra automáticamente un agente. El Access Broker opcional gestiona registro y permisos por separado; el IdP externo emite tokens OAuth.

## Docker

Requiere Git y Docker Compose v2. init solicita una contraseña de administrador de al menos 12 caracteres, sin valor predeterminado. El ejemplo apunta a un destino sintético, no a un servicio real.

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway/deploy/selfhost
docker compose build app
docker compose run --rm app init
docker compose --profile smoke up -d
docker compose run --rm app client-key
```

Inicie sesión como admin en http://localhost:18080. Lea la clave con client-key y guárdela en los encabezados secretos del cliente. El gateway está en http://localhost:18084; el token del destino sintético es Bearer synthetic-target-token.

Para su servicio, cambie upstream, authority, rutas, herramientas y resource. `gateway_auth` admite `client_key`, `agent_key` o `jwt`; `target_auth` admite `none`, `passthrough_bearer`, `static_bearer` y `static_api_key`. JWT y passthrough no se combinan. Las credenciales fijas usan un archivo 0600 legible por UID 10001 y rechazan entradas en conflicto.

La UI gestiona políticas y contraseñas. Para cambiar mapeos: haga copia, ejecute policy-reset, render y recree el despliegue. Solo se reinician las políticas guardadas; cuentas, claves y eventos se conservan. Las nuevas solicitudes usan la política actualizada.

Los puertos se enlazan a loopback. El uso remoto necesita proxy TLS y console_origin exacto. Inspector y Envoy no publican puertos del host. Evite rutas de evasión con controles de red.

El estado persiste en volúmenes. Detenga y respalde ambos volúmenes y la configuración. down -v destruye datos. Para revertir, restaure la imagen anterior y su copia correspondiente. Un listener sano no prueba autenticación: verifique solicitudes permitidas/bloqueadas y efectos en el destino. Streaming prolongado, HA e IAM real requieren validación adicional.

[Compatibilidad y VS Code](gateway-compatibility.md) · [Detailed examples, backup and migration (English)](../en/self-hosting.md)

## Activar el Access Broker integrado

Lo siguiente describe el **modo JWT delegated**. Consulte la [guía AISG](aisg.md) para agent_key local y el modo agent autónomo.

Use `gateway_auth.mode: jwt` y declare en `identity_claims` los nombres de claims para tenant, user, agent, delegation y task. Configure después `access_broker.enabled: true` y un `access_broker.tenant_id`. Registre previamente el agent y la delegation del mismo tenant en la consola. Un claim obligatorio ausente o un tenant distinto se bloquea antes del reenvío. Consulte el YAML exacto en la [referencia inglesa](../en/self-hosting.md). El file store local es para un solo host, no para HA multinodo.

## 0.44 · Buffered SSE

[Latencia de Buffered SSE y adecuación al despliegue](latency.md)

El gateway recopila e inspecciona toda la respuesta admitida antes de entregar contenido. La latencia del primer contenido incluye recopilación e inspección. Conviene a tareas que pueden esperar un resultado completo; el chat interactivo exige un presupuesto explícito de latencia.
