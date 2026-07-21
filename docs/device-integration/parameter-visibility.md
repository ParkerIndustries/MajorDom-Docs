# Parameter Visibility & UX Recipe

Every parameter your controller exposes lands somewhere in the MajorDom apps. Getting that
placement right is what makes a device feel like a product instead of a protocol dump. This page
is the **recipe**: how to decide where each parameter goes, and how to encode that in your
integration's specs.

The hard part is *knowledge*, not code — whether an attribute is an everyday control, a diagnostic,
or a scaling constant **cannot be inferred from the protocol**. So you curate it, per cluster, in
your spec tables. This page tells you how.

## The four buckets

The apps surface parameters at four depths. Two SDK fields drive it: `Device.main_parameter`
(one UUID) and `Parameter.visibility` (`user` / `setting` / `system`).

| Bucket | Where it shows | Driven by |
|---|---|---|
| **main** | The one-tap action on the room/control-center tile (usually a toggle) | `device.main_parameter` → a parameter that satisfies `can_be_main_parameter` |
| **user** | The device screen when you tap the device — the everyday controls & live readings | `visibility = user` |
| **settings** | Behind an extra "Settings / Advanced" tap — configured once, rarely touched | `visibility = setting` |
| **system** | Hidden one layer deeper — internal wiring, not shown by default | `visibility = system` |

Goal: **the `user` list is short and everyday.** If a device's `user` bucket has 20+ entries,
it's over-exposed — that's a bug, not a feature. See [Validation](#validation).

## The classification recipe

For each attribute/command, decide the bucket in this order (first match wins):

1. **On a system/infrastructure cluster?** (Identify, Groups, OTA, Basic, diagnostics…) → **system**.
2. **Security material?** (keys, credentials, PIN/RFID tables, Matter `Aliro*`) → **system**, always.
3. **Metadata?** (scaling constants `*_divisor`/`*_multiplier`, bounds `*_min`/`*_max`/`min_measured_value`, capabilities, counts, tolerances) → **system** — *and reuse its value as metadata for the real parameter* (see [Metadata priority](#metadata-priority)).
4. **Writable everyday control?** (on/off, brightness, thermostat setpoint, fan mode) → **user**.
5. **Writable, but occasional config?** (report interval, transition time, calibration) → **setting**.
6. **A live reading a person watches?** (temperature, level, lock state, battery %) → **user**.
7. **Everything else** (read-only internals, static descriptors) → **system**.

The two integration mappers implement exactly this. They **default the unknown case to `system`**
(hidden) and *promote* into `user` only from curated allowlists — so a new/uncurated attribute is
quietly hidden rather than flooding the screen. You surface it by adding it to a list below.

### Encoding it in the specs

Both `matter_spec.py` and `zigbee_spec.py` carry the curation as plain sets keyed by
`(cluster_id, attribute_id)`:

| Set | Effect |
|---|---|
| `USER_READINGS` | read-only attrs promoted to **user** (the live readings) |
| `EVERYDAY_CONTROL_ATTRIBUTES` | writable attrs promoted to **user** (+ forced `control` role) |
| `SENSITIVE_*` | never-user security material → **system** |
| `METADATA_ATTRIBUTES` / `is_metadata_attribute()` | scaling/bounds → **system** + metadata source |
| `CONFIG_HEAVY_CLUSTERS` (zigbee) | clusters where "reportable" is a poor user signal (e.g. DoorLock) |
| `MAIN_PARAMETER_BY_CLUSTER` | which command/attr is the one-tap `main_parameter`, in priority order |

Add an entry, re-run the audit (below), done. Prefer **explicit curation over heuristics** — the
name heuristics (`*_divisor`, `min_measured_value`, …) are a *fallback* for the long tail and for
quirks we haven't seen yet.

## Metadata priority

A parameter's `min_value` / `max_value` / `min_step` / `unit` / `valid_values` should come from the
**best available source**, in this order:

1. **The device's own limit attributes at runtime** — e.g. `LevelControl.MinLevel/MaxLevel`,
   `*.MinMeasuredValue/MaxMeasuredValue`, an ElectricalMeasurement `*_divisor`/`*_multiplier`. These
   are the ground truth for *this* device, so they win.
2. **Hardcoded spec tables** — `ATTRIBUTE_UNITS`, `ATTRIBUTE_MIN_STEPS`, `ATTRIBUTE_SCALE`, valid
   value enums. Curated from the ZCL / Matter data model.
3. **Type-/heuristic-driven defaults** — the wire type's numeric range, enum members, etc.

Those step-1 attributes are exactly the ones the recipe sends to **system** — so they don't clutter
the UI, but their *values* still power the real parameter's bounds. When a metadata field you'd
expect (a unit for a measurement, a range for a level) is missing from all three sources, **log a
warning** — that's how you detect a new quirk or a device that ships a nonstandard attribute.

## Users can override

Treat every mapping as a **default, not gospel**. Devices lie, quirks exist, and people have
preferences. `Parameter.visibility` is patchable (`ParameterVisibilityPatch`), and metadata
(unit / bounds / step / whether it's the main parameter) should remain user-tunable. Curate for the
best out-of-the-box result; never assume it's perfect.

## Validation

Run the per-cluster audit while curating — it runs the *actual* mapping over the full protocol
surface (Zigbee: every zigpy ZCL cluster; Matter: the whole chip data model) and buckets the
result the way the app would:

```sh
poetry run python scripts/param_ux_audit.py   # in integration-zigbee or integration-matter
```

Because zigpy and chip are enumerable in-process, this is the exhaustive analog of Matter's MVD
device sweep — no hardware, no binaries. Wire it into CI as a snapshot test so a new SDK/chip/zigpy
version that reshuffles a cluster shows up as a diff.

The SDK also ships dev-time warnings you can call after building a device's parameters:

- **too many `user` params** for one device (over-exposure smell),
- **near-duplicate names** in the `user` bucket (Levenshtein/ratio) *and* **same-unit-same-role**
  duplicates (catches redundant representations like Zigbee color `hue/sat` **and** `x/y`),
- **missing expected metadata** (unit/range) — a new-quirk signal.

These are advisory (dev/pairing-time), never fatal — a device with 12 genuine `user` controls is
fine; the warning just tells you to look.

## Per-cluster examples

| Device | main | user | settings | system |
|---|---|---|---|---|
| Dimmable light | On/Off toggle | on/off, brightness, color | transitions, startup behaviour | capabilities, min/max level |
| Thermostat | setpoint nudge | local temperature, heating/cooling setpoint, mode | calibration, schedule config | abs limits, transition counts |
| Door lock | Unlock | lock state, door state, battery | auto-relock, one-touch, sounds | credential counts, keys (never user) |
| Temp sensor | — | measured value | — | min/max/tolerance (→ bounds metadata) |
| Fan | Fan mode | fan mode, percent/speed | — | supported-features flags |

See also: [Implementing a Controller](controller.md), [Data Models](data_models.md).
