import React, {useEffect, useState} from 'react';
import {Panel} from './components';
import {request} from './client';
import {t} from './i18n';

export default function Operations({policy, readOnly=false}) {
  const [state,setState]=useState(null), [config,setConfig]=useState('');
  const [secret,setSecret]=useState(''), [profile,setProfile]=useState('http');
  const [models,setModels]=useState(''), [route,setRoute]=useState(0);
  const [origin,setOrigin]=useState(''), [path,setPath]=useState('/mcp');
  const [protocol,setProtocol]=useState('mcp'), [tools,setTools]=useState('notes.read');
  const [targetAuth,setTargetAuth]=useState('none');
  const [body,setBody]=useState('{"message":"Contact alex@example.com"}');
  const [result,setResult]=useState(null), [error,setError]=useState(''), [busy,setBusy]=useState(false);
  const [draftPolicy,setDraftPolicy]=useState(JSON.stringify(policy,null,2));
  async function reload() {
    const next=await request('/operations'); setState(next);
    setConfig(JSON.stringify((next.pending || {}).config || next.active,null,2));
    setSecret('');setOrigin(next.active.upstream);
  }
  useEffect(()=>{reload().catch(e=>setError(e.message));},[]);
  async function run(work) {
    setBusy(true); setError('');setResult(null);
    try {setResult(await work());} catch(e){setError(e instanceof SyntaxError ? t('Enter valid JSON.') : e.message);} finally {setBusy(false);}
  }
  function chooseProfile() {
    const current=JSON.parse(config);
    if(profile==='http') {
      const url=new URL(origin);
      const names=tools.split(',').map(x=>x.trim()).filter(Boolean);
      if(!names.length)throw new Error(t('Enter at least one tool name.'));
      const rule={action:'invoke',resource:'configured-service',effect:'block'};
      const mapping={authority:url.host,path,method:'POST',protocol,
        ...(protocol==='mcp' ? {tools:Object.fromEntries(names.map(name=>[name,rule])),redact_fields:['/params/arguments/message']} : {tool:names[0],rule,redact_fields:['/message']})};
      const next={console_origin:state.active.console_origin,gateway_auth:state.active.gateway_auth,
        access_broker:state.active.access_broker,upstream:origin,allow_plaintext_upstream:url.protocol==='http:',
        gateway_max_inflight:state.active.gateway_max_inflight,
        target_auth:targetAuth==='static_bearer' ? {mode:targetAuth,secret_file:'/state/new-target.key'} : {mode:targetAuth},
        routes:[mapping]};
      setConfig(JSON.stringify(next,null,2));return;
    }
    const next={console_origin:state.active.console_origin,gateway_auth:state.active.gateway_auth,
      access_broker:state.active.access_broker,max_body_bytes:state.active.max_body_bytes,
      gateway_max_inflight:state.active.gateway_max_inflight,
      llm:{provider:profile,models:models.split(',').map(x=>x.trim()).filter(Boolean)}};
    setConfig(JSON.stringify(next,null,2));
  }
  const input=()=>({version:state.version,config:JSON.parse(config),...(secret ? {target_secret:secret}: {})});
  return <Panel title={t('Connection workspace')} sub={t('Active settings and staged changes stay separate.')}>
    <div className="td-form-body td-operations">
      {error && <p className="td-error" role="alert">{t(error)}</p>}
      {!state ? <p>{t('Loading')}</p> : <>
        <div className="td-callout"><div><strong>{t(state.restart_required ? 'Changes staged — restart required' : 'Active connection')}</strong>
          <p>{state.active.upstream} · {state.active.gateway_auth.mode}</p>
          <p>{t('Saving does not change live traffic. Gateway identity settings remain managed in the deployment file.')}</p>
        </div></div>
        <fieldset disabled={busy || readOnly}>
          <h3>{t('1. Configure a connection')}</h3>
          <label>{t('Connection profile')}<select value={profile} onChange={e=>setProfile(e.target.value)}>
            <option value="http">HTTP / MCP</option>{['openai','anthropic','google','openrouter'].map(p=><option key={p} value={p}>{p}</option>)}
          </select></label>
          {profile==='http' && <>
            <label>{t('Destination origin')}<input value={origin} onChange={e=>setOrigin(e.target.value)} placeholder="https://tools.example.com"/></label>
            <label>{t('Request path')}<input value={path} onChange={e=>setPath(e.target.value)}/></label>
            <label>{t('Protocol')}<select value={protocol} onChange={e=>setProtocol(e.target.value)}><option value="mcp">MCP</option><option value="http">HTTP JSON</option></select></label>
            <label>{t('Tool names (comma-separated)')}<input value={tools} onChange={e=>setTools(e.target.value)}/></label>
            <label>{t('Destination authentication')}<select value={targetAuth} onChange={e=>setTargetAuth(e.target.value)}>{['none','passthrough_bearer','static_bearer'].map(a=><option key={a} value={a}>{a}</option>)}</select></label>
            <p>{t('New HTTP/MCP tools start blocked. Review actions, resources and redaction fields before allowing traffic. HTTP is unencrypted; use it only on a trusted network.')}</p>
          </>}
          {profile!=='http' && <label>{t('Allowed models')}<input value={models} onChange={e=>setModels(e.target.value)} placeholder="gpt-4.1-mini"/></label>}
          <button className="td-btn" onClick={()=>run(async()=>{chooseProfile();return {status:'profile_selected'};})}>{t('Prepare profile')}</button>
          <details><summary>{t('Connection settings (JSON)')}</summary><label>{t('Connection settings (JSON)')}<textarea rows={14} value={config} spellCheck={false} onChange={e=>setConfig(e.target.value)}/></label></details>
          <label>{t('New destination credential')}<input type="password" autoComplete="new-password" value={secret} onChange={e=>setSecret(e.target.value)}/></label>
          <p>{t('Leave blank to keep an existing credential. Secret values are never displayed again.')}</p>
          <div className="td-actions"><button className="td-btn" onClick={()=>run(()=>request('/operations/validate',input()))}>{t('Validate')}</button>
            <button className="td-btn primary" onClick={()=>run(async()=>{await request('/operations/stage',input());await reload();return {status:'staged'};})}>{t('Save staged settings')}</button></div>
          {state.history.length>0 && <label>{t('Restore a saved revision')}<select defaultValue="" onChange={e=>{const revision=Number(e.target.value);if(revision)run(async()=>{await request('/operations/restore',{version:state.version,revision});await reload();return {status:'restoration_staged'};});}}>
            <option value="">—</option>{[...new Set(state.history.map(h=>h.revision))].map(r=><option key={r} value={r}>{r}</option>)}</select></label>}
          <h3>{t('2. Activate during a maintenance window')}</h3>
          <p>{t('Stop both services, activate, then start both. Changed route mappings reset route policies to their configured defaults.')}</p>
          <pre>docker compose stop app envoy{'\n'}docker compose run --rm app activate-config{'\n'}docker compose up -d app envoy</pre>
          <h3>{t('3. Diagnose the active connection')}</h3>
          <p>{t('Checks inspector and Envoy listeners plus observed request outcomes. It does not bypass network isolation to probe the destination.')}</p>
          <button className="td-btn" onClick={()=>run(()=>request('/operations/diagnose',{}))}>{t('Check connection')}</button>
          <p>{t('401: check gateway or target credentials. 403: inspect policy and scope evidence. 503: check the inspection path and capacity. A status code alone does not identify which component rejected the request.')}</p>
          <button className="td-btn" onClick={()=>run(async()=>{await reload();return {status:'refreshed'};})}>{t('Refresh')}</button>
          <pre>{JSON.stringify(state.recent_gateway_outcomes,null,2)}</pre>
          <h3>{t('Latency observations')}</h3>
          <p>{t('Last 256 samples per phase in this process, including failures. Milliseconds. Refresh to update.')}</p>
          <div className="td-latency-scroll"><table><thead><tr><th>{t('Phase')}</th><th>{t('Samples')}</th><th>p50 (ms)</th><th>p95 (ms)</th><th>max (ms)</th></tr></thead>
            <tbody>{(state.latency?.series || []).map(row=><tr key={row.phase}>
              <td>{t({gateway_total:'Gateway response ready',envoy_exchange:'Envoy exchange',request_inspection:'Request inspection',response_metadata_inspection:'Response metadata inspection',response_inspection:'Response inspection'}[row.phase])}</td>
              <td>{row.samples}</td>{['p50_ms','p95_ms','max_ms'].map(key=><td key={key}>{row[key]===null ? '—' : row[key]}</td>)}
            </tr>)}</tbody></table></div>
          {!state.latency?.series.some(row=>row.samples>0) && <p>{t('No measurements yet')}</p>}
          <p>{t('Envoy exchange includes upstream collection and inspection. Inspection includes queue wait. These independent distributions cannot be subtracted. Gateway time ends before client delivery; measure client first-content latency separately.')}</p>
          <h3>{t('Last 10 request timelines')}</h3>
          <div className="td-latency-scroll"><table><thead><tr>{['Status','Total (ms)','Before Envoy (ms)','Upstream headers wait (ms)','Response body wait (ms)','Inspector stream wait (ms)','Inspector queue (ms)','Inspector work (ms)','After response check (ms)','Complete'].map(key=><th key={key}>{t(key)}</th>)}</tr></thead>
            <tbody>{(state.latency?.requests || []).slice(0,10).map((row,index)=><tr key={index}>
              <td>{row.http_status ?? '—'}</td>
              {['gateway_total_ms','before_envoy_ms','upstream_headers_wait_ms','response_body_wait_ms','inspector_stream_wait_ms','inspection_queue_ms','inspection_work_ms','after_response_check_ms'].map(key=><td key={key}>{row[key] ?? '—'}</td>)}
              <td>{t(row.complete ? 'Complete' : 'Incomplete')}</td>
            </tr>)}</tbody></table></div>
          {!state.latency?.requests?.length && <p>{t('No request timelines yet')}</p>}
          <p>{t('Request timelines contain numeric timings and status only. The body wait includes upstream work and transport. Durations overlap and must not be summed. Early authentication or admission failures appear in gateway outcomes, not these timelines.')}</p>
          <h3>{t('4. Preview local policy')}</h3>
          <p>{t('No upstream request or agent authorization. Preview does not modify the active policy or create approvals. Use synthetic data.')}</p>
          <label>{t('Configured routes')}<select value={route} onChange={e=>setRoute(Number(e.target.value))}>{state.active.routes.map((r,i)=><option key={i} value={i}>{r.method} {r.path}</option>)}</select></label>
          <label>{t('Sample JSON body')}<textarea rows={4} value={body} onChange={e=>setBody(e.target.value)}/></label>
          <label>{t('Candidate policy (not applied)')}<textarea rows={8} value={draftPolicy} onChange={e=>setDraftPolicy(e.target.value)}/></label>
          <button className="td-btn" onClick={()=>run(()=>request('/operations/preview',{route,body:JSON.parse(body),policy:JSON.parse(draftPolicy)}))}>{t('Preview decision')}</button>
        </fieldset>
        {result && <div role="status"><strong>{result.decision ? t({allow:'Allow',block:'Block',redact:'Redact',unknown:'Needs review'}[result.decision] || result.decision) : result.valid ? t('Validate') + ' ✓' : result.status}</strong><pre>{JSON.stringify(result,null,2)}</pre></div>}
        <h3>{t('First success checklist')}</h3>
        <ol><li>{t('Configure and activate one fixed destination.')}</li><li>{t('Send a permitted request through the gateway using separate gateway and target credentials.')}</li><li>{t('Send synthetic PII and an explicitly blocked action. Check the result and Traffic / Events evidence.')}</li><li>{t('Restart the stack and verify the active settings and policy persist.')}</li></ol>
      </>}
    </div>
  </Panel>;
}
