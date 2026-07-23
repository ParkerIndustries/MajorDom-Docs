# Parameter UX

Every parameter your controller exposes ends up somewhere in the MajorDom apps. This page shows
you how to decide **where each one goes** and **how it behaves** — so a device feels polished
instead of showing a wall of raw protocol fields.

In most cases the protocol alone can't make these calls for you. Whether a field is an everyday
control, a rare setting, or an internal constant is usually something *you* decide, per
parameter. The recipe below makes those decisions easy.

The fields themselves (`visibility`, `main_parameter`, `default_value`, bounds) are defined in
[Data Models](data_models.md); this page is about choosing good values for them.

## The four buckets

Two fields control placement: `Device.main_parameter` (one UUID) and `Parameter.visibility`
(`user` / `setting` / `system`).

| Bucket | Where the user sees it |
|---|---|
| **main** | The one-tap action on the room tile — usually a toggle. Set `device.main_parameter`. |
| **user** | The device screen (tap the device) — everyday controls and live readings. `visibility = user` |
| **settings** | Behind a "Settings" tap — set once, rarely touched. `visibility = setting` |
| **system** | Hidden — internal wiring. `visibility = system` |

Goal: **keep the `user` list short.** A light should show on/off, brightness, color — not 20
diagnostic fields. A device with 20+ `user` parameters is usually over-exposed — most of them
probably belong in `settings` or `system`. (A custom DIY device with genuinely many controls is
the rare exception.)

## How to pick a bucket

Go through your parameters one by one and take the **first** rule that matches:

1. **Infrastructure, not a device feature?** (pairing machinery, firmware update, diagnostics, group management) → **system**
2. **Security material?** (keys, credentials, PIN codes) → **system**, always.
3. **Metadata about another parameter?** (a min/max limit, a scaling factor, a capability flag) → **system** — but keep its *value*: use it as the real parameter's bounds (see [Where bounds come from](#where-bounds-come-from)).
4. **Something people change every day?** (on/off, brightness, target temperature, fan mode) → **user**
5. **Something people configure once?** (report interval, transition time, calibration) → **setting**
6. **A live reading people look at?** (temperature, lock state, battery %) → **user**
7. **Everything else** → **system**

One habit worth copying from the built-in integrations: **when in doubt, hide it.** Default
unknown parameters to `system` and *promote* to `user` only the ones you've deliberately chosen.
That way a new or odd parameter quietly stays hidden instead of cluttering the screen.

## The one-tap main parameter

`Device.main_parameter` is what happens when the user taps the device's room tile.
`Parameter.can_be_main_parameter` tells you which parameters qualify, and the tap behaves
differently depending on the parameter:

| Main parameter | Tap behaviour |
|---|---|
| `none` (an argument-less command like Toggle) | **button** — fires the command |
| `bool` | **toggle** — flips between on and off |
| `enum` with `valid_values` defined | **cycle** — each tap moves to the next value, wrapping around |
| `default_value` = one value | **button** — every tap sends that same value |
| `default_value` = a set of values | **cycle** through just those values — works for **any** data type |

So a main parameter isn't limited to "do the same thing every time": a bool toggles, an enum
steps through its states — and by setting `default_value` to a set of values you can add
cycling to *any* parameter. Most of the time that's a two-value toggle (0 and some preferred
value — e.g. brightness `{0, 80}` so a dimmer tile taps like an on/off switch), but the cycle
can be longer. The same trick narrows an enum's cycle to a subset (just `{off, on}` for a fan).
Set it with `with_default_value(...)` — it takes one value or a set, and always stores a set
(one value is a 1-element set); labels for the values come from `valid_values`.
You don't compute any of this in your integration: when a tap produces a value-less command,
**the Hub derives the value to send** (from the stored state, via `Parameter.main_cycle` +
`next_main_parameter_value`) and hands your `send_command` a concrete value. Only a `none`-type
command arrives value-less — you just fire it. If the device reports a value that isn't in the
cycle, the next tap sends the first one, so it always recovers to a sane state.

More on `main_parameter` and `default_value` at the model level: [Data
Models](data_models.md#main_parameter-and-default_value).

## Where bounds come from

A parameter's `min_value` / `max_value` / `unit` should come from the best source available,
in this order:

1. **The device itself** — many devices expose their own limit attributes (e.g. `MinLevel` /
   `MaxLevel`). Read those at runtime; they're the truth for *this* device.
2. **Your spec tables** — values you wrote down from the protocol spec.
3. **The wire type** — e.g. a uint8 is 0–255. Last resort.

The limit attributes in step 1 are the same ones rule 3 sent to `system` — hidden from the UI,
but their values still power the real parameter's bounds. If a unit or range you'd expect is
missing everywhere, **log a warning**: that's how you notice a quirky device.

## Users can override you

Treat your mapping as a good default, not the final word. `Parameter.visibility` is patchable
by the user (`ParameterVisibilityPatch`), and metadata should stay tunable too. Devices lie and
people have preferences — curate the best out-of-the-box experience, and let users adjust it.

## Check your work

The SDK ships advisory warnings you can run after building a device's parameters
(`majordom_integration_sdk.parameter_audit`). They flag:

- too many `user` parameters on one device (over-exposure),
- two `user` parameters with nearly the same name (one is probably redundant),
- missing expected metadata (unit/range) — a quirky-device signal.

They warn, never fail — many genuine controls can be fine; the warning just says "look at this."

If your protocol library lets you enumerate *every* possible parameter (zigpy and Matter's
`chip` both do), you can go further and audit the whole protocol at once — the Zigbee and
Matter integrations each ship `scripts/param_ux_audit.py` for that, wired into CI. For a small
or cloud-based protocol, just map your real test devices and eyeball the four buckets per
device.

See also: [Data Models](data_models.md), [Implementing a Controller](controller.md).
