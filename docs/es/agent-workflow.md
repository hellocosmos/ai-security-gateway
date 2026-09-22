# Verificación modelo → MCP → modelo (0.44)

[English](../en/agent-workflow.md) · [한국어](../ko/agent-workflow.md) · [简体中文](../zh-CN/agent-workflow.md) · [日本語](../ja/agent-workflow.md) · [Español](../es/agent-workflow.md) · [Français](../fr/agent-workflow.md)

Conecta el SDK oficial de OpenAI y el cliente MCP mediante dos gateways independientes. Cambia tanto base_url del modelo como la URL MCP. El mismo identificador de agente utiliza claves distintas en cada gateway.

Por defecto el modelo es un guion sintético, sin inferencia real ni llamadas de pago. Docker, Envoy y el inspector verifican lectura permitida para A, lectura denegada para B, eliminación bloqueada, redacción de PII, revocación de claves utilizadas y credenciales con caducidad fijada en el pasado. Se contrastan las decisiones con los registros del destino.

La validación real de OpenAI requiere un modelo explícito y un archivo privado de clave de prueba con permisos 0600. --model y --provider-key-file habilitan llamadas de pago con datos empresariales sintéticos. No hay sustitución por resultados sintéticos ante fallos. El 2026-09-18 se validaron los tres escenarios con OpenAI real y `gpt-4.1-mini`, con dos llamadas al modelo por escenario. El destino MCP y los datos de negocio siguen siendo sintéticos. Esto valida ese modelo y cuenta, no todos los proveedores ni entornos de producción. Se eliminan las cookies de respuesta LLM; las marcas temporales enteras acotadas de Chat Completions, OpenAI Responses y los formatos SSE admitidos se trata como metadato temporal. Los campos de negocio anidados siguen inspeccionándose.

Solo se eliminan los proyectos de prueba creados por el ejemplo. No se verifican HA, rendimiento, streaming en tiempo real ni cancelación. Consulta la guía inglesa para todos los comandos y límites.

```bash
pip install -e '.[dev,console,compat,llm-compat]'
python -m examples.agent_workflow --report .runtime-state/workflow-042.json
```

[Full setup / live mode / evidence](../en/agent-workflow.md)


## 0.42

La validación ampliada cubre un servidor MCP local real, fallos del inspector, recuperación y antirrepetición en un mismo host, y contratos sintéticos de cuatro proveedores. No certifica MCP de clientes, otras cuentas reales ni HA entre servidores. En pruebas locales de cinco segundos, a 0,1 RPS por usuario hipotético, 10 y 30 RPS dieron resultados previstos; desde 50 RPS aparecieron respuestas 503. No hubo eliminaciones prohibidas ni fugas de PII en las muestras. No es una garantía de capacidad ni una recomendación de hardware; los resultados detallados están en inglés.

[Detailed qualification and measurements](../en/agent-workflow.md#042-extended-qualification)

SSE: el correo dividido en dos fragmentos se enmascaró antes de entregar la respuesta completa. El proveedor sintético terminó tras el timeout del cliente; no se garantiza cancelación inmediata de la generación.
