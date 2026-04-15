# Data Models Reference

## Pairing

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

## Device

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
    main_parameter: UUID | None = None  # for the tap action on the room view, toggle in most cases

class Device(DeviceInfo):
    integration_data: SerializeAsAny[dict | Base] = Field(default_factory=Base)

class DeviceState(DeviceInfo):
    parameters: list[ParameterState]
```

## Parameter

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

class ParameterVisibility(StrEnum):
    user = "user"  # main, everyday interaction, device screen widgets (on/off, brightness, volume)
    setting = "setting"  # user-configurable, initial setup or low-frequency, like "auto off timer"
    system = "system"  # firmware, diagnostics, internals; not visible

class Parameter(UUIdentifable):
    id: UUID
    name: str
    data_type: ParameterDataType
    unit: ParameterUnit = ParameterUnit.plain
    role: ParameterRole
    visibility: ParameterVisibility
    min_value: int | float | None = None
    max_value: int | float | None = None
    min_step: int | float | None = None
    valid_values: dict[int | float | str, str] | None = None  # value → display label
    fields: list["Parameter"] | None = None  # schema for data_type=struct
    integration_data: Any

class ParameterState(Parameter):
    value: bytes
```
