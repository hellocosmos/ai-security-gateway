# Interactive streaming decision — 0.45

The shipping response path still buffers the complete supported SSE response before release. Interactive partial delivery is not enabled. A candidate streamed path must prove cross-chunk PII and secret detection, policy decisions before each released byte, malformed/replayed SSE handling, bounded memory and backpressure, timeout/cancel fail-closed behavior, and approval before any downstream action. Content already sent cannot be recalled. If these checks cannot be guaranteed for a route, use full buffering and measure the UX budget.
