## MajorDom Device Integration Guide

An **integration** is a module that bridges MajorDom Hub with IoT devices of a specific protocol or vendor (e.g. HomeKit, Zigbee, Z-Wave).

---

### Concepts

| Term | Meaning |
|---|---|
| **Hub** | The MajorDom Hub core software |
| **Integration** | A protocol/vendor-specific plugin |
| **Controller** (capitalized) | The class your integration must implement (`AbstractController` subclass) |
| **a controller** (lowercase) | Any third-party device that can control IoT devices (smartphone, Alexa, etc.) |
| **Discovery** | A detected, unpaired device that is available to be paired |
| **Device** | A paired and controllable device saved in the Hub's database |
| **Parameter** | A single controllable or observable property of a device (e.g. brightness, temperature) |

A device moves through these states:

```
Invisible → Discoverable (Discovery) → Paired (Device)
```

---

### Suggested Module Structure

An integration will typically need more than just a controller. Recommended minimal layout:

```
services/controller/myintegration/
├── controller.py        # AbstractController subclass — the only required file
├── models.py            # Typed integration_data schemas for Device and Parameter subclasses, see Storing Data
├── mapper.py            # Protocol ↔ MajorDom domain model conversions, isolated from the controller for readability
└── parameters_map.py    # Supplemental metadata for parameters that the API does not expose, usually in a form of a static dictionary. For example, device might expose min/max limits for a number via device's API, but the unit is only defined in pdf specification.
```

**`controller.py`** is the only required file. The rest are a template for keeping the controller clean — separate models, pull out conversion logic into a mapper, add metadata dictionary, etc. Of course, other files can be added as needed.

---

### Implementation Checklist

- [ ] Discovery of new devices (`self.dependencies.output.controller_did_receive_discovery` is called)
- [ ] Discovery of devices already paired to the Hub on reconnect, e.g. after a reboot (`self.dependencies.output.controller_did_connect_device` is called)
- [ ] `start_pairing_window` is implemented if the protocol requires an explicit scan mode
- [ ] Device pairing (`pair_device` is implemented)
- [ ] Device schema is properly mapped: device info, parameter list, and each parameter's metadata are translated to MajorDom's domain model
- [ ] Hub → Device control (`send_command` is implemented)
- [ ] Device → Hub event subscription (`self.dependencies.output.controller_did_receive_device_events` is called on incoming events)
- [ ] `identify`, `unpair`, and `fetch` are implemented
- [ ] Graceful shutdown in `stop`

---

### Implementing a Controller

Create a directory under `services/controller/` for your integration and subclass [`AbstractController`](https://github.com/ParkerIndustries/MajorDom-Hub/tree/develop/majordom_hub/services/controller/framework/abstract_controller.py).

#### Hub → Device

Implement all abstract methods defined in [`AbstractController`](https://github.com/ParkerIndustries/MajorDom-Hub/tree/develop/majordom_hub/services/controller/framework/abstract_controller.py). The Hub calls these to drive your integration.

#### Device → Hub

Use `self.dependencies.output` ([`ControllerOutput`](https://github.com/ParkerIndustries/MajorDom-Hub/tree/develop/majordom_hub/services/controller/framework/abstract_controller.py)), injected by the Hub:

```python
# New unpaired device found during discovery
await self.dependencies.output.controller_did_receive_discovery(self, discovery)

# Device successfully paired and connected (also call on reconnect after reboot)
await self.dependencies.output.controller_did_connect_device(self, device_id)

# Device reported new parameter values
await self.dependencies.output.controller_did_receive_device_events(self, events)
```

#### The `discoveries` property

Return your current in-memory cache of unpaired, visible devices. The Hub polls this — do not trigger scanning here.

```python
@property
def discoveries(self) -> dict[UUID, Discovery]:
    return self._discoveries  # maintained elsewhere, e.g. in a discovery event callback
```

The `UUID` for a given physical device must remain stable as long as it is visible.

#### `start_pairing_window(duration_sec)`

Optional. Override only if your protocol requires an explicit short-lived scan mode to surface new devices (e.g. Zigbee permit-join, BLE burst scan). Always-on discovery (mDNS, SSDP) does not need this. Default is a no-op.

---

### Injected Dependencies

The Hub populates `self.dependencies` (see [`AbstractController.Dependencies`](https://github.com/ParkerIndustries/MajorDom-Hub/tree/develop/majordom_hub/services/controller/framework/abstract_controller.py)) before calling `start()`.

| Field | Type | Description |
|---|---|---|
| `output` | `ControllerOutput` | Callback object for pushing events to the Hub |
| `make_device_repository` | `Callable[[], AsyncContextManager[DeviceRepository]]` | Factory for the device repository |
| `zeroconf` | `AsyncZeroconf` | Shared zeroconf instance for mDNS discovery |
| `register_zeroconf` | `Callable[[set[str]], None]` | Register mDNS service types to listen for |
| `hardware_interfaces` | `list[str]` | OS-level hardware interface paths assigned to this integration (e.g. `/dev/ttyACM0`) |

---

### Storing Data

#### File Storage (`documents_folder`)

For files that cannot be stored in the database (e.g. a protocol's own SQLite DB, certificates, binary blobs), use `self.documents_folder`:

```python
path = self.documents_folder / "zigbee.db"
```

Resolves to a dedicated directory for this integration under the Hub's data root, created automatically on first write.

#### integration_data

MajorDom's Device and Parameter schemas expose an `integration_data` field for storing protocol-specific state (pairing tokens, internal IDs, etc.). By default it is an untyped dict persisted as JSON. 

Integrations can subclass Device/DeviceState and Parameter/ParameterState to declare a typed schema for that field — Hub will then handle (de-)serialization automatically before passing Device instance to Controller's methods or when saving to the database.

```python
# myintegration/models.py
from majordom_hub.schemas.base import Base
from majordom_hub.schemas.device import Device, DeviceState
from majordom_hub.schemas.parameter import Parameter, ParameterState

class MyDeviceIntegrationData(Base):
    pairing_token: str | None = None

class MyDevice(Device):
    integration_data: MyDeviceIntegrationData

class MyParameterState(ParameterState):
    integration_data: MyParameterIntegrationData
```

To make the Hub use these custom types, the integration's Controller must override `device_type` and `parameter_type`:

```python
@property
def device_type(self) -> type[MyDevice]:
    return MyDevice

@property
def parameter_type(self) -> type[MyParameter]:
    return MyParameter
```

The Hub will deserialize objects into these types before passing them to your implemented methods.

#### Repository

Use `self.dependencies.make_device_repository` to read or persist devices:

```python
async with self.dependencies.make_device_repository() as repo:
    device = await repo.get(device_id, as_=MyDevice) # `as_=MyDevice` is optional but provides hassle-free deserialization

async with self.dependencies.make_device_repository() as repo:
    device.integration_data.some_field = new_value # assuming `MyDevice.integration_data` uses custom class with `some_field` present
    await repo.save(device)
```

---

### Notes

#### Helper Methods

`AbstractController` provides these `@final` helpers — do not override them:

| Method / Property | Description |
|---|---|
| `self.name_slug` | URL-safe slug of `self.name`; used as a stable integration identifier |
| `self.integration_uuid()` | Stable `UUID` for this integration, derived from `name_slug` |
| `self.device_uuid(device_id)` | Stable `UUID` for a device given any unique string (MAC, serial, etc.) |
| `self.parameter_uuid(device_uuid, parameter_id)` | Stable `UUID` for a parameter scoped to its device |
| `self.documents_folder` | `Path` to this integration's file storage directory |

#### IDs

Use the built-in helpers to generate deterministic UUIDs — no DB lookup needed, IDs stay consistent across restarts and re-pairings:

```python
device_id = self.device_uuid(device_mac_or_serial)
parameter_id = self.parameter_uuid(device_id, f'{accessory_id}.{characteristic_id}')
```

Discovery `id` isn't required to match Device `id`, but this is recommended.

#### For IP Devices

- **Handle IP changes.** DHCP can reassign addresses. Identify devices by a stable ID (MAC, serial, mDNS hostname, domain-provided id) rather than IP. Monitor ip address regularly and keep it up to date.
- **Use the Hub's provided discovery.** Register your mDNS service types via `self.dependencies.register_zeroconf`, or SSDP service via `self.dependencies.register_ssdp`. It is not recommended to spin up your own discovery stack.

---

### Data Models Reference

#### Pairing

```python
class CredentialsType(str, Enum):
    code = "code"      # pin, e.g. 123-45-678 (HomeKit) or 1234-123-1234 (Matter)
    secret = "secret"  # e.g. AES key like in ESPHome
    qr = "qr"          # raw QR data
    none = "none"

    def with_mask(self, code_mask: str) -> CredentialsType:
        """
        mask format: D as digit placeholder, other symbols like dashes remain unchanged,
        e.g. "DDD-DD-DDD" for "123-45-678"
        """
        self.code_mask = code_mask
        return self

type CredentialsValue = str

class Discovery(Base):
    # technical
    id: UUID
    integration: NonEmptyStr
    credentials: CredentialsType
    expiration: datetime | None = None
    # for UX
    transport: NonEmptyStr
    device_manufacturer: str | None
    device_name: NonEmptyStr
    device_category: str | None
    device_icon: str | None
```

#### Device

```python
class DeviceInfo(DevicePatch):
    id: UUID
    name: str
    note: str = ""
    icon: str | None = None
    category: str | None = None
    room_id: UUID
    transport: str
    integration: str
    manufacturer: str | None
    last_seen: datetime | None = None
    available: bool = False

class Device(DeviceInfo):
    integration_data: SerializeAsAny[dict | Base] = Field(default_factory=Base)

class DeviceState(DeviceInfo):
    parameters: list[ParameterState]
```

#### Parameter

```python
class ParameterDataType(StrEnum):
    none = "none"        # e.g. button
    bool = "bool"
    integer = "integer"
    decimal = "decimal"  # python float
    enum = "enum"        # integer with string representation
    string = "string"
    data = "data"        # binary data, base64 encoded at high level

class ParameterUnit(StrEnum):
    plain = "plain"
    percentage = "percentage"
    second = "second"
    hertz = "hertz"
    kilogram = "kilogram"
    arcdegree = "arcdegree"
    meters = "meters"
    mps = "mps"      # meters per second
    mps2 = "mps2"    # meters per second squared
    rpm = "rpm"
    newton = "newton"
    joule = "joule"
    watt = "watt"
    celsius = "celsius"
    kelvin = "kelvin"
    volt = "volt"
    ampere = "ampere"
    lux = "lux"
    pascal = "pascal"
    ppm = "ppm"      # parts per million, air quality
    bytes = "bytes"
    bps = "bps"      # bytes per second

class ParameterRole(StrEnum):
    sensor = 'sensor'   # read-only
    control = 'control' # read-write
    event = 'event'     # fire-and-forget

class Parameter(UUIdentifable):
    id: UUID
    name: str
    data_type: ParameterDataType
    unit: ParameterUnit = ParameterUnit.plain
    role: ParameterRole
    min_value: int | float | None = None
    max_value: int | float | None = None
    min_step: int | float | None = None
    valid_values: dict[int | float | str, str] | None = None  # value → display label
    integration_data: Any

class ParameterState(Parameter):
    value: bytes
```
