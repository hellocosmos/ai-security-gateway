# Un único producto de código abierto

> **AISG:** [Conectar, identificar, controlar, verificar](aisg.md). El gateway autentica con una clave de despliegue o JWT verificado. agent_key identifica agentes registrados sin IAM externo. JWT identity_mode: agent usa los atributos verificados de tenant y agente; delegated también exige usuario, tarea y delegación. Los agentes existentes requieren delegación por defecto.

[English](../en/editions.md) · [한국어](../ko/editions.md) · [简体中文](../zh-CN/editions.md) · [日本語](../ja/editions.md) · [Español](../es/editions.md) · [Français](../fr/editions.md)

TrapDefense 0.44 usa una sola base de código con licencia MIT. Runtime Gateway y Agent Access Broker se publican juntos en este repositorio; no se necesitan una distribución Python privada, provider entry point, license key ni edition switch.

## Estado de entrega

| Límite | Estado | Evidencia y límite |
|---|---|---|
| Runtime Gateway y consola | **Open Source Preview** | Código público, CI, ruta Envoy sintética, políticas HTTP/MCP, controles PII/secret y UI local. El routing y la capacidad de producción requieren validación específica. |
| Agent Access Broker integrado | **Experimental** | Registry, delegation, autorización estricta, aislamiento tenant, transacciones de archivo y aprobación única vinculada a la solicitud. Faltan validaciones con IdP/política reales y multi-node. |
| Docker autoalojado | **Preview** | Adapter, Envoy, inspector, console, autenticación gateway y credenciales destino separadas compiladas desde fuente. Un origen fijo por instalación. |
| Managed cloud, fleet, HA multinodo, auditoría externa inmutable | **Planned** | No se entrega ni se presenta como disponible. |

El modo gateway-only aplica inspección local y verifica la fuente confiable. El modo broker-enabled añade identidad JWT verificada, agent registry, delegation, autorización resource/action y approval. Ambos usan el mismo paquete abierto.

Los futuros servicios de pago pueden operar el mismo runtime como managed service y añadir fleet lifecycle, HA, auditoría externa, conectores, onboarding de políticas, SLA y soporte. Es un límite de servicio y operación, no una puerta de funciones del código.

El file store funciona para procesos POSIX del mismo host con reemplazo atómico y locks; no es una base distribuida ni sirve para HA NFS/SMB. Las pruebas sintéticas no certifican IdP reales, Conditional Access, autenticación MCP de clientes, routing TLS ni capacidad.

[Docker 0.44](self-hosting.md) · [Arquitectura](architecture.md) · [Seguridad](security.md) · [Compatibilidad](gateway-compatibility.md)
