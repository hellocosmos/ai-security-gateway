# Arquitectura y límite de confianza

**Instalación:** siga la [guía Docker](self-hosting.md). Entra SSO y la demostración de la consola desde fuentes son una instalación separada; no se aplican automáticamente a Docker.

> **AISG:** [Conectar, identificar, controlar, verificar](aisg.md). El gateway autentica con una clave de despliegue o JWT verificado. agent_key identifica agentes registrados sin IAM externo. JWT identity_mode: agent usa los atributos verificados de tenant y agente; delegated también exige usuario, tarea y delegación. Los agentes existentes requieren delegación por defecto.

[English](../en/architecture.md) · [한국어](../ko/architecture.md) · [简体中文](../zh-CN/architecture.md) · [日本語](../ja/architecture.md) · [Español](../es/architecture.md) · [Français](../fr/architecture.md)

> **0.47:** la consola (plano de control) y el gateway/inspector (plano de datos) son procesos separados. La política llega al plano de datos solo como instantánea firmada con Ed25519; las evidencias vuelven por un spool de solo anexado. Consulte [separación de planos](plane-separation.md).

La consola admite SSO Microsoft Entra ID de un solo tenant con roles Administrador y Lector. La identidad del operador y la autorización del agente son límites distintos; el Access Broker integrado aplica la autorización. [Entra SSO](identity.md).

```text
AI agents → TrapDefense AI Firewall → Tools / MCP servers / APIs
            Action policy · Data protection · Audit
          ← Inspected responses ←
```

## Plano de datos y de control

La API autentica al operador local, guarda políticas y sirve la UI. Envoy reenvía HTTP/MCP admitido y llama al inspector mediante gRPC ExtProc para solicitudes y respuestas. Cada flujo conserva una instantánea de política. Un destino HTTP sintético sin acciones empresariales aporta recibos. Consulte la [instalación](console.md).

## Contrato de confianza

1. Fuerce las rutas fuera de TrapDefense para impedir el bypass del proxy.
2. Termine HTTPS del cliente en su ingress TLS y use el adaptador de firma incluido. El descifrado TLS externo es opcional para integraciones de red diseñadas aparte; no es un requisito para base_url/MCP URL.
3. El adaptador de confianza elimina `x-td-*` y `x-asr-*` del cliente y firma lo que observó. Preserve método, autoridad, ruta/consulta, cabeceras de aplicación y cuerpo completo. `inspection/identity.py` define la vinculación y exclusiones.
4. Guarde la clave HMAC solo en el salto de confianza y el inspector, nunca en agentes. Permita explícitamente el `source_id` del modo gateway-only. Aísle texto claro y ExtProc: los ejemplos no autentican una escucha gRPC pública.
5. Envoy usa búfer completo, límites de tamaño/tiempo y `failure_mode_allow: false`. Elimina la atestación antes de reenviar. La firma vincula el original; una aprobación persistente, si existe, vincula el resumen de la acción después de ocultar datos.
6. El modo gateway-only aplica reglas locales explícitas de ruta/herramienta/recurso/acción y verifica el origen. No establece identidad de usuario ni autoridad delegada del agente.
7. El modo Broker exige claims JWT verificados y evalúa registry, delegation, task, resource, action y approval de un solo uso; la identidad incompleta falla de forma cerrada.

No existe adaptador universal para cualquier equipo TLS. La integración debe evitar suplantación de metadatos y restringir el acceso directo al destino.

## Cobertura y límites

Las rutas exigen coincidencia exacta de autoridad, método, ruta y cabeceras. MCP cubre llamadas JSON-RPC asignadas y versiones configuradas, no certifica todas sus funciones. Transportes arbitrarios, túneles WebSocket, cuerpos cifrados opacos, CONNECT sin restricciones y descubrimiento automático quedan fuera. Solo se modifican campos/formatos permitidos; transformaciones inseguras se bloquean. Las firmas detectan patrones conocidos acotados, sin garantía frente a toda inyección. SSE almacena un flujo completo y limitado, no streaming ilimitado token a token.

El colector mirror independiente recibe copias y no afecta al original; con solo cabeceras la cobertura es incompleta. Mirror de la consola observa su ruta síncrona sin modificar cuerpo, pero el fallo de comunicación del inspector bloquea. Distinga ambos en despliegues e informes. JSONL y auditoría SQLite omiten contenido original y claves; son almacenamiento local modificable, no retención inmutable.

## Perfil de red

La consola usa loopback y una imagen Envoy amd64/arm64 fijada por digest. macOS usa Docker Desktop hacia el host; Linux, host networking. El inventario enumera interfaces del SO, no puertos físicos. Enrutamiento de dos NIC, puente transparente, salida física fijada, IdP/TLS reales, HA y rendimiento requieren trabajo separado. Las pruebas opcionales agentgateway son compatibilidad, no un servicio gestionado.
