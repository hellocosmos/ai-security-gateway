# 控制平面/数据平面分离（0.47）

[English](../en/plane-separation.md) · [한국어](../ko/plane-separation.md) · [简体中文](../zh-CN/plane-separation.md) · [日本語](../ja/plane-separation.md) · [Español](../es/plane-separation.md) · [Français](../fr/plane-separation.md)

**保证：**控制台（控制平面）停止、崩溃，或其数据库被锁定、损坏时，数据平面继续执行**最近一次验证通过的策略快照**。检查或证据存储不可用时，数据平面仍然失败关闭（fail closed）。没有任何请求会在没有检查结论的情况下到达目标。

这是单个 Docker 主机内的故障域分离，不是多节点 HA。

## 服务

| Compose 服务 | 职责 | 监听 | 持有 |
|---|---|---|---|
| `app` | 控制平面：控制台、策略发布、CLI（`init`、`client-key`、`activate-config`） | 18080（公开） | `console.sqlite`、Ed25519 策略**签名**密钥（`control-keys` 卷） |
| `dataplane` | 网关、检查器（或检查器池）、证据 spool | 18084（公开）、18081 与 18085（内部） | 仅策略**验证**密钥（`policy-trust`，只读）、nonce、broker 状态 |
| `envoy` | 私有检查代理 | 18082（内部） | 生成的配置 |

数据平面从不打开 `console.sqlite`，也不读取 `deployment.yaml`。策略和连接设置只通过签名快照传入。Envoy 在数据平面就绪后启动，而不是在控制台就绪后。

## 策略快照

- 每次应用策略及每次启动时，都会在 `/state/policy/` 下发布不可变快照（`history/` 与原子替换的 `current.json`）。内容未变时不重新发布。
- 数据平面每 0.25 秒检查新快照，验证签名、格式、模式和修订顺序。新请求使用新策略；进行中的请求保留开始时的策略。
- **应用在执行生效后返回。**控制台应用策略时，最多等待 5 秒，直到数据平面（以及池中每个检查器）报告新修订版。若未收到确认，策略仍会保存，并审计 `policy.dataplane_pending`。
- 被拒绝的快照不会替换正在运行的策略。拒绝信息显示在“连接”页面的数据平面状态中，并审计为 `dataplane.snapshot_rejected`。

| 拒绝原因 | 含义 |
|---|---|
| `policy_snapshot_signature_invalid` | 签名后内容被修改，或由其他密钥签名 |
| `policy_snapshot_malformed` / `policy_snapshot_invalid` | 文件不完整、不可读或不符合模式 |
| `policy_snapshot_revision_regressed` | 比正在运行的修订版更旧 |
| `connection_changed_restart_required` | 路由、目标或认证已变更，需要重启数据平面 |
| `policy_snapshot_missing` / `policy_trust_key_unavailable` | 没有可验证的内容；启动时数据平面保持关闭 |

## 证据

决策记录写入 `/state/dataplane/events/` 下按进程划分的 spool，每条记录执行 `fsync`。控制台将其导入自身数据库，事件与读取位置在同一事务中提交，因此控制台重启不会丢失或重复记录。控制台停机期间产生的记录会在其恢复后出现。事件与概览 API 在响应前会先导入待处理记录。

在 **inline** 模式下若无法写入记录，该请求失败关闭；在存储恢复可写之前，新请求返回 HTTP 503 `dataplane_unavailable`。mirror 模式继续运行并报告存储故障。具体原因只出现在运维状态中，不会出现在客户端响应里。

## 故障行为（已验证）

| 故障 | 行为 | 依据 |
|---|---|---|
| 控制台进程被强制终止 | 允许与阻止判定持续生效；重启后导入证据 | `tests/runtime/test_plane_faults_runtime.py` F1 |
| `console.sqlite` 被独占锁定 | 不增加检查延迟 | F2（Docker）与 `tests/test_plane_isolation.py` |
| `console.sqlite` 损坏或删除 | 数据平面不受影响 | `tests/test_plane_isolation.py` |
| 快照被篡改、不完整、使用其他密钥或更旧 | 保留最近一次有效策略；审计拒绝 | F4（Docker）与单元测试 |
| 数据平面启动时没有快照 | 不处理任何请求 | F5 |
| 检查器 worker 被强制终止 | 该请求失败；worker 被替换 | `test_selfhost_runtime.py` 池测试 |
| Envoy 停止 | HTTP 503，无直连回退 | F10 |
| 证据存储写入失败（inline） | 请求失败关闭；存储恢复前拒绝准入 | 单元测试 |

使用 `TD_FAULT_E2E=1 python -m pytest tests/runtime/test_plane_faults_runtime.py -q` 运行 Docker 故障注入套件。

## 运维

```bash
docker compose ps
docker compose logs --tail=100 app dataplane envoy
# 数据平面就绪与状态（内部端口，不对外公开）：
docker compose exec -T dataplane python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:18085/_trapdefense/status').read().decode())"
```

激活已暂存的连接设置需要停止全部三个服务。只要控制台、数据平面或 Envoy 仍在运行，`activate-config` 就会拒绝执行。

```bash
docker compose stop app dataplane envoy
docker compose run --rm app activate-config
docker compose up -d app dataplane envoy
```

固定目标凭据（`static_bearer`、`static_api_key`）需同时挂载到 `dataplane`（使用）和 `app`（激活时校验）。轮换后重启 `dataplane`。

备份：`state` 与 `generated` 是必需的。若丢失 `control-keys` 或 `policy-trust`，控制台会在下次启动时生成新密钥对并重新发布快照。

## 从 0.46 升级

1. 按[自托管](self-hosting.md)说明备份并停止堆栈。
2. 更新源码，然后运行 `docker compose build app`。
3. 迁移私有 Compose 覆盖：网关公开端口的变更和目标密钥挂载应放在 `dataplane` 上（密钥挂载也需放在 `app` 上）。
4. 运行 `docker compose up -d`。控制台根据现有保存的策略发布首个签名快照；数据平面等待该快照后进入就绪状态。

镜像默认命令 `serve` 在一个容器内以独立的受监管进程运行两个平面：控制台退出时只重启控制台，数据平面退出时容器停止。如需上述隔离，请使用分离的 Compose 服务。

## 性能

网关首个内容 p95（毫秒），与[延迟](latency.md)使用相同的合成基准和主机（2026-10-01，Docker ARM64，14 个 CPU）。差异在单次运行的波动范围内。突发、PII、大小限制、超时和凭据边界均未改变。独立的控制台进程约增加 110 MiB 内存（采样峰值：数据平面 149.5 MiB、CPU 85.6%，控制台 109.4 MiB）。[JSON](../evidence/latency-047-synthetic.json)

| 场景 · 并发 | 0.46 | 0.47 |
|---|---:|---:|
| short · 1 / 8 / 32 | 232 / 420 / 1253 | 224 / 430 / 1232 |
| long · 1 / 8 / 32 | 822 / 1164 / 3014 | 810 / 1183 / 3112 |

## 限制

- 单主机。审批、代理注册和凭据签发需要控制台；控制台停机时，已有的审批与凭据仍然有效。
- 只有在 `policy-trust` 与 `control-keys` 的写权限受到限制时，签名密钥才能保护快照通道。能同时写入这两个卷的主体可以签署策略。
- 修订顺序仅在数据平面进程运行期间强制执行。重启后，数据平面接受当前的签名快照。
- Broker 状态与本地代理凭据仍是 `state` 卷上的共享文件。
