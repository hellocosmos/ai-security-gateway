# Compatibilidad de clientes del gateway — 0.45

> [Conexiones de proveedores de modelos](providers.md) · OpenAI / Anthropic / Gemini / OpenRouter.

> **AISG:** [Conectar, identificar, controlar, verificar](aisg.md). El gateway autentica con una clave de despliegue o JWT verificado. agent_key identifica agentes registrados sin IAM externo. JWT identity_mode: agent usa los atributos verificados de tenant y agente; delegated también exige usuario, tarea y delegación. Los agentes existentes requieren delegación por defecto.

[English](../en/gateway-compatibility.md) · [한국어](../ko/gateway-compatibility.md) · [简体中文](../zh-CN/gateway-compatibility.md) · [日本語](../ja/gateway-compatibility.md) · [Español](../es/gateway-compatibility.md) · [Français](../fr/gateway-compatibility.md)

El cliente debe poder cambiar la URL HTTP/MCP remota a TrapDefense y enviar una clave de conexión o un JWT Bearer OAuth. La autenticación cliente→TrapDefense se mantiene separada de TrapDefense→destino.

| Ruta | Evidencia de 0.42 |
|---|---|
| JSON HTTP genérico | Integración sintética verificada con HTTPX |
| SDK oficial de Python MCP 1.30.0 | Inicialización, notificación y lista de herramientas MCP `2025-11-25` verificadas en integración sintética |
| OAuth con forma de Entra | `scp`, `tid`, `oid`, `azp`, discovery, DCR, PKCE y resource binding verificados sintéticamente; no es un tenant Entra real |
| OAuth con forma de Okta | `scp` como array y `cid` verificados en el flujo sintético completo; no es un servidor Okta real |
| Keycloak sintético / local real | Además del flujo sintético, un Keycloak 26.7.3 oficial fijado por digest emitió un token local real validado con su discovery y JWKS |
| MCP remoto de VS Code 1.135 | El producto instalado mostró `Running`, descubrió una herramienta y produjo los tres receipts MCP con una solicitud de inicialización `2025-11-25` |
| MCP con estado, SSE prolongado, WebSocket, stdio | No admitidos; session headers y upstream SSE fallan de forma cerrada |
| HA multinodo | No admitida; una instancia con SQLite, replay y audit state locales |

`gateway_auth` usa `client_key` o `jwt`. En modo JWT, TrapDefense es un OAuth Resource Server con metadata RFC 9728 y `WWW-Authenticate`. `scope`/`scp` puede ser una cadena separada por espacios o un array; `authorized_parties` opcional limita `azp`, `appid` o `cid`. En 0.42, los app roles de Entra en `roles` no se interpretan como scopes.

`target_auth` admite `none`, `passthrough_bearer`, `static_bearer` y `static_api_key`. El JWT del gateway no llega al destino. El IdP externo o un credential provider separado gestiona login, emisión, refresh y OBO.

Antes de aprobar una integración, verifique URL, ambas autenticaciones, inicialización/descubrimiento MCP, acciones permitidas y denegadas, efectos en destino, PII/secret, 401 del destino, fallo de inspección y ausencia de fallback directo. Consulte comandos, configuración y fuentes en la [guía inglesa](../en/gateway-compatibility.md).


La evidencia actual incluye OpenAI real con MCP sintético, fixtures de SDK oficiales, MCP/Keycloak locales reales e inicialización/descubrimiento de VS Code. El SSE de modelos se almacena completo; MCP con estado, IAM de clientes, HA entre hosts y capacidad productiva no están certificados. Consulte [validación y límites de 0.42](agent-workflow.md).
