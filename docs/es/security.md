# Alcance de seguridad y notificación

[English](../en/security.md) · [한국어](../ko/security.md) · [简体中文](../zh-CN/security.md) · [日本語](../ja/security.md) · [Español](../es/security.md) · [Français](../fr/security.md)

**Canal de políticas 0.47:** el plano de control firma las instantáneas con una clave Ed25519 del volumen `control-keys`; el plano de datos las verifica con la clave pública del volumen de solo lectura `policy-trust` y, ante cualquier rechazo, conserva su última política verificada. Restrinja la escritura en ambos volúmenes. Consulte [separación de planos](plane-separation.md).

La consola admite SSO Microsoft Entra ID de un solo tenant con roles Administrador y Lector. La identidad del operador y la autorización del agente son límites distintos; el Access Broker integrado aplica la autorización. [Entra SSO](identity.md).

Notifique vulnerabilidades en privado a **hellocosmos@gmail.com** , indicando revisión, reproducción sintética e impacto. No incluya datos de clientes, tokens ni credenciales reales en incidencias públicas. No se promete un SLA de respuesta fijo.

## Cobertura PII

La inspección sin conexión evalúa los seis perfiles de idioma para cada carga compatible:

- Inglés: correo electrónico, teléfono, tarjeta de crédito, IBAN y SSN estadounidense.
- Coreano: registros de residente y extranjero, permiso de conducir, pasaporte y registro empresarial.
- Chino simplificado: teléfono y número de identidad de residente GB 11643.
- Japonés: teléfono y número individual de 12 dígitos (My Number).
- Español: teléfono, NIF, NIE y pasaporte.
- Francés: teléfono y número de seguridad social NIR, incluidos códigos de Córcega.

Los identificadores nacionales validan formato y suma de comprobación cuando la norma la define. Es inspección determinista de patrones, no NER general: nombres, ubicaciones, direcciones postales, imágenes, OCR y archivos arbitrarios quedan fuera de esta versión.

### Selección de política y evidencia Mirror

El tratamiento PII usa una precedencia determinista: **herramienta/acción mapeada → ruta → valor global**. La acción elegida para la solicitud también rige su respuesta compatible, incluido SSE almacenado por completo. La evidencia solo registra la acción y el alcance, nunca el contenido capturado. En modo Mirror, un hallazgo completo conserva `would_redact` o `would_block` y los bytes originales siguen sin cambios; un transporte o una inspección incompletos quedan como `unknown`.

## Cobertura de exposición de secretos

La inspección sin conexión bloquea claves privadas reconocidas, formatos comunes de tokens de AWS, GitHub, GCP, Slack, Stripe y OpenAI, JWT firmados con estructura válida, combinaciones de consulta SAS de Azure Storage y valores de alta entropía en campos JSON sensibles. Se aplica a cuerpos de solicitud compatibles, respuestas y flujos SSE reensamblados.

Las cabeceras `Authorization`, cookie y API-key de la solicitud solo se conservan para la ruta de destino ya autenticada por firma y asignada explícitamente, y se omiten de la auditoría. Las cabeceras de respuesta sí se inspeccionan. Texto parecido a JWT pero no válido, parámetros `sig` ordinarios y marcadores de documentación no se bloquean. El registro contiene solo `secret_detected`, nunca el valor capturado. La cobertura determinista puede omitir formatos nuevos o propios y producir falsos positivos; rote toda credencial real que pudiera haber cruzado un límite no confiable.

El perímetro cubre tráfico HTTP/MCP compatible, enrutado explícitamente desde un salto firmado de confianza. Los ejemplos locales son demostraciones sintéticas, no equipos de producción endurecidos.

- Limite los listeners de texto claro, ExtProc y mirror a redes y remitentes de confianza.
- Proteja y rote las claves de firma; nunca las entregue a agentes. Imponga rutas al destino para evitar desvíos.
- Los fallos inline del inspector o de autorización deben bloquear. El colector mirror separado no bloquea originales; Mirror de la consola usa una ruta síncrona y bloquea si falla la comunicación con el inspector.
- Configure límites de cuerpo/tiempo, mapeos y ocultación por campo. SSE con búfer tiene límites, no es streaming ilimitado.
- La protección de repetición y auditoría SQLite local no garantiza HA distribuida ni retención inmutable.
- La detección de patrones y PII tiene falsos positivos y negativos.
- Un origen firmado no acredita la identidad humana o del agente. El modo Broker requiere una cadena JWT verificada y un mapeo explícito de claims.

La cuenta inicial es `admin` con contraseña `1234`; cámbiela en Configuración. La gestión escucha en loopback. La configuración de red administra el contenedor Envoy propio de la demo, no direcciones de interfaces del SO, rutas físicas ni reglas de firewall. Autenticación, controles CSRF y hashes no convierten esta demo sintética en IAM de producción. MIT cubre todo el runtime y Access Broker; los activos y credenciales de clientes quedan fuera del repositorio.
