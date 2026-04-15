# Implementing a Controller

## AbstractController Overview

Create a directory under `services/controller/` for your integration and subclass [`AbstractController`](https://github.com/ParkerIndustries/MajorDom-Hub/tree/develop/majordom_hub/services/controller/framework/abstract_controller.py).

### Hub → Device

Implement all abstract methods defined in [`AbstractController`](https://github.com/ParkerIndustries/MajorDom-Hub/tree/develop/majordom_hub/services/controller/framework/abstract_controller.py). The Hub calls these to drive your integration.

### Device → Hub

Use `self.dependencies.output` ([`ControllerOutput`](https://github.com/ParkerIndustries/MajorDom-Hub/tree/develop/majordom_hub/services/controller/framework/abstract_controller.py)), injected by the Hub:

```python
# New unpaired device found during discovery
await self.dependencies.output.controller_did_receive_discovery(self, discovery)

# An already-discovered (unpaired) device changed its advertisement
await self.dependencies.output.controller_did_update_discovery(self, discovery)

# A previously-discovered device is no longer visible
await self.dependencies.output.controller_did_lose_discovery(self, discovery_id)

# Device successfully paired and connected (also call on reconnect after reboot)
await self.dependencies.output.controller_did_connect_device(self, device_id)

# Device reported new parameter values or events
await self.dependencies.output.controller_did_receive_device_events(self, events)
```

### The `discoveries` property

Return your current in-memory cache of unpaired, visible devices. The Hub polls this — do not trigger scanning here.

```python
@property
def discoveries(self) -> dict[UUID, Discovery]:
    return self._discoveries  # maintained elsewhere, e.g. in a discovery event callback
```

The `UUID` for a given physical device must remain stable as long as it is visible.

### `start_pairing_window(duration_sec)`

Optional. Override only if your protocol requires an explicit short-lived scan mode to surface new devices (e.g. Zigbee permit-join, BLE burst scan). Always-on discovery (mDNS, SSDP) does not need this. Default is a no-op.

## Injected Dependencies

The Hub populates `self.dependencies` (see [`AbstractController.Dependencies`](https://github.com/ParkerIndustries/MajorDom-Hub/tree/develop/majordom_hub/services/controller/framework/abstract_controller.py)) before calling `start()`.

| Field | Type | Description |
|---|---|---|
| `output` | `ControllerOutput` | Callback object for pushing events to the Hub |
| `make_device_repository` | `Callable[[], AsyncContextManager[DeviceRepository]]` | Factory for the device repository |
| `zeroconf_discovery_service` | `ZeroconfDiscoveryService` | Shared mDNS/Zeroconf discovery service |
| `ssdp_discovery_service` | `SSDPDiscoveryService` | Shared SSDP discovery service |
| `ble_discovery_service` | `BLEDiscoveryService` | Shared BLE scanner service |
| `hardware_interfaces` | `list[str]` | OS-level hardware interface paths assigned to this integration (e.g. `/dev/ttyACM0`) |

## Helper Methods

`AbstractController` provides these `@final` helpers. Do not override them. 

```python
@property
def name_slug(self) -> str: ...
# URL-safe slug of self.name; stable integration identifier

def integration_uuid(self) -> UUID: ...
# Stable UUID for this integration, derived from name_slug

def device_uuid(self, device_id: str) -> UUID: ...
# Stable UUID for a device given any unique string (MAC, serial, etc.)

def parameter_uuid(self, device_uuid: UUID, parameter_id: str) -> UUID: ...
# Stable UUID for a parameter scoped to its device

@property
def documents_folder(self) -> Path: ...
# Path to this integration's dedicated file storage directory
```

For example

```python
path = self.documents_folder / "zigbee.db"
```

Use the built-in uuid generators to make deterministic UUIDs — no DB lookup needed, IDs stay consistent across restarts and re-pairings. Discovery `id` isn't required to match Device `id`, but this is recommended.

```python
device_id = self.device_uuid(device_mac)
param_id = self.parameter_uuid(device_id, f"{accessory_id}.{characteristic_id}")
```

## See Also

- [Storing Data](storing_data.md) — `integration_data`, typed schemas, file storage, and the device repository
- [Data Models Reference](data_models.md) — `Discovery`, `Device`, `Parameter`, and related types
