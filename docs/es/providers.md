# Conexiones de proveedores de modelos (0.45)

[English](../en/providers.md) · [한국어](../ko/providers.md) · [简体中文](../zh-CN/providers.md) · [日本語](../ja/providers.md) · [Español](../es/providers.md) · [Français](../fr/providers.md)

Conserve el SDK y el formato nativo. Cambie base_url y api_key; use una clave del gateway o una credencial individual de agente opcional. La clave real del proveedor permanece en el gateway.

Un proveedor por despliegue, con modelos permitidos y rutas exactas. Para varios proveedores use proyectos Compose, puertos y volúmenes separados.

SSE se almacena completo y se inspecciona antes de entregar los eventos originales. No es streaming de tokens en tiempo real. Límite predeterminado: 120 segundos y 1 MiB. Respuestas incompletas o no soportadas se bloquean.

Se admite texto y llamadas a funciones ejecutadas por el cliente. Quedan fuera archivos, medios, herramientas del proveedor, WebSocket, razonamiento cifrado y firmas thought de Gemini. Proteja la ejecución real de herramientas mediante su ruta HTTP/MCP.

Para control por agente active agent_key y Broker; registre herramientas y acceso autónomo explícito en la consola y emita una credencial. Úsela en el mismo parámetro api_key.

Los perfiles están en deploy/selfhost/providers/. Sustituya YOUR_MODEL_ID y guarde la clave del proveedor de forma segura en /state/provider-key. La validación usa SDK oficiales de Python con servicios sintéticos, no certifica todas las funciones reales.

| Provider | Gateway base_url | API |
| --- | --- | --- |
| OpenAI | https://gateway.example.com/v1 | Chat Completions / Responses |
| Anthropic | https://gateway.example.com | Messages |
| Gemini native | https://gateway.example.com | v1beta generateContent / streamGenerateContent |
| Gemini OpenAI | https://gateway.example.com/v1beta/openai | Chat Completions |
| OpenRouter | https://gateway.example.com/api/v1 | Chat Completions |


[SDK examples / Docker commands](../en/providers.md) · [AISG](aisg.md)

## 0.44 · Buffered SSE

[Latencia de Buffered SSE y adecuación al despliegue](latency.md)

El gateway recopila e inspecciona toda la respuesta admitida antes de entregar contenido. La latencia del primer contenido incluye recopilación e inspección. Conviene a tareas que pueden esperar un resultado completo; el chat interactivo exige un presupuesto explícito de latencia.
