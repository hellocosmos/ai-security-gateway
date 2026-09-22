"""Fixed-destination configuration. No client-controlled upstream selection."""
from pathlib import Path
import copy
from typing import Annotated, Literal
from urllib.parse import urlsplit
import ipaddress
import re
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from asr_proxy.inspection.contracts import RouteRule
from .providers import ProviderProfile, ORIGINS
from asr_proxy.inspection.identity import TRANSPORT_HEADERS, reserved_header


def _network_url(value: str, field: str, *, allow_loopback: bool, resource: bool = False):
  parsed=urlsplit(value)
  loopback=parsed.hostname in ('localhost','127.0.0.1','::1')
  if (parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password
      or parsed.fragment or (parsed.scheme=='http' and not (allow_loopback and loopback))):
    raise ValueError(f'{field} must use HTTPS; explicit synthetic mode permits HTTP loopback only')
  if resource and (parsed.query or not parsed.path.startswith('/')):
    raise ValueError(f'{field} must be an absolute resource URI without query or fragment')
  return parsed


class ClientKeyGatewayAuth(BaseModel):
  model_config = ConfigDict(extra='forbid')
  mode: Literal['client_key'] = 'client_key'


class AgentKeyGatewayAuth(BaseModel):
  model_config = ConfigDict(extra="forbid")
  mode: Literal["agent_key"] = "agent_key"


class AgentIdentityClaims(BaseModel):
  """Explicit allowlist that maps verified JWT claims to broker identity fields."""
  model_config = ConfigDict(extra='forbid')
  tenant_id: str = 'tid'
  user_id: str = 'sub'
  agent_id: str = 'agent_id'
  delegation_id: str = 'delegation_id'
  task_id: str = 'task_id'
  agent_instance_id: str | None = 'agent_instance_id'
  approval_id: str | None = 'approval_id'

  @model_validator(mode='after')
  def validate_claim_names(self):
    values = [value for value in self.model_dump().values() if value is not None]
    if any(not re.fullmatch(r'[A-Za-z0-9_.:/-]{1,128}', value) for value in values):
      raise ValueError('Identity claim names must be explicit JWT claim keys')
    return self


class JwtGatewayAuth(BaseModel):
  model_config = ConfigDict(extra='forbid')
  mode: Literal['jwt'] = 'jwt'
  identity_mode: Literal['delegated','agent'] = 'delegated'
  issuer: str
  audience: str = Field(min_length=1,max_length=512)
  jwks_uri: str
  resource: str
  authorization_servers: list[str] = Field(min_length=1,max_length=5)
  required_scopes: list[str] = Field(min_length=1,max_length=32)
  authorized_parties: list[str] = Field(default_factory=list,max_length=32)
  allow_insecure_loopback: bool = False
  identity_claims: AgentIdentityClaims | None = None

  @model_validator(mode='after')
  def validate_contract(self):
    _network_url(self.issuer,'issuer',allow_loopback=self.allow_insecure_loopback)
    _network_url(self.jwks_uri,'jwks_uri',allow_loopback=self.allow_insecure_loopback)
    resource=_network_url(self.resource,'resource',allow_loopback=self.allow_insecure_loopback,resource=True)
    for server in self.authorization_servers:
      _network_url(server,'authorization_servers',allow_loopback=self.allow_insecure_loopback)
    if len(set(self.authorization_servers))!=len(self.authorization_servers):
      raise ValueError('authorization_servers must be unique')
    if self.issuer not in self.authorization_servers:
      raise ValueError('authorization_servers must include the token issuer')
    if len(set(self.required_scopes))!=len(self.required_scopes) or any(
        not re.fullmatch(r'[A-Za-z0-9._:/-]{1,128}', scope) for scope in self.required_scopes):
      raise ValueError('required_scopes must be unique OAuth scope tokens')
    if len(set(self.authorized_parties))!=len(self.authorized_parties) or any(
        not value or len(value)>256 or any(c.isspace() for c in value) for value in self.authorized_parties):
      raise ValueError('authorized_parties must contain unique non-empty client identifiers')
    if any(c.isspace() for c in self.audience):raise ValueError('audience must not contain whitespace')
    if resource.path=='':self.resource=self.resource.rstrip('/')
    return self

  @property
  def metadata_path(self):
    path=urlsplit(self.resource).path.rstrip('/')
    return '/.well-known/oauth-protected-resource'+path

  @property
  def metadata_url(self):
    parsed=urlsplit(self.resource)
    return f'{parsed.scheme}://{parsed.netloc}{self.metadata_path}'


GatewayAuth = Annotated[ClientKeyGatewayAuth | JwtGatewayAuth | AgentKeyGatewayAuth, Field(discriminator='mode')]


class AccessBrokerDeployment(BaseModel):
  model_config = ConfigDict(extra='forbid')
  enabled: bool = False
  tenant_id: str | None = Field(default=None,min_length=1,max_length=256)

  @model_validator(mode='after')
  def validate_tenant(self):
    if self.enabled != bool(self.tenant_id):
      raise ValueError('Enabled Access Broker requires one tenant_id')
    return self


class TargetAuth(BaseModel):
  model_config = ConfigDict(extra='forbid')
  mode: Literal['none','passthrough_bearer','static_bearer','static_api_key'] = 'passthrough_bearer'
  secret_file: str | None = None
  header: str | None = None
  prefix: str = ''

  @model_validator(mode='after')
  def validate_contract(self):
    static=self.mode in ('static_bearer','static_api_key')
    if static != bool(self.secret_file):
      raise ValueError('Static target authentication requires one secret_file')
    if self.secret_file and not Path(self.secret_file).is_absolute():
      raise ValueError('secret_file must be an absolute path')
    if self.mode=='static_api_key':
      if not self.header or not re.fullmatch(r'[A-Za-z0-9!#$%&\'*+.^_`|~-]{1,64}',self.header):
        raise ValueError('static_api_key requires a valid header')
      self.header=self.header.lower()
      if self.header=='authorization' or self.header in TRANSPORT_HEADERS or reserved_header(self.header):
        raise ValueError('Target API-key header is reserved')
    elif self.header is not None:
      raise ValueError('header is supported only for static_api_key')
    if self.mode!='static_api_key' and self.prefix:
      raise ValueError('prefix is supported only for static_api_key')
    if len(self.prefix)>64 or '\r' in self.prefix or '\n' in self.prefix:
      raise ValueError('Invalid target credential prefix')
    return self

  def public(self):
    value={'mode':self.mode}
    if self.mode=='static_api_key':value.update(header=self.header,prefix=self.prefix)
    return value


class Deployment(BaseModel):
  model_config = ConfigDict(extra='forbid')
  upstream: str
  llm: ProviderProfile | None = None
  allow_plaintext_upstream: bool = False
  console_origin: str = 'http://localhost:18080'
  gateway_auth: GatewayAuth = Field(default_factory=ClientKeyGatewayAuth,discriminator='mode')
  access_broker: AccessBrokerDeployment = Field(default_factory=AccessBrokerDeployment)
  target_auth: TargetAuth = Field(default_factory=TargetAuth)
  destination_auth: Literal['passthrough', 'static_bearer'] | None = Field(default=None,exclude=True)
  bearer_file: str | None = Field(default=None,exclude=True)
  max_body_bytes: int = Field(default=1048576, ge=1024, le=1048576)
  gateway_max_inflight: int = Field(default=32, ge=4, le=64, strict=True)
  gateway_admission_wait_ms: int = Field(default=0, ge=0, le=2000, strict=True)
  inspector_replicas: Literal[1, 2, 4] = 1
  routes: list[RouteRule] = Field(min_length=1, max_length=100)

  @field_validator('inspector_replicas', mode='before')
  @classmethod
  def validate_inspector_replicas(cls, value):
    if type(value) is not int or value not in (1, 2, 4):
      raise ValueError('inspector_replicas must be 1, 2 or 4')
    return value

  @model_validator(mode='before')
  @classmethod
  def normalize_legacy_auth(cls,value):
    if not isinstance(value,dict):return value
    data=dict(value)
    if data.get('llm'):
      profile=ProviderProfile.model_validate(data['llm'])
      data.setdefault('upstream',ORIGINS[profile.provider])
      data.setdefault('routes',profile.routes())
      data.setdefault('target_auth',profile.target())
    legacy_mode=data.pop('destination_auth',None)
    legacy_file=data.pop('bearer_file',None)
    if 'target_auth' in data and (legacy_mode is not None or legacy_file is not None):
      raise ValueError('Use target_auth or legacy destination_auth, not both')
    if 'target_auth' not in data:
      if legacy_mode=='static_bearer':
        data['target_auth']={'mode':'static_bearer','secret_file':legacy_file}
      else:
        if legacy_file is not None:raise ValueError('passthrough must not set bearer_file')
        data['target_auth']={'mode':'passthrough_bearer'}
    return data

  @model_validator(mode='after')
  def validate_contract(self):
    target = urlsplit(self.upstream)
    if (target.scheme not in ('http', 'https') or not target.hostname or target.username or target.password
        or target.path not in ('', '/') or target.query or target.fragment):
      raise ValueError('upstream must be an HTTP(S) origin without credentials, path or query')
    if not re.fullmatch(r'[a-zA-Z0-9.-]+', target.hostname):
      raise ValueError('Use a DNS hostname or IPv4 upstream')
    if target.scheme == 'http' and not self.allow_plaintext_upstream:
      raise ValueError('HTTP requires allow_plaintext_upstream for a trusted network')
    if target.scheme == 'https':
      try: ipaddress.ip_address(target.hostname)
      except ValueError: pass
      else: raise ValueError('HTTPS requires a DNS hostname for certificate verification')
    if target.port is not None and not 1 <= target.port <= 65535:
      raise ValueError('Invalid upstream port')
    origin = urlsplit(self.console_origin)
    if (origin.scheme not in ('http', 'https') or not origin.hostname or origin.username or origin.password
        or origin.path or origin.query or origin.fragment):
      raise ValueError('console_origin must be an exact HTTP(S) origin')
    if self.gateway_auth.mode in ('jwt','agent_key') and self.target_auth.mode=='passthrough_bearer':
      raise ValueError('JWT or agent-key gateway authentication cannot use target Bearer passthrough')
    if self.gateway_auth.mode=='agent_key' and not self.access_broker.enabled:
      raise ValueError('Agent keys require the Access Broker')
    if self.access_broker.enabled and not (self.gateway_auth.mode=='agent_key' or (
        self.gateway_auth.mode=='jwt' and self.gateway_auth.identity_claims is not None)):
      raise ValueError('Access Broker requires agent_key or JWT gateway authentication with identity_claims')
    if self.llm:
      if self.upstream != ORIGINS[self.llm.provider]:
        raise ValueError('Provider profile requires its fixed HTTPS origin')
      if self.target_auth.mode not in ('static_bearer','static_api_key'):
        raise ValueError('Provider profiles require separate static target credentials')
      expected=self.llm.target()
      if self.target_auth.mode!=expected['mode'] or self.target_auth.header!=expected.get('header') or self.target_auth.prefix:
        raise ValueError('Provider authentication does not match its native API')
      if self.routes != [RouteRule.model_validate(r) for r in self.llm.routes()]:
        raise ValueError('Provider profiles use generated exact routes and model scopes')
    seen = set()
    for route in self.routes:
      if route.authority != target.netloc:
        raise ValueError('Every route authority must equal the fixed upstream authority')
      if (not re.fullmatch(r'/[A-Za-z0-9_./~:-]*', route.path) or '..' in route.path.split('/')
          or '//' in route.path or route.method not in ('GET','POST','PUT','PATCH','DELETE','HEAD')):
        raise ValueError('Routes require unambiguous exact paths and supported HTTP methods')
      pair = (route.method, route.path)
      if pair in seen: raise ValueError('Duplicate method/path mapping')
      seen.add(pair)
      if route.protocol == 'mcp' and route.method != 'POST':
        raise ValueError('This profile supports stateless MCP JSON POST only')
      rules = route.tools if route.protocol == 'mcp' else {route.tool: route.rule}
      if not rules or any(rule is None for rule in rules.values()):
        raise ValueError('Explicit tool/action rules are required')
      if any(not rule.resource and not rule.resource_pointer for rule in rules.values()):
        raise ValueError('Every rule requires a resource mapping')
    return self

  def entries(self):
    for index, route in enumerate(self.routes):
      rules = route.tools if route.protocol == 'mcp' else {route.tool: route.rule}
      for name, rule in rules.items():
        yield f'{index}:{name}', name, rule

  def public(self):
    return {'llm': self.llm.model_dump() if self.llm else None, 'upstream': self.upstream, 'console_origin': self.console_origin,
      'gateway_auth':{'mode':self.gateway_auth.mode},'target_auth':self.target_auth.public(),
      'access_broker':{'enabled':self.access_broker.enabled,'tenant_id':self.access_broker.tenant_id,
        'maturity':'experimental'},
      'destination_auth':self.target_auth.mode,'source': 'selfhost-adapter',
      'max_body_bytes': self.max_body_bytes,
      'gateway_max_inflight': self.gateway_max_inflight,
      'gateway_admission_wait_ms': self.gateway_admission_wait_ms,
      'inspector_replicas': self.inspector_replicas,
      'routes': [{'method': r.method, 'path': r.path, 'protocol': r.protocol,
                  'tools': list(r.tools) if r.protocol == 'mcp' else [r.tool]} for r in self.routes]}


def load(path):
  return Deployment.model_validate(yaml.safe_load(Path(path).read_text()))


def envoy_config(config):
  template = Path(__file__).parents[1] / 'console/envoy-inline.yaml'
  value = yaml.safe_load(template.read_text())
  clusters = value['static_resources']['clusters']
  def socket(cluster):
    return cluster['load_assignment']['endpoints'][0]['lb_endpoints'][0]['endpoint']['address']['socket_address']
  socket(clusters[0]).update(address='app', port_value=18081)
  if config.inspector_replicas > 1:
    inspector = clusters[0]
    group = inspector['load_assignment']['endpoints'][0]
    original = group['lb_endpoints'][0]
    group['lb_endpoints'] = []
    for index in range(config.inspector_replicas):
      member = copy.deepcopy(original)
      member['endpoint']['address']['socket_address'].update(address='app', port_value=18120 + index)
      member['endpoint']['health_check_config'] = {'port_value': 18130 + index}
      group['lb_endpoints'].append(member)
    inspector['lb_policy'] = 'ROUND_ROBIN'
    inspector['common_lb_config'] = {'healthy_panic_threshold': {'value': 0}}
    inspector['health_checks'] = [{'timeout': '1s', 'interval': '1s',
      'unhealthy_threshold': 1, 'healthy_threshold': 1,
      'http_health_check': {'path': '/_trapdefense/health', 'codec_client_type': 'HTTP1'}}]
  target = urlsplit(config.upstream)
  socket(clusters[1]).update(address=target.hostname, port_value=target.port or (443 if target.scheme=='https' else 80))
  if target.scheme == 'https':
    clusters[1]['transport_socket'] = {'name':'envoy.transport_sockets.tls','typed_config':{
      '@type':'type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext',
      'sni':target.hostname,'common_tls_context':{'validation_context':{
        'trusted_ca':{'filename':'/etc/ssl/certs/ca-certificates.crt'},
        'match_typed_subject_alt_names':[{'san_type':'DNS','matcher':{'exact':target.hostname}}]}}}}
  listener = value['static_resources']['listeners'][0]
  if config.llm:
    manager=listener['filter_chains'][0]['filters'][0]['typed_config']
    duration=f'{config.llm.timeout_seconds}s'
    manager['stream_idle_timeout']=duration
    route=manager['route_config']['virtual_hosts'][0]['routes'][0]['route']
    route['timeout']=duration
    route['max_stream_duration']['max_stream_duration']=duration
  listener['per_connection_buffer_limit_bytes'] = config.max_body_bytes
  return yaml.safe_dump(value, sort_keys=False)
