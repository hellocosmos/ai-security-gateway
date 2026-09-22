import React from 'react';
import { t } from './i18n';
import { Panel } from './components';

export default function DeploymentSettings({deployment, network}) {
  return <Panel title={t('Self-hosted AI Firewall')} sub={t('Configured destination only')}>
    <div className="td-form-body">
      <div className="td-callout"><div><strong>{t('Client → TrapDefense → MCP / API')}</strong><p>{t('Only routed traffic is inspected. Target-service permissions still apply.')}</p></div></div>
      <dl className="td-dl">
        <dt>{t('Destination')}</dt><dd>{deployment.upstream}</dd>
        <dt>{t('Client authentication')}</dt><dd>{deployment.gateway_auth?.mode || 'client_key'}</dd>
        <dt>{t('Destination authentication')}</dt><dd>{deployment.target_auth?.mode || deployment.destination_auth}</dd>
        <dt>{t('Inspector')}</dt><dd>{network?.inspector_ready ? t('Ready') : t('Unavailable')}</dd>
        <dt>Envoy</dt><dd>{network?.proxy_ready ? t('Listener reachable') : t('Unavailable')}</dd>
        {deployment.llm && <><dt>{t('Model provider')}</dt><dd>{deployment.llm.provider}</dd>
          <dt>{t('Allowed models')}</dt><dd>{deployment.llm.models.join(', ')}</dd>
          <dt>{t('Response delivery')}</dt><dd>{t('Buffered SSE: complete inspection before delivery')}</dd>
          <dt>{t('Provider timeout')}</dt><dd>{deployment.llm.timeout_seconds}s</dd></>}
        <dt>{t('Body limit')}</dt><dd>{deployment.max_body_bytes} bytes</dd>
        <dt>{t('Gateway in-flight limit')}</dt><dd>{deployment.gateway_max_inflight ?? 32}</dd>
      </dl>
      <p>{t('The connection key verifies deployment access, not agent or user identity.')}</p>
      <p>{t('Gateway and target credentials are separate. JWT gateway tokens are not forwarded to the target.')}</p>
      <p>{t(deployment.llm ? 'Native text and function calls. Files, media, provider-side tools and real-time streaming are not supported.' : 'JSON HTTP and stateless JSON MCP only. OAuth login brokering, sessions and long-lived SSE are not supported by this profile.')}</p>
      <h3>{t('Configured routes')}</h3>
      {deployment.routes.map(r=><p key={`${r.method}:${r.path}`}><code>{r.method} {r.path}</code> · {r.protocol} · {r.tools.join(', ')}</p>)}
      <p className="td-note">{t('Use the connection workspace below to stage destinations and mappings. Activate them with the stack stopped.')}</p>
      <p className="td-note">{t('Listener checks do not prove destination authentication or successful inspection. Send a test request and inspect its decision record.')}</p>
    </div>
  </Panel>;
}
