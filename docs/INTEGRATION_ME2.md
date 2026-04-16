# Integração MCBT 2.0 → ME2 (MES)

Guia de integração do **Checkweigher Dinâmico (CWD/MCBT 2.0)** com o **ME2 — Manufacturing Execution System** da Meitech.

> Audiência: dev (humano ou Claude Code) trabalhando no repositório do ME2 que precisa adicionar o MCBT como equipamento monitorado.
> Versão do firmware MCBT analisada: `250815`. Caminho do código fonte: `dev-meitech/mcbt_cpp`.

---

## 1. Visão geral

O MCBT é uma **classificadora/pesadora dinâmica** que combina pesos de N módulos para formar pacotes dentro da tolerância de uma receita. Roda em **Toradex Verdin iMX8 Plus + Ivy Carrier** com Linux Torizon, em C++17.

Diferente das máquinas Schneider/Siemens que o ME2 monitora hoje, **o MCBT NÃO precisa ser lido via Modbus pelo coletor do ME2** — o próprio firmware já expõe:

- **HTTP REST** (Pistache, porta `8080`) — leitura de produção, parâmetros, receita ativa, dados operacionais; CRUD; controle.
- **WebSocket** (libwebsockets, porta `9000`, protocolo `mcbt-protocol`) — broadcast de estado a 20 Hz (a cada 50 ms).
- **SQLite local** em `/home/torizon/data/database_mcbt.db` — histórico, receitas, parâmetros, usuários.

Portanto, o coletor do ME2 deve falar com o MCBT como um **client HTTP/WS**, não como mestre Modbus. Isso é uma classe nova de driver para o collector.

```
MCBT (Toradex)                      ME2 Collector             ME2 Backend
┌──────────────────┐  HTTP polling  ┌────────────────┐        ┌──────────┐
│ Pistache :8080   │ ──────────────►│ HttpDriver     │ ──────►│ SQLite   │
│ WebSocket :9000  │ ──────────────►│ (novo)         │        │ buffer   │
│ SQLite local     │                │                │        └────┬─────┘
└──────────────────┘                └────────────────┘             ▼
                                                              SyncService
                                                                   ▼
                                                              PostgreSQL
                                                                   ▼
                                                              WS /ws/live
                                                                   ▼
                                                              Dashboard
```

---

## 2. Identidade do equipamento

### Limitação atual do MCBT

O firmware **não armazena `serial_number`, `model` nem `manufacturer`**. A máquina é identificada apenas por:
- `machineType: "MCBT"` (constante hardcoded em `dashboardAPI.hpp:97`)
- `version: "250815"` (constante em `MCBT.hpp:192` — versão do firmware, não da máquina física)

### Decisão para o ME2

O `serial_number` (placa física, padrão Meitech `MEI-2024-NNNN`) deve ser **definido no `equipment.json` do ME2**, não lido do MCBT. Não há GVL_ME2 nesta máquina — o coletor injeta o serial.

Isso é coerente com `serial_number_source: "fixed"` que já existe no schema do ME2 (CLAUDE.md, seção Equipment JSON Config).

> **Ação futura recomendada (fora da POC):** adicionar campo `sSerialNumber` ao MCBT (tabela nova em SQLite + endpoint `GET /machine/identity`) para alinhar com o padrão GVL_ME2. Discutir com Gabriel/Paulo/Thalis no próximo ciclo.

---

## 3. equipment.json proposto para o MCBT

```json
{
  "serial_number": "MEI-2024-XXXX",
  "serial_number_source": "fixed",
  "name": "Checkweigher Dinâmico CWD-01",
  "model": "MCBT 2.0",
  "manufacturer": "Meitech",
  "plant_id": "<uuid>",
  "protocol": "http",
  "connection": {
    "host": "192.168.1.230",
    "http_port": 8080,
    "ws_port": 9000,
    "ws_path": "/",
    "ws_protocol": "mcbt-protocol",
    "auth": {
      "endpoint": "/usr/login",
      "user": "meitech",
      "password": "<from-env>"
    }
  },
  "polling": {
    "dashboard_interval_s": 5,
    "history_interval_s": 60,
    "operational_interval_s": 300,
    "use_websocket": true
  },
  "alerts": {
    "uptime_status_code": 18,
    "downtime_l1_min": 5,
    "downtime_l2_min": 15,
    "notify_l1": "operations",
    "notify_l2": "management"
  },
  "mcbt_specific": {
    "firmware_version_expected": "250815",
    "module_count": 16,
    "feeder_type": 0,
    "selector_funnel_type": 0
  }
}
```

`protocol: "http"` é um **valor novo** (hoje o ME2 só tem `s7`/`modbus`/`opcua`) — vai exigir um novo driver, ver §6.

---

## 4. Mapeamento de domínio MCBT → ME2

### O que conta como "uma peça produzida"

No mundo do ME2: `production_events` é gerado quando `parts_ok` muda (trigger on change).

No MCBT: uma "peça" = **um pacote fechado** com peso dentro da tolerância da receita ativa. O firmware mantém isso em duas formas:

| Local | Como é exposto | Use no ME2 |
|-------|----------------|-----------|
| `packagesHistory` (deque em memória, últimos 15) | `GET /dashboardData` campo `packagesHistory[]` ou `GET /history/lastPackages/:n` | Para snapshot quase real-time. |
| `packageCounts.<recipeId>` (mapa em memória) | `GET /dashboardData` campo `packageCounts` | Para contagens já agregadas (dia/hora/3min/30min). |
| Histórico persistido | `GET /history/packages/:startTime/:endTime` | Para reprocessamento e auditoria. |

**Estratégia recomendada para o coletor ME2:**

1. Pollar `GET /history/lastPackages/:n` a cada `dashboard_interval_s` (5 s default).
2. Manter `_last_seen_timestamp` por `equipment_id` (in-memory dict, mesmo padrão do `DataProcessor._last_parts_ok`).
3. Para cada pacote com `timestamp > _last_seen_timestamp`, gerar um `production_events` com:
   - `parts_ok = 1` (cada pacote = 1 peça boa)
   - `cycle_time_s = delta entre timestamps consecutivos`
   - `product_no = recipe.name` (de `GET /recipe/getActiveRecipe`)
   - `weight_g = pacote.weight` (campo novo em `production_events` ou em `process_events`)
4. Atualizar `_last_seen_timestamp`.

**Não** usar a contagem agregada (`countLastDay`) como fonte da verdade — ela pode resetar (`POST /system/clearPackageCountsAndHistory`), o que iria corromper a sequência no PostgreSQL.

### Mapeamento de status (`word_status`)

O MCBT não tem o `wWordStatus` do padrão GVL_ME2. O coletor precisa **derivar** a partir dos campos do `/dashboardData`:

| Condição no MCBT | `word_status` do ME2 | Estado |
|-------------------|---------------------|--------|
| `isRunning && !isInError && packageMachineStatus.state in [PACKAGING, REJECTING]` | `18` | Uptime |
| `isRunning && !isInError && packageMachineStatus.state == READY` mas sem produção há < timeout | `16` | Idle |
| `!isRunning && sanitizationMode` | `64` | Setup (higienização) |
| `paused` (via `POST /system/control { stop: true }`) | `17` | Planned Stop |
| `isInError` | `32` | Failure |
| `centralCone.status == DISABLED` ou ausência de feed | `20` | Starving |
| Selector Funnel preso/cheio (a definir como detectar) | `24` | Blocked |
| Erro Modbus/CAN no MCBT (sem comunicação com PLC interno) | `32` | Failure |
| HTTP request timeout do collector → MCBT | (sem evento — `connection_log`) | — |

A regra `word_status == 18 → producing` definida no CLAUDE.md continua valendo. Configure `alerts.uptime_status_code: 18` no equipment.json.

> **Detecção de Idle vs Uptime:** se `state == PACKAGING` ou `REJECTING`, é Uptime. Se `state == READY` há mais de N segundos sem novo pacote, é Idle. O firmware não emite isso diretamente — derive no coletor.

### Changeover (troca de receita)

O MCBT **não emite evento** de troca de receita. O coletor deve detectar via diff:

1. Pollar `GET /recipe/getActiveRecipe` a cada `dashboard_interval_s`.
2. Comparar `id` com o anterior em memória.
3. Se mudou → emitir um `process_events` com `variable_name = "recipe_change"`, `value = {from, to, name}`. Opcionalmente registrar como Setup (`word_status = 64`) por X minutos.

### Quality (refugo/retrabalho)

O MCBT não distingue pacote "ok" de "rejeitado" no `packagesHistory` retornado (pelo menos não nos campos visíveis). Investigar:
- O `packageMachineStatus.state == REJECTING` indica que o ciclo atual é uma rejeição.
- Considerar abrir issue no firmware para que cada `PackageRecord` carregue um campo `rejected: bool` ou `reason`.

Por ora, `quality = 1.0` como default (CLAUDE.md já prevê isso).

### Operating hours / total cycles

`GET /operationalData` retorna `operatingHours`, `totalCycles`, `lastMaintenanceHours`. Útil para:
- Trigger de alerta de manutenção preventiva no ME2 (`alerts` com `level = "maintenance"`).
- KPI no dashboard de "horas até próxima manutenção".

Pollar a cada `operational_interval_s` (5 min é suficiente).

---

## 5. Endpoints do MCBT que o ME2 consome

Resumo das rotas relevantes para o MES. Todas em `http://<host>:8080`.

| Endpoint | Método | Auth | Frequência | Para que serve no ME2 |
|----------|--------|------|------------|----------------------|
| `/usr/login` | POST | — | 1× ao iniciar / on 401 | Obter JWT (válido até expirar; renovar on 401). |
| `/dashboardData` | GET | público | 5 s | Snapshot completo: estado, módulos, system info, contagens agregadas. |
| `/history/lastPackages/:n` | GET | público | 5 s (n=20) | Stream de pacotes para gerar `production_events`. |
| `/history/packages/:start/:end` | GET | público | sob demanda (backfill) | Recuperar histórico após reconexão. |
| `/recipe/getActiveRecipe` | GET | público | 5 s | Detectar changeover; popular `product_no`. |
| `/operationalData` | GET | público | 5 min | KPIs de manutenção, horímetro. |
| `/errors` | GET | público | 30 s | Pull de erros (⚠️ **limpa o buffer**, ver §8). |
| `/logs?offset=&limit=` | GET | público | sob demanda | Audit/debug, expor em tela "Logs do equipamento". |
| `/getDeviceIPAndVersion` | GET | público | 5 min | Validar `firmware_version_expected`, alertar se mudou. |
| `/parameters` | GET | público | 1 h | Snapshot de config (incluir em report de equipamento). |

**Endpoints que o ME2 NÃO deve chamar** (somente UI local do MCBT ou Meitech support):

- `POST /system/shutdown`, `POST /writeReg/*`, `POST /writeBit/*`, `POST /system/terminal`, qualquer CRUD de `/recipe`, `/parameters`, `/usr`, `/hbm`, `/upperMotor`, etc. — mexer aí pode parar a máquina.

### WebSocket (opcional, mas recomendado para Live Monitor)

Conectar em `ws://<host>:9000/` com subprotocol `mcbt-protocol`. Recebe broadcast a cada **50 ms** com o mesmo payload do `GET /dashboardData`.

**Não use o WS para gerar `production_events`** — a 20 Hz vai inundar o buffer SQLite e o WebSocket interno do ME2 (`/ws/live`). Use HTTP polling para persistência e WS apenas para repassar live data ao dashboard, com **throttle de 1 Hz** no `useWebSocket.js` do React.

> **Cuidado:** o MCBT tem reconexão simples e nenhum heartbeat custom. Implementar reconnect com backoff (já presente em `useWebSocket.js`) e tratamento de mensagens parciais.

---

## 6. Driver `HttpDriver` no coletor ME2

Hoje o coletor tem `Snap7Driver`, `ModbusDriver`, `OpcUaDriver` (ver `api/collector/drivers/`). Adicionar um quarto:

```
api/collector/drivers/
├── base.py             # BaseDriver ABC (não muda)
├── snap7_driver.py
├── modbus_driver.py
├── opcua_driver.py
├── http_driver.py      # ← NOVO
└── factory.py          # registrar "http" → HttpDriver
```

### Responsabilidades do `HttpDriver`

1. **Login** — `POST /usr/login` na conexão e on 401, salva token, injeta header `Authorization: Bearer <token>` em chamadas subsequentes (apenas onde for necessário; a maioria dos GETs do MCBT é pública).
2. **Polling loop** — três tickers concorrentes (asyncio):
   - 5 s: `dashboardData` + `lastPackages/20` + `getActiveRecipe`
   - 30 s: `errors`
   - 5 min: `operationalData`, `getDeviceIPAndVersion`
3. **Mapeamento → eventos do ME2** (descrito em §4).
4. **Buffer offline** — se HTTP falhar, mesma estratégia que os outros drivers: tentar reconectar com backoff exponencial, registrar `connection_log`. Quando voltar, fazer **backfill** via `GET /history/packages/:start/:end` desde o último timestamp persistido.
5. **Não fazer write** — `HttpDriver.write()` raise `NotImplementedError`. Operação do MCBT continua sendo feita pela UI local da máquina, não pelo MES.

### Interface BaseDriver

Manter compatível com `BaseDriver`:

```python
class HttpDriver(BaseDriver):
    async def connect(self) -> None: ...      # login + health check
    async def disconnect(self) -> None: ...   # logout (opcional, MCBT não tem)
    async def read_all(self) -> dict: ...     # mapeia /dashboardData → dict ME2-style
    async def is_connected(self) -> bool: ...
```

O `read_all()` deve retornar o mesmo shape que os outros drivers retornam (campos `parts_ok`, `word_status`, `cycle_time_s`, `product_no`, `serial_number`), para o `DataProcessor` continuar agnóstico de protocolo.

---

## 7. Schema do PostgreSQL — o que muda?

**Nada na estrutura central.** O ME2 já tem `production_events`, `status_events`, `process_events`, `connection_log`, `alerts`, `oee_snapshots`. O `HttpDriver` apenas alimenta as mesmas tabelas.

**Sugestões de adições (opcionais)**:

| Tabela | Coluna nova | Para que |
|--------|-------------|---------|
| `production_events` | `weight_g INT NULL` | Peso do pacote (MCBT-specific, mas útil para outras pesadoras). |
| `me2_equipment` | `firmware_version TEXT NULL` | Bater com `getDeviceIPAndVersion.programVersion`, alertar drift. |
| `me2_equipment` | `mcbt_module_count INT NULL` | Refletir `parameters.moduleQuantity`. |

Migração via Alembic, padrão (CLAUDE.md, seção Commands).

---

## 8. Considerações importantes

### 8.1 `GET /errors` é destrutivo

A rota **limpa o buffer ao retornar**. Isso significa:
- Apenas **uma instância** do coletor ME2 deve consumir `/errors` por máquina.
- Se outra ferramenta (UI local do MCBT, suporte) também ler, mensagens vão se perder.
- Considerar pedir ao time do firmware um modo "peek" (`GET /errors?clear=false`).

### 8.2 Timezone hardcoded UTC-3

O firmware usa UTC-3 internamente para timestamps (ver `dashboardAPI.hpp:213`). Isso bate com São Paulo, mas:
- ME2 deve sempre **converter para UTC** antes de inserir no PostgreSQL (`TIMESTAMPTZ`).
- Para clientes em outros fusos, isso vai falhar — alinhar com firmware antes de SaaS.

### 8.3 Senhas em plaintext no MCBT

`tb_user.password` é texto puro. O usuário `meitech` usado pelo coletor deve ter senha **forte e única por máquina**, vinda de variável de ambiente (`MCBT_PASSWORD_<serial>`), nunca commitada.

### 8.4 Histórico em memória

`packagesHistory` (deque com 15 itens) e `packageCountsMap` ficam em RAM. Se o MCBT crashar, pacotes não persistidos somem. A tabela `tb_package_history` recebe write periódico, mas o intervalo exato precisa ser confirmado em `MCBT.cpp`. Consequência: o backfill via `/history/packages` pode ter buracos. Em caso de divergência entre buffer ME2 e MCBT, **confiar no que o ME2 tem** (ele é a SOR para reporting).

### 8.5 Confiabilidade de rede

MCBT na fábrica vai estar atrás do roteador VPN Weidmüller (ver CLAUDE.md, seção Hardware Context). Mesma premissa que Modbus: latência alta, drops intermitentes. SQLite buffer + reconnect automático são obrigatórios — bom que o `HttpDriver` herde isso de `BaseDriver`.

### 8.6 Não confundir camadas Modbus

O MCBT internamente faz Modbus TCP com seu PLC interno (`192.168.1.251` por default em `tb_parameter.clp_ip`). **Esse Modbus não deve ser tocado pelo ME2.** O coletor ME2 fala com o app C++ do MCBT, que por sua vez fala com seu próprio PLC. Não tente conectar Modbus diretamente ao MCBT contornando a HTTP API — você vai disputar o canal com o firmware.

### 8.7 Endpoints CLP e Simulation

`POST /writeReg`, `POST /writeBit`, `POST /simulation/weight` existem mas **são para o operador da máquina ou para teste de fábrica**. Não usar do ME2.

---

## 9. Roteiro de implementação (sugestão de sprints)

| Sprint | Entrega |
|--------|---------|
| 1 | `HttpDriver` esqueleto + login + `GET /dashboardData` mapeando para `read_all()`. Equipamento aparece no Live Monitor como online/offline. |
| 2 | Polling `lastPackages` → `production_events`; mapping de `word_status` derivado. OEE começa a calcular. |
| 3 | Detecção de changeover (`/recipe/getActiveRecipe`) + `product_no` populado. |
| 4 | `/errors` + `/operationalData` → `alerts` e KPI de manutenção. Tela "Logs do equipamento" lendo `/logs`. |
| 5 | WebSocket `:9000` → repasse com throttle para `/ws/live` do ME2. Backfill via `/history/packages` em reconexão. |
| 6 | Migração Alembic adicionando `weight_g`, `firmware_version`. Validação ponta a ponta com 1 MCBT real via VPN. |

---

## 10. Pendências para alinhar com o time do firmware MCBT

Antes ou em paralelo à integração, abrir tickets/conversas:

1. **Serial number persistente** — adicionar campo no SQLite (`tb_machine_identity` com `serial_number`, `model`, `manufacturer`) e endpoint `GET /machine/identity`. Alinha com padrão GVL_ME2.
2. **Flag de rejeição em `PackageRecord`** — atualmente impossível distinguir pacote bom de refugo no histórico. Adicionar `rejected: bool` e `reject_reason: string`.
3. **`/errors?clear=false`** — modo não-destrutivo, ou um endpoint `/errors/stream` (SSE) que não precisa polling destrutivo.
4. **Códigos de erro padronizados** — hoje são strings livres em `ExceptionsManager`. Definir enum (`MODBUS_TIMEOUT`, `CAN_BUS_OFF`, `HBM_OVERWEIGHT`, etc.) que vire campo `code` no JSON.
5. **Hash de senhas** — bcrypt em `tb_user.password` antes de qualquer cliente real.
6. **Timezone configurável** — remover hardcode UTC-3.
7. **Heartbeat WebSocket** — ping/pong custom para detectar zombies.
8. **Endpoint de health** — `GET /health` retornando `{ uptime, db_ok, modbus_ok, can_ok }` para o coletor monitorar saúde sem precisar parsear `dashboardData`.

---

## Apêndice A — Mapeamento rápido de campos

`/dashboardData` → modelo ME2:

| MCBT (JSON) | ME2 | Observação |
|-------------|-----|------------|
| `machineType` | — | Sempre `"MCBT"`. Use só para validar tipo. |
| `version` | `me2_equipment.firmware_version` | Comparar com `firmware_version_expected`. |
| `isRunning` | parte de `word_status` | Ver tabela §4. |
| `isInError` | parte de `word_status` | Idem. |
| `packageMachineStatus.state` | parte de `word_status` | Idem. |
| `packageMachineStatus.notReadyTimeSeconds` | downtime timer (cross-check) | Pode ajudar a calibrar `_downtime_start` do AlertEngine. |
| `centralCone.weight`, `modules.<id>.weight` | `process_events` (variable_name = `central_cone_weight`, `module_<id>_weight`) | Útil para troubleshooting; não obrigatório. |
| `packageCounts.<recipeId>.countLastHour` | KPI cross-check | Não usar como fonte; comparar com soma do ME2 para detectar drift. |
| `packagesHistory[].weight` | `production_events.weight_g` (campo novo) | Por pacote. |
| `packagesHistory[].timestamp` | `production_events.ts` | Converter para UTC. |
| `systemInfo.cpuTemp`, `cpuUsage` | `process_events` | Para futuro alerting de hardware. |

---

**Fim do documento.** Mantenha sincronizado com o firmware: ao atualizar o MCBT, revisar §5 e §8 para mudanças de contrato.
