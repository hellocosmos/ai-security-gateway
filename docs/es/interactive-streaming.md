# Decisión sobre streaming interactivo — 0.45

La ruta actual inspecciona la respuesta SSE completa antes de entregarla. No se habilita entrega parcial. Una opción futura debe demostrar detección PII y secretos entre fragmentos, decisión antes de cada byte, manejo SSE malformado o repetido, límites de memoria y presión, bloqueo seguro al cancelar o expirar y aprobación antes de acciones. El contenido ya enviado no puede retirarse. Si una ruta no cumple, mantenga buffering completo y mida su UX.
