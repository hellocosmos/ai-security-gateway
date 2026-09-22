# TrapDefense — AI Security Gateway (0.45)

> [Conexiones de proveedores de modelos](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

[en](../en/aisg.md) · [ko](../ko/aisg.md) · [zh-CN](../zh-CN/aisg.md) · [ja](../ja/aisg.md) · [es](../es/aisg.md) · [fr](../fr/aisg.md)

Conecte API HTTP y servidores MCP remotos compatibles a través de un límite de seguridad explícito. Añada identidad para controlar cada agente.

## Conectar, identificar, controlar, verificar

Inicie el entorno sintético Docker, registre un agente en Access Broker, habilite el acceso autónomo a las herramientas elegidas y emita una credencial. Cambie la URL del cliente y envíe la credencial en Authorization. Pruebe una llamada permitida y otra bloqueada y revise las decisiones.

## Elegir el modelo de identidad

El gateway autentica con una clave de despliegue o JWT verificado. agent_key identifica agentes registrados sin IAM externo. JWT identity_mode: agent usa los atributos verificados de tenant y agente; delegated también exige usuario, tarea y delegación. Los agentes existentes requieren delegación por defecto.

## Ciclo de credenciales

Las credenciales caducan en 1 hora, 24 horas o hasta 30 días. Solo se almacenan hashes; la nueva credencial se muestra una vez. Rotar revoca inmediatamente la anterior. Revocar o deshabilitar al agente bloquea la autenticación posterior. Las credenciales del destino permanecen separadas.

## Compatibilidad y límites

Un destino fijo por instalación; HTTP JSON y MCP JSON POST sin estado con rutas explícitas. No se admiten SSE, sesiones con estado, stdio, WebSocket ni llamadas internas de SaaS. Cambiar el base_url del modelo no enruta herramientas ejecutadas por separado. Configure cada endpoint protegido y evite desvíos mediante controles de red.

## Aprobaciones

El acceso autónomo comprueba herramientas, recursos y acciones. Las acciones de alto riesgo exigen aprobación con caducidad vinculada a la solicitud. Tras la revisión, reintente la misma solicitud con la clave local y X-TD-Approval-ID; la aprobación se consume una sola vez. Mirror no crea ni consume aprobaciones.

## Evidencia

La verificación sintética local no certifica IdP de producción, rutas de clientes, HA ni capacidad. Access Broker sigue siendo experimental. No hay registro de nube gestionada disponible.

## Inicio rápido

```bash
cd deploy/selfhost
docker compose -f compose.yaml -f compose.agent.yaml build app
docker compose -f compose.yaml -f compose.agent.yaml run --rm app init
docker compose -f compose.yaml -f compose.agent.yaml --profile smoke up -d
```

Console: `http://localhost:18080` · Gateway: `http://localhost:18084`

```text
API base_url: http://localhost:18084
MCP URL: http://localhost:18084/mcp
Authorization: Bearer <agent-credential>
```


```bash
# Set TD_AGENT_CREDENTIAL locally to the credential displayed once in the console.
# Register notes.read and enable autonomous access first.
curl --fail-with-body http://localhost:18084/api/notes \
  -H "Authorization: Bearer ${TD_AGENT_CREDENTIAL}" \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'

# Expected: HTTP 403. The fixture policy blocks notes.delete.
curl --fail-with-body http://localhost:18084/mcp \
  -H "Authorization: Bearer ${TD_AGENT_CREDENTIAL}" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"notes.delete","arguments":{}}}'
```

[Self-hosting](self-hosting.md) · [Identity](identity.md) · [Compatibility](gateway-compatibility.md)
