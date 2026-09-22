# Operator workspace (0.44)

The Docker console now includes a connection workspace under **Connections / System** and **Settings**. The four model profiles generate native provider mappings; HTTP/MCP profiles generate explicitly blocked tools. Review actions, resources and redaction fields before permitting traffic. Advanced mappings remain editable as JSON.

## Save, activate and recover

Validate and save a staged connection. A new target secret is write-only and stored in an owner-only file in the state volume. Leave it blank to retain a referenced credential. Saving does not change the active gateway. Console origin, gateway authentication and Access Broker trust remain controlled by the mounted deployment file.

During a maintenance window, run these commands from `deploy/selfhost`:

```bash
docker compose stop app envoy
docker compose run --rm app activate-config
docker compose up -d app envoy
```

Activation refuses to run while the app holds its runtime lock or the configured Envoy listener is reachable. Stop both services as shown: the CLI cannot verify that a separately managed Envoy has stopped. Changes are deliberately not hot-reloaded. Route mapping changes reset route policies to the new configured defaults; review them before activation. Accounts, client keys and audit history are preserved.

The console shows active settings separately from pending changes and retains ten saved revisions. Restoring a revision stages it; repeat the maintenance commands to apply it. The previous policy snapshot is restored when available. Managed credential files remain in the protected state volume so restoration works; back up the volume securely. External secret files must still be mounted when an old revision is restored. Connection settings stored in state take precedence over connection fields in `deployment.yaml`; the file still controls console origin, gateway authentication and broker trust.

## Diagnosis and preview

Diagnostics inspect the inspector/Envoy listeners and observed gateway outcomes. The app does not bypass the isolated egress network to contact the destination. Listener readiness does not establish destination authentication. Counters contain only phase, HTTP status, count and timestamp and reset when the app restarts. `gateway_authentication` identifies admission failures; `inspection_path_transport` identifies transport failures; a response from the inspection path alone cannot distinguish destination rejection from local policy. Correlate it with Traffic / Events evidence.

Policy preview uses the same local content/routing engine in an isolated temporary store. It never calls the destination, changes policy, checks agent authorization or creates approvals. Results include allow/block/redact, reason codes and entity types; request content is not returned or persisted. Use synthetic JSON, up to 8 KiB. Apply real policy changes separately in Policies.

## First success

1. Initialize the Docker installation with a unique administrator password.
2. Configure a fixed destination and keep gateway credentials separate from destination credentials.
3. Send one permitted request, synthetic PII and a blocked action through the actual gateway; check output and Traffic / Events.
4. Stage a change, activate it with the stack stopped, and verify persistence after restart.
5. Stage a saved revision and verify recovery before relying on it operationally.

Use the [installation fixture](self-hosting.md) for deterministic evaluation and the [two-agent workflow](agent-workflow.md) for model-to-tool evidence. A customer MCP with its actual account and authorization remains a separate qualification, not something these synthetic checks prove.

## 0.44 · Buffered SSE

[Buffered SSE latency and rollout fit](latency.md)

The gateway collects and inspects the complete supported response before delivering content. Client first-content latency includes collection and inspection, not just scanner time. This suits workflows that can wait for a complete result; interactive chat must be tested against an explicit latency budget.
