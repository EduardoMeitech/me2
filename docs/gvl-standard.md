# GVL_ME2 Standard

> Standard for the automation team (Gabriel, Paulo, Thalis).
> Every machine connected to ME2 must implement `GVL_ME2` and `FB_ME2Status`.

---

## 1. Purpose

`GVL_ME2` is a Global Variable List that the ME2 collector reads from every PLC. It provides a **uniform interface** regardless of the machine's own program logic. The collector never touches the machine's internal variables — it only reads from `GVL_ME2`.

`FB_ME2Status` is a function block that calculates `wWordStatus` from the individual status booleans. It runs every PLC scan cycle.

---

## 2. Variable List

| Variable | IEC Type | Size | Description |
|----------|----------|------|-------------|
| `sSerialNumber` | `STRING(20)` | 20 chars | Machine serial number from the physical plate (e.g., `MEI-2024-0042`). Written once at startup or first run. |
| `sProductNo` | `STRING(20)` | 20 chars | Current product code. Updated on changeover by the machine program. |
| `dwPartsOK` | `DWORD` | 4 bytes | Good parts counter. Cumulative within the shift. Reset to 0 at shift boundary by the machine program or manually. |
| `rCycleTime` | `REAL` | 4 bytes | Last completed cycle time in seconds (e.g., `2.45`). Updated at the end of each production cycle. |
| `wWordStatus` | `WORD` | 2 bytes | Machine state code calculated by `FB_ME2Status`. See encoding table below. |
| `bProcess_01` | `BOOL` | 1 bit | Application-specific process variable 1 (defined per machine). |
| `bProcess_02` | `BOOL` | 1 bit | Application-specific process variable 2. |
| `bProcess_03` | `BOOL` | 1 bit | Application-specific process variable 3. |
| `bProcess_04` | `BOOL` | 1 bit | Application-specific process variable 4. |
| `bProcess_05` | `BOOL` | 1 bit | Application-specific process variable 5. |
| `bProcess_06` | `BOOL` | 1 bit | Application-specific process variable 6. |
| `bProcess_07` | `BOOL` | 1 bit | Application-specific process variable 7. |
| `bProcess_08` | `BOOL` | 1 bit | Application-specific process variable 8. |

### Notes

- `sSerialNumber` must match the `serial_number` in `config/equipment.json`. This is how the collector identifies which machine it is talking to.
- `dwPartsOK` is a DWORD (unsigned 32-bit) in the PLC, but on Schneider M-series it may be mapped to a signed 16-bit Modbus register. The collector handles overflow correction automatically — see Section 6.
- `bProcess_01..08` are free-use variables. Each machine defines their meaning (e.g., bProcess_01 = "Clamp closed", bProcess_02 = "Water pump on"). Document the mapping in the machine's commissioning sheet.

---

## 3. FB_ME2Status — Function Block

### Purpose

`FB_ME2Status` reads 7 individual status booleans from the machine program and calculates the `wWordStatus` code using bitwise encoding. This ensures a single, consistent state value that the collector can read in one register.

### Input Variables

| Input | IEC Type | Bit Weight | Description |
|-------|----------|------------|-------------|
| `bAlarm` | `BOOL` | 1 | Any active alarm (fault, interlock) |
| `bRunning` | `BOOL` | 2 | Machine is actively producing (cycle in progress) |
| `bStopped` | `BOOL` | 4 | Machine is deliberately stopped (not alarm) |
| `bStarving` | `BOOL` | 8 | Waiting for material from upstream |
| `bReady` | `BOOL` | 16 | Machine is ready / enabled / automatic mode |
| `bBlocked` | `BOOL` | 32 | Cannot output — downstream buffer full |
| `bSetup` | `BOOL` | 64 | Changeover / setup in progress |

### Output

| Output | IEC Type | Description |
|--------|----------|-------------|
| `wStatus` | `WORD` | Calculated status code — assign to `GVL_ME2.wWordStatus` |

### Calculation Logic (Structured Text)

```iecst
FUNCTION_BLOCK FB_ME2Status
VAR_INPUT
    bAlarm    : BOOL;
    bRunning  : BOOL;
    bStopped  : BOOL;
    bStarving : BOOL;
    bReady    : BOOL;
    bBlocked  : BOOL;
    bSetup    : BOOL;
END_VAR
VAR_OUTPUT
    wStatus   : WORD;
END_VAR

// Priority-based encoding — highest priority wins
IF bAlarm AND bStopped THEN
    wStatus := 128;    // Emergency stop (alarm + stopped)
ELSIF bAlarm THEN
    wStatus := 32;     // Failure
ELSIF bSetup THEN
    wStatus := 64;     // Setup / changeover
ELSIF bBlocked AND bReady THEN
    wStatus := 24;     // Blocked (ready but downstream full)
ELSIF bStarving AND bReady THEN
    wStatus := 20;     // Starving (ready but no material)
ELSIF bRunning AND bReady THEN
    wStatus := 18;     // Uptime (running + ready = producing)
ELSIF bRunning AND NOT bReady THEN
    wStatus := 19;     // Uptime variant (running but not in auto — manual jog)
ELSIF bReady AND NOT bRunning THEN
    wStatus := 16;     // Idle (ready but not producing)
ELSIF bStopped THEN
    wStatus := 17;     // Planned stop (scheduled break)
ELSE
    wStatus := 0;      // Unknown / initializing
END_IF;
```

---

## 4. WordStatus Encoding Table

| Code | State | Bits Active | Color (Dashboard) | ME2 Interpretation |
|------|-------|-------------|-------------------|--------------------|
| **0** | Unknown | none | Gray | Initializing or communication lost |
| **16** | Idle | bReady | Yellow `#F9A825` | Machine ready, not producing. Downtime timer runs. |
| **17** | Planned Stop | bStopped | Gray | Scheduled break or planned maintenance. May exclude from availability depending on config. |
| **18** | **Uptime** | bRunning + bReady | **Green `#388E3C`** | **Machine producing.** This is the target state. Downtime timer stops. |
| **19** | Uptime (manual) | bRunning | Green (light) | Running but not in automatic mode. Some machines count this as uptime — configurable via `uptime_variants` in equipment.json. |
| **20** | Starving | bStarving + bReady | Teal `#00897B` | Waiting for material from upstream process. |
| **24** | Blocked | bBlocked + bReady | Orange `#E65100` | Downstream full, machine cannot output. |
| **32** | Failure | bAlarm | Red `#D32F2F` | Alarm active. Requires operator intervention. |
| **64** | Setup | bSetup | Blue `#0066CC` | Changeover in progress. |
| **128** | Emergency | bAlarm + bStopped | Dark Red `#7B0000` | Emergency stop activated. |

### Rules for the Collector

- `word_status == 18` (or value in `uptime_variants`) means the machine is producing. **All other values start the downtime timer.**
- The L1 alert fires after `downtime_l1_min` minutes of continuous downtime.
- The L2 alert fires after `downtime_l2_min` minutes of continuous downtime.
- Alert resets automatically when `word_status` returns to an uptime value.

---

## 5. Implementation: Schneider (Modbus TCP)

### Memory Layout

On Schneider M221/M241/M251/M340, GVL variables are mapped to Modbus holding registers (`%MW`). The automation engineer assigns the base addresses in the PLC program and records them in `config/equipment.json`.

**Standard address convention (recommended):**

| Variable | Register Start | Count | Modbus Type |
|----------|---------------|-------|-------------|
| `sSerialNumber` | `%MW100` | 10 | Holding registers (2 ASCII chars per register) |
| `sProductNo` | `%MW110` | 10 | Holding registers (2 ASCII chars per register) |
| `wWordStatus` | `%MW200` | 1 | Holding register (UINT16) |
| `dwPartsOK` | `%MW202` | 1 | Holding register (UINT16, see overflow note) |
| `rCycleTime` | `%MW204` | 2 | Holding registers (REAL = IEEE 754 float, big-endian) |
| `bProcess_01..08` | `%MW300` | 1 | Holding register (packed bits, bit 0 = Process_01) |

### String Encoding

Each Modbus holding register holds 2 ASCII characters:

```
Register %MW100 = 0x4D45 → 'M' (0x4D) + 'E' (0x45)
Register %MW101 = 0x492D → 'I' (0x49) + '-' (0x2D)
Register %MW102 = 0x3230 → '2' (0x32) + '0' (0x30)
...
```

The collector reads 10 registers (20 chars), decodes as big-endian ASCII, and strips trailing nulls/spaces.

### Float Encoding

`rCycleTime` (REAL) occupies 2 consecutive holding registers in IEEE 754 big-endian format:

```python
import struct
raw = client.read_holding_registers(204, 2)
cycle_time = struct.unpack('>f', struct.pack('>HH', raw[0], raw[1]))[0]
```

### DWORD / Overflow

On M-series PLCs, `dwPartsOK` is a DWORD in the PLC program but may map to a single signed 16-bit Modbus register. When the value exceeds 32767, it wraps to a negative number. The collector corrects this:

```python
if parts_ok < 0:
    parts_ok = parts_ok + 32768
```

This is configured per-variable with `"overflow_fix": true` in equipment.json.

**Important:** If your PLC supports 32-bit Modbus registers (e.g., M340, M580), map `dwPartsOK` to 2 registers as UINT32 and set `overflow_fix: false`. Update the `count` to 2 and `type` to `uint32` in equipment.json.

---

## 6. Implementation: Siemens (S7comm / Snap7)

### Memory Layout

On Siemens S7-300/400/1200/1500, GVL variables are placed in a Data Block (DB). The standard is **DB100** for GVL_ME2.

**Important:** On S7-1200/1500, the DB must have **"Optimized block access" disabled** (use standard/absolute addressing). Otherwise Snap7 cannot read by offset.

**Standard DB100 layout:**

| Variable | DB | Offset | Size | S7 Type |
|----------|----|--------|------|---------|
| `sSerialNumber` | DB100 | 0.0 | 22 bytes | STRING[20] (2-byte header + 20 chars) |
| `sProductNo` | DB100 | 22.0 | 22 bytes | STRING[20] |
| `wWordStatus` | DB100 | 44.0 | 2 bytes | WORD |
| `dwPartsOK` | DB100 | 46.0 | 4 bytes | DWORD |
| `rCycleTime` | DB100 | 50.0 | 4 bytes | REAL |
| `bProcess_01` | DB100 | 54.0 | bit 0 | BOOL |
| `bProcess_02` | DB100 | 54.1 | bit 1 | BOOL |
| `bProcess_03` | DB100 | 54.2 | bit 2 | BOOL |
| `bProcess_04` | DB100 | 54.3 | bit 3 | BOOL |
| `bProcess_05` | DB100 | 54.4 | bit 4 | BOOL |
| `bProcess_06` | DB100 | 54.5 | bit 5 | BOOL |
| `bProcess_07` | DB100 | 54.6 | bit 6 | BOOL |
| `bProcess_08` | DB100 | 54.7 | bit 7 | BOOL |

### String Encoding

Siemens STRING[20] has a 2-byte header: byte 0 = max length (20), byte 1 = actual length. The string content starts at byte 2. The Snap7 driver reads all 22 bytes and extracts characters from bytes 2 through (2 + actual_length - 1).

```python
import snap7
data = client.db_read(100, 0, 22)
max_len = data[0]
actual_len = data[1]
serial = data[2:2+actual_len].decode('ascii')
```

### Connection Parameters

| Parameter | S7-300/400 | S7-1200/1500 |
|-----------|-----------|--------------|
| Port | 102 | 102 |
| Rack | 0 | 0 |
| Slot | 2 (300) / 0 (400) | 1 |

Configure `rack` and `slot` in `config/equipment.json` under `connection`.

### S7-1200/1500: Access Permissions

To allow Snap7 to read DB100:

1. In TIA Portal, open the DB properties.
2. Uncheck **"Optimized block access"** (use absolute addressing).
3. Under CPU properties > Protection & Security > Connection mechanisms, enable **"Permit access with PUT/GET communication"**.

---

## 7. Implementation: OPC-UA (Future — Toradex/CODESYS + M580)

### NodeID Convention

For CODESYS-based PLCs, variables are accessed via OPC-UA with the following NodeID pattern:

```
ns=4;s=Application.GVL_ME2.sSerialNumber
ns=4;s=Application.GVL_ME2.sProductNo
ns=4;s=Application.GVL_ME2.dwPartsOK
ns=4;s=Application.GVL_ME2.rCycleTime
ns=4;s=Application.GVL_ME2.wWordStatus
ns=4;s=Application.GVL_ME2.bProcess_01
```

Port: 4840 (default OPC-UA).

This is out of scope for the POC but the collector's `OpcUaDriver` is already stubbed for it.

---

## 8. Commissioning Checklist

When connecting a new machine to ME2, the automation engineer must:

1. [ ] Implement `GVL_ME2` with all variables from Section 2.
2. [ ] Implement `FB_ME2Status` and call it every scan cycle.
3. [ ] Assign the output `wStatus` to `GVL_ME2.wWordStatus`.
4. [ ] Write the machine's serial number to `GVL_ME2.sSerialNumber` at startup.
5. [ ] Map `GVL_ME2` to Modbus registers (Schneider) or DB100 (Siemens).
6. [ ] Record the register/offset addresses in `config/equipment.json`.
7. [ ] Verify with ModRSsim2 (Modbus) or Snap7 client test (Siemens) that all variables are readable.
8. [ ] Document `bProcess_01..08` meanings in the machine's commissioning sheet.
9. [ ] Test the full chain: PLC change → collector detects → API stores → dashboard shows.
10. [ ] Confirm alert L1 fires after the configured downtime threshold.
