## MajorDom Device Integration Guide

### Overview

To integrate a device into MajorDom, you need to implement a subclass of `AbstractController` - which provides an essential standartized interface for MajorDom to interact with your device(s). To share runtime information with MajorDom, you should call respective methods of `self.dependencies.output` (defined as `ControllerOutput`).

### Storing Data

`self.dependencies.make_device_repository` provides and async context manager for device repository which allows you to perform CRUD operations on devices. You can store arbitrary data in `Device.integration_data` or `Parameter.integration_data` fields as long as they are JSON serializable. You can use custom subclasses of `Device` and `Parameter` to override `integration_data` type annotation, for example, with another pydantic model for hassle-free automatic serialization and deserialization.

### Checklist

- discovery of new devices (`self.dependencies.output.controller_did_receive_discovery` is called)
- discovery of devices already paired to Hub, for example, in cases of device's or Hub's reboot (`self.dependencies.output.controller_did_connect_device` is called)
- device pairing (`async def pair_device` is implemented)
- device schema is properly mapped: device info, parameters list, and each parameter's metadata are translated to MajorDom language
- Hub -> Device control (`async def send_command` is implemented)
- Device -> Hub device event subscription handling (`self.dependencies.output.controller_did_receive_device_events` is being called)
- `identify`, `unpair`, `fetch` methods are implemented
- graceful shutdown in `def stop` method


### AbstractController Overview

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncContextManager, Callable, Protocol, Type
from uuid import UUID

from typing_extensions import Iterable
from zeroconf.asyncio import AsyncZeroconf

from majordom_hub.repository.device_repository import DeviceRepository
from majordom_hub.schemas.automation.events import DeviceParameterChangedEvent
from majordom_hub.schemas.command import DeviceCommand
from majordom_hub.schemas.device import CredentialsValue, Device, Discovery, Parameter


class ControllerOutput(Protocol):

    async def controller_did_receive_discovery(self, controller: AbstractController, discovery: Discovery): ...

    async def controller_did_connect_device(self, controller: AbstractController, device_id: UUID): ...

    async def controller_did_receive_device_events(self, controller: AbstractController, event: Iterable[DeviceParameterChangedEvent]): ...

class AbstractController[TDevice: Device, TParameter: Parameter](ABC):

    @dataclass
    class Dependencies:
        output: ControllerOutput
        make_device_repository: Callable[[], AsyncContextManager[DeviceRepository]]
        zeroconf: AsyncZeroconf
        register_zeroconf: Callable[[set[str]], None]

    def __init__(self, dependencies: Dependencies):
        self.dependencies = dependencies

    # Abstract - to be implemented

    @property
    @abstractmethod
    def discoveries(self) -> dict[UUID, Discovery]:
        return {}

    @property
    @abstractmethod
    def name(self) -> str:
        return ''

    @property
    def device_type(self) -> Type[TDevice]:
        '''Override this property to use your own Device subclass for auto parsing'''
        return Device

    @property
    def parameter_type(self) -> Type[TParameter]:
        '''Override this property to use your own Parameter subclass for auto parsing'''
        return Parameter

    @abstractmethod
    async def start(self): 
        '''Setup the integration here'''
        ...

    @abstractmethod
    async def stop(self): 
        '''Gracefully cleanup and shutdown the integration'''
        ...

    @abstractmethod
    async def pair_device(self, discovery: Discovery, credentials: CredentialsValue | None): ...

    @abstractmethod
    async def unpair(self, device: TDevice): ...

    @abstractmethod
    async def identify(self, device: TDevice): ...

    @abstractmethod
    async def fetch(self, device: TDevice): ...

    @abstractmethod
    async def send_command(self, command: DeviceCommand, device: TDevice, parameter: TParameter): ...
```

### Data Models

```python
# Pairing

class CredentialsType(str, Enum):
    code = "code"  # pin, e.g. 1234-123-1234 (matter) or 123-45-678 (homekit)
    secret = "secret"  # for example, AES key like in esphome
    qr = "qr"  # raw qr data;
    none = "none"
    # can be extended if needed

    def with_mask(self, code_mask: str) -> CredentialsType:
        """
        mask format: D as digit placeholder, other symbols like dashes remain unchanged,
        for example "DDD-DD-DDD" for "123-45-678"
        Can be extended if needed.
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


# Device


class DeviceInfo(DevicePatch):
    name: str
    note: str = ""
    icon: str | None = None
    category: str | None = None
    room_id: UUID
    
    id: UUID
    transport: str
    integration: str
    manufacturer: str | None

    last_seen: datetime | None = None
    available: bool = False


class Device(DeviceInfo):
    integration_data: SerializeAsAny[dict | Base] = Field(default_factory=Base)


class DeviceDataModel(DeviceInfo):
    parameters: list[Parameter]


class DeviceState(DeviceInfo):
    parameters: list[ParameterState]

# Parameters

class ParameterDataType(StrEnum):
    none = "none" # e.g. button
    # numeric
    bool = "bool"
    integer = "integer"
    decimal = "decimal" # python float
    enum = "enum" # integer with string_representation
    # data
    string = "string"
    data = "data" # binary data, base64 encoded at high level
    # can be extended if needed

class ParameterUnit(StrEnum):
    plain = "plain" # raw data type
    percentage = "percentage"
    # time
    second = "second"
    hertz = "hertz"
    # kinematic
    kilogram = "kilogram"
    arcdegree = "arcdegree"
    meters = "meters"
    mps = "mps" # meters per second, speed
    mps2 = "mps2" # meters per second squared, acceleration
    rpm = "rpm" # revolutions per minute
    newton = "newton" # force
    joule = "joule" # energy
    watt = "watt" # power
    # temperature
    celsius = "celsius"
    kelvin = "kelvin"
    # electricity
    volt = "volt"
    ampere = "ampere"
    # light
    lux = "lux"
    # air
    pascal = "pascal"
    ppm = "ppm" # parts per million, air quality
    # informatics
    bytes = "bytes" # data size
    bps = "bps" # bytes per second, data rate

class ParameterRole(StrEnum):
    sensor = 'sensor' # get-only
    control = 'control' # get-set
    event = 'event'

class Parameter(UUIdentifable):
    id: UUID
    name: str
    data_type: ParameterDataType
    unit: ParameterUnit = ParameterUnit.plain
    role: ParameterRole

    # value constraints (value for nubmers, char length for string, byte length for data)
    min_value: int | float | None = None
    max_value: int | float | None = None
    min_step: int | float | None = None
    
    valid_values: dict[int | float | str, str] | None = None # value and string representation, mostly for enums

    integration_data: Any

class ParameterState(Parameter):
    value: bytes
```
