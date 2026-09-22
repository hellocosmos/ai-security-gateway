# TrapDefense — Open-source AI Security Gateway

[0.45: Cronologías por solicitud y admisión](docs/es/latency.md) · [Decisión sobre streaming interactivo](docs/es/interactive-streaming.md)

[0.44: Latencia de Buffered SSE y adecuación al despliegue](docs/es/latency.md)

## Least Privilege, Least Agency

**El mínimo privilegio limita el acceso. La mínima autonomía acota la acción autónoma.**

Nuestro principio de diseño: otorgar al agente solo el acceso necesario y delimitar las acciones que puede realizar por sí mismo. TrapDefense complementa IAM y los permisos del servicio de destino mediante políticas de acciones y datos para llamadas compatibles enrutadas por el gateway. La identidad opcional del agente añade ámbitos individuales, delegación y aprobaciones.

[0.44: Espacio de operación (0.44)](docs/es/operator-workspace.md)


[0.42: Verificación modelo → MCP → modelo](docs/es/agent-workflow.md)

**0.44:** [Conexiones de proveedores de modelos](docs/es/providers.md) — OpenAI · Anthropic · Gemini · OpenRouter.

**Conecte API HTTP y servidores MCP remotos compatibles a través de un límite de seguridad explícito. Añada identidad para controlar cada agente.**

[Conectar, identificar, controlar, verificar →](docs/es/aisg.md)

[English](README.md) · [한국어](README.ko.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Français](README.fr.md)

> **Open Source Preview 0.45:** todo el runtime y la consola operativa se publican con licencia MIT. El Agent Access Broker integrado está implementado y validado con datos sintéticos, pero permanece **Experimental** hasta validar IdP reales, políticas de clientes, HA y capacidad.

TrapDefense es un AI Firewall autoalojado para tráfico HTTP y MCP compatible. Inspecciona solicitudes y respuestas, aplica políticas de action, PII y secrets, conserva evidencia saneada y puede autorizar una acción según agent, delegation, task, resource y una aprobación humana de un solo uso.

```text
AI agent → gateway autenticado → enlace de solicitud confiable → Envoy + inspector
         → Access Broker integrado opcional → Tool / MCP / HTTP API
```

## La consola en acción

Pantallas reales de 0.41 con datos sintéticos. El panel incluye una prueba con un retraso deliberado de siete segundos del proveedor; no es una referencia de rendimiento. La gestión de agentes corresponde a otra demostración local.

![Panel de ejecución](docs/assets/console-dashboard-041.png)

<table>
<tr>
<td width="50%"><img src="docs/assets/console-agents-041.png" alt="Permisos de agentes · Experimental"><br><strong>Permisos de agentes · Experimental</strong></td>
<td width="50%"><img src="docs/assets/console-provider-041.png" alt="Configuración del proveedor"><br><strong>Configuración del proveedor</strong></td>
</tr>
</table>

## Un único producto de código abierto

No existen ediciones de código Community y Enterprise. Este repositorio público contiene Runtime Gateway, inspección HTTP/MCP, protección PII/secret, validación OAuth JWT externa, Agent Registry, delegation, Access Broker, human approval, audit, consola operativa y despliegue Docker. No se requiere un paquete runtime privado.

Los futuros servicios de pago pueden cubrir cloud administrado, operación de fleets, HA multinodo, auditoría externa inmutable, integraciones y soporte. Las funciones actuales de enforcement permanecen abiertas. [Modelo de código abierto](docs/es/editions.md)

## Docker autoalojado

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway/deploy/selfhost
docker compose build app
docker compose run --rm app init
docker compose --profile smoke up -d
```

Abra `http://localhost:18080` e inicie sesión como `admin` con la contraseña elegida durante la inicialización. El cliente debe permitir configurar la URL HTTP/MCP y `X-TD-Client-Key` o un Bearer JWT. La credencial del servicio destino es independiente y cada instalación usa un origen fijo con mapeos explícitos. [Contrato de autoalojamiento](docs/es/self-hosting.md)

## Access Broker integrado (Experimental)

El modo solo gateway valida la fuente de reenvío y la política local; no afirma la identidad del agent. El modo Broker exige un JWT emitido por un IdP externo y un mapeo explícito de claims. TrapDefense propaga únicamente los claims verificados y configurados a `tenant_id`, `user_id`, `agent_id`, `delegation_id` y `task_id`. La ausencia de identidad obligatoria bloquea antes del reenvío.

El Broker verifica tenant, registry, ámbitos de tool/resource, delegation, user, task, action, request digest y approval. Las acciones de alto riesgo producen `approval_required`; una aprobación solo puede consumirse una vez para la solicitud exacta. TrapDefense no sustituye los permisos del servicio destino ni emite tokens OAuth descendentes.

## Demo local y validación

```bash
./scripts/install-console.sh
./scripts/run-console.sh
```

Abra [http://127.0.0.1:5176](http://127.0.0.1:5176), use `admin` / `1234` y cambie la contraseña. La demo registra agents y delegations sintéticos en el Broker real basado en archivos y muestra “requiere aprobación → aprobar → una ejecución → replay bloqueado”.

```bash
pip install -e ".[dev]"
pytest -q
npm run check --prefix console
npm run build --prefix console
```

Estas pruebas son evidencia de código, protocolo y escenarios sintéticos. No certifican un tenant real de Entra/Okta/Keycloak, Conditional Access, autenticación MCP del cliente, routing obligatorio, HA ni capacidad de producción.

[Consola](docs/es/console.md) · [Arquitectura](docs/es/architecture.md) · [Seguridad](docs/es/security.md) · [Migración](docs/es/migration.md) · [Documento base en inglés](README.md)

## Licencia

MIT. Todo el Runtime Gateway y Access Broker de este repositorio es código abierto.
