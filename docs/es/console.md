# Instalación y operación de la consola

> **0.44:** [Espacio de operación (0.44)](operator-workspace.md)


> **AISG:** [Conectar, identificar, controlar, verificar](aisg.md). El gateway autentica con una clave de despliegue o JWT verificado. agent_key identifica agentes registrados sin IAM externo. JWT identity_mode: agent usa los atributos verificados de tenant y agente; delegated también exige usuario, tarea y delegación. Los agentes existentes requieren delegación por defecto.

> Docker 0.44: [Autoalojamiento](self-hosting.md) · [Compatibilidad del gateway](gateway-compatibility.md). Esta página describe la demostración sintética separada desde fuentes.

[English](../en/console.md) · [한국어](../ko/console.md) · [简体中文](../zh-CN/console.md) · [日本語](../ja/console.md) · [Español](../es/console.md) · [Français](../fr/console.md)

La consola admite SSO Microsoft Entra ID de un solo tenant con roles Administrador y Lector. La identidad del operador y la autorización del agente son límites distintos; el Access Broker integrado aplica la autorización. [Entra SSO](identity.md).

## Instalar e iniciar

Requisitos: Python 3.11+, Node.js 22.12+ o 24, npm y Docker Engine/Desktop local en ejecución. Solo hace falta este repositorio: no requiere SDK, paquete runtime privado ni API de modelos. Los scripts usan `uv` si está instalado; en caso contrario, Python venv/pip. Ejecute sin sudo y mantenga Docker local.

```bash
git clone https://github.com/hellocosmos/ai-security-gateway.git
cd ai-security-gateway
./scripts/install-console.sh
./scripts/run-console.sh
```

Abra [http://127.0.0.1:5176](http://127.0.0.1:5176). La cuenta inicial es **admin / 1234** . Cámbiela en **Configuración → Contraseña de administrador** ; se revocan todas las sesiones. La consola solo escucha en loopback: es una instalación local de evaluación, no un dispositivo expuesto a Internet. Los conflictos de puerto detienen el inicio sin terminar otros servicios. Ctrl+C detiene la aplicación y elimina únicamente el contenedor Envoy de esta instalación.

## Idioma

Seleccione el idioma en el acceso o la barra superior. El inglés es predeterminado; se incluyen coreano, chino simplificado, japonés, español y francés. La selección se guarda en el navegador y no cierra la sesión. La documentación se abre en ese idioma. Los nombres de herramientas, códigos de reglas, identificadores y entradas del usuario permanecen iguales. Traducir la UI no amplía la cobertura lingüística de PII.

## Ruta real del tráfico

```text
Browser -> management API/UI :5176
                 -> signed synthetic sender -> Envoy :18082 -> HTTP destination :18090
                                                 <-> gRPC inspector :18101–18104
                 <- response inspection <- decision + receipt <- UI
```

El emisor simula un salto de confianza y firma solicitudes sintéticas exactas; no es un descifrador TLS ni un IdP. Envoy es real y el destino HTTP es independiente. La demo usa el Access Broker integrado real con identidades sintéticas y aprobación vinculada a la solicitud, sin ejecutar acciones externas.

## Páginas y primer recorrido

1. **Panel:** ejecute lectura de notas, ocultación de datos, bloqueo de credenciales filtradas, borrado, inyección, transferencia externa y PII de respuesta. Los datos proceden de solicitudes reales, no de decisiones precargadas.
2. **Tráfico / Eventos:** filtre y revise el estado HTTP, recepción en destino, ocultación y versión de política. El CSV contiene metadatos depurados.
3. **Políticas:** bloquee `notes.read`, valide, aplique y repita. Restaure permitir al terminar. Los cambios afectan a flujos nuevos; los ya iniciados conservan su política.
4. **Conexiones / Sistema:** revise componentes y ruta. ** Auditoría:** examine cambios de sesión, política y red.
5. **Configuración:** vea las interfaces y cambie puerto, tiempo de espera o límite del cuerpo. La validación utiliza Envoy. Aplicar reinicia brevemente el contenedor propio, comprueba la nueva escucha y restaura la anterior si falla.

## Política PII por ruta y herramienta

La acción PII global es el valor predeterminado. Una ruta HTTP/MCP puede sustituirla y una acción mapeada o herramienta MCP puede sustituir la ruta. La precedencia exacta es **herramienta/acción → ruta → global**; los valores omitidos se heredan. La acción y el alcance elegidos se guardan en la evidencia depurada y se reutilizan al inspeccionar la respuesta correspondiente.

En **Políticas → Excepción de PII**, configure cada herramienta de la demo para heredar, ocultar o bloquear. En modo Mirror no se modifican la solicitud ni la respuesta originales; la interfaz muestra **Permitiría**, **Ocultaría** o **Bloquearía**. `unknown` se reserva para capturas incompletas o fallos de inspección. El resultado Mirror es evidencia de evaluación, no prueba de aplicación en producción.

## Red y NIC

| Ajuste | Valor predeterminado / significado |
|---|---|
| Despliegue | L7 explícito, una interfaz loopback |
| API/UI de gestión | `127.0.0.1:5176` |
| Entrada del proxy | `127.0.0.1:18082`, puerto no privilegiado configurable |
| Inspector | `127.0.0.1:18101–18104`, gRPC ExtProc |
| Destino | `127.0.0.1:18090`, solo HTTP sintético |
| Tiempo de espera | 5 segundos, configurable entre 2 y 30 |
| Límite de cuerpo | 1 MiB, configurable entre 1 KiB y 1 MiB |
| Interfaces | Nombres, direcciones, enlace, MTU y función reales del host |

El número de interfaces no es el de NIC físicas: incluye loopback, puentes y túneles. Este perfil no configura enrutamiento físico con una/dos NIC, puente transparente, IP/rutas del SO ni fijación de salida física. El formulario no admite destinos de producción arbitrarios. macOS utiliza reenvío al host de Docker Desktop; Linux usa host networking para llegar al loopback. Envoy 1.39.1 está fijado con un digest multi-arquitectura amd64/arm64.

## Modos de inspección y fallos

**Inline** permite, bloquea u oculta. Rechaza solicitudes sin asignación o firma y bloquea si falla la comunicación del inspector. ** Mirror en esta consola** observa la misma ruta síncrona sin modificar contenido ni consumir aprobaciones; los fallos de comunicación siguen bloqueando. El colector mirror independiente del inspector recibe copias y no puede afectar al original. Ninguno proporciona inspección de streaming ilimitado. No hay alternativa de llamada directa al motor si falla el proxy.

## Persistencia y solución de problemas

`.runtime-state/console` guarda hashes de cuenta/sesión, políticas, configuración de red y eventos SQLite depurados. Use `TD_CONSOLE_STATE` para otro directorio privado. Haga copias con el servicio detenido; cambiar la ruta crea una instalación distinta. Se excluye de Git. La clave de firma es efímera dentro de la demo, sin provisionar saltos externos. Los contadores del destino se reinician con el proceso; las evidencias guardadas permanecen. La auditoría es local y modificable, no inmutable.

Si falla el inicio, revise Docker y los puertos 5176/18101–18104/18111–18114/18090 y el puerto del proxy. No termine servicios ajenos automáticamente. La ausencia de evidencias es un error, no un éxito. La latencia incluye efectos locales y del contenedor; no es un benchmark de producción. TLS real, IAM, enrutamiento forzado, HA y endurecimiento necesitan validación aparte.

## Verificar y mantener traducciones

```bash
.venv/bin/python -m pytest -q
npm run check --prefix console
npm run build --prefix console
# Stop the running console before this Docker test.
TD_CONSOLE_E2E=1 .venv/bin/python -m pytest tests/test_console.py -q
```

Sin `TD_CONSOLE_E2E=1` se omiten las pruebas Docker. Se comprueba la igualdad de claves y marcadores en los seis diccionarios y que el código esté en inglés. Actualice las claves inglesas y todos los JSON a la vez, sin cambiar los códigos API estables. En caso de discrepancia, la documentación inglesa es la referencia. Consulte [arquitectura](architecture.md), [ediciones](editions.md), [migración](migration.md) y [seguridad](security.md).


## Operaciones en un mismo host

[1 / 2 / 4 inspectors · Linux service](operations.md)
