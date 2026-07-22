# Standalone Mode — Running an Integration Without the Hub

Every MajorDom integration is a self-contained library for its protocol. The Hub is just one
consumer: it constructs your `Controller`, injects dependencies, and drives it. You can do exactly
the same thing yourself — to script a device, embed an integration in another app, or test against
real hardware — with no Hub involved.

There are three ways to run one, all in `majordom_integration_sdk.dev`:

| | `run_cli(...)` | `run_controller(...)` | `build_dependencies(...)` |
|---|---|---|---|
| Use for | driving a device by hand from a prompt | watching devices, quick demos | programmatic pair / control / fetch |
| Discovery services | started for you (mDNS/SSDP/BLE, network-live) | started for you | assembled; you start them if you need them |
| Output | interactive commands + console log | logs discoveries/events to the console | **your delegate** (see below) |
| Blocks | interactive prompt until `exit` | runs until Ctrl-C | you drive the lifecycle |
| Extra deps | `majordom-integration-sdk[cli]` | none | none |

## Interactive CLI — `run_cli`

The fastest way to actually *use* an integration by hand: it starts the controller with live
discovery and a local device store, then drops you into a prompt to pair, control, and inspect
devices. It's the MajorDom Hub's operator CLI, scoped to a single integration.

The interactive CLI needs one extra (typer-shell + rich), so install the `cli` extra:

```sh
pip install "majordom-integration-sdk[cli]"
```

```python
# cli.py
import asyncio
from majordom_integration_sdk.dev import run_cli
from integration_template.controller import ExampleController  # your controller

asyncio.run(run_cli(ExampleController, db_path="devices.db"))
```

```sh
python cli.py
```

```text
example > help          # list commands
example > discoveries   # devices seen on the network (id, name, transport, expected credentials)
example > pair <discovery_id> [credentials_type] [credentials_value]
example > pair_window 60 # open a join window (Zigbee); no-op where discovery is continuous
example > devices        # paired devices (id, name, available)
example > device <id>    # its parameters (id, name, role, visibility, value)
example > control <device_id> <parameter_id> <value>   # value parsed as JSON if possible
example > identify <device_id>   # blink/beep
example > fetch <device_id>      # refresh state from the device
example > unpair <device_id>
example > exit
```

Pass `db_path=` to keep paired devices across restarts (a file-backed store); omit it for an
in-memory one. Under the hood this is exactly the wiring described below — the same
`build_dependencies` plus a delegate that persists state — so anything the CLI does you can also do
in code.

## Watch mode — `run_controller`

The quickest way to see an integration work. It wires real, network-live discovery services, a
file-backed device store, and a console logger, then runs your controller until interrupted:

```python
import asyncio
from majordom_integration_sdk.dev import run_controller
from integration_template.controller import ExampleController  # your controller

asyncio.run(run_controller(ExampleController, db_path="devices.db"))
```

## Programmatic mode — `build_dependencies` + call the controller

For anything beyond watching — pair a device, send a command, fetch state — build the dependencies
yourself and call the controller's methods directly:

```python
import asyncio
from majordom_integration_sdk.dev import build_dependencies
from majordom_integration_sdk.schemas.device import ProvidedCredentials
from integration_template.controller import ExampleController

async def main():
    deps = build_dependencies(integration=ExampleController.name, db_path="devices.db")
    controller = ExampleController(deps)
    await controller.start()
    # ... await controller.pair_device(discovery, ProvidedCredentials(...)), send_command, fetch ...
    await controller.stop()

asyncio.run(main())
```

## The dependency structure

`build_dependencies()` returns the same `AbstractController.Dependencies` the Hub injects. Its main
fields:

- **`output`** — the *delegate* the controller calls to report discoveries, connections, and events
  (a `ControllerOutput`). Defaults to a console logger; pass your own to actually receive them (next
  section).
- **`make_device_repository`** — an async-context factory for the device store. `db_path=` selects a
  file-backed SQLite repository (state survives restarts); omit it for an in-memory one. Scoped to
  your integration via `integration=`.
- **`documents_folder`** — a `Path` your controller may write files into (per-integration subtree).
- **discovery services** — `zeroconf_discovery_service`, `ssdp_discovery_service`,
  `ble_discovery_service`, if your protocol discovers over mDNS / SSDP / BLE.

```python
deps = build_dependencies(
    integration=ExampleController.name,
    db_path="devices.db",   # omit for in-memory
    output=MyDelegate(),    # see below
)
```

## Receiving discoveries & events — implement a delegate

The controller doesn't *return* discoveries and events; it **pushes** them to `deps.output`. To act
on them in standalone mode, pass an object implementing the `ControllerOutput` protocol. The
simplest path is to subclass the SDK's `LoggingControllerOutput` and override only what you need:

```python
import asyncio
from majordom_integration_sdk.dev import LoggingControllerOutput, build_dependencies
from majordom_integration_sdk.schemas.device import CredentialsType, ProvidedCredentials
from integration_template.controller import ExampleController

class MyDelegate(LoggingControllerOutput):
    def __init__(self):
        self.discoveries = {}

    async def controller_did_receive_discovery(self, controller, discovery):
        self.discoveries[discovery.id] = discovery

    async def controller_did_receive_events(self, controller, events):
        for event in events:
            print("event:", event)

async def main():
    delegate = MyDelegate()
    deps = build_dependencies(integration=ExampleController.name, db_path="devices.db", output=delegate)
    controller = ExampleController(deps)
    await controller.start()

    # wait for the first discovery, then pair it
    while not delegate.discoveries:
        await asyncio.sleep(0.2)
    discovery = next(iter(delegate.discoveries.values()))
    device_id = await controller.pair_device(
        discovery, ProvidedCredentials(type=CredentialsType.code, value="123-45-678")
    )

    # ... controller.send_command(...), controller.fetch(device), controller.identify(device) ...

    await controller.stop()

asyncio.run(main())
```

The full delegate surface — every method the controller may call:

| Method | Called when |
|---|---|
| `controller_did_receive_discovery(controller, discovery)` | a new device is discovered |
| `controller_did_update_discovery(controller, discovery)` | a known discovery's details change |
| `controller_did_lose_discovery(controller, discovery_id)` | a discovery is gone |
| `controller_did_connect_device(controller, device_id)` | a paired device comes online (incl. after pairing) |
| `controller_did_lose_device(controller, device_id)` | a paired device goes offline |
| `controller_did_receive_events(controller, events)` | the device reports parameter changes (`DeviceParameterChange`) |

Subclassing `LoggingControllerOutput` gives every method a logging default, so you only implement
the ones you care about.

## Testing without real devices

For tests, prefer the offline doubles in `majordom_integration_sdk.testing` —
`build_test_dependencies()` (in-memory, faked discovery services) plus `RecordingControllerOutput`
(captures discoveries/events for assertions) — over `build_dependencies` and real hardware. See
[Example Integration](example-integration.md#testing) and any integration's `tests/`.
