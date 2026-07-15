# Example Integration

A worked-through, pseudo-code integration you can copy as a starting point. It isn't real
protocol code — there's no such thing as "AcmeProtocol" or "AcmeClient". Every piece that
would normally come from a real device library is marked `# pseudo` so you know it's made
up. Everything else — module layout, method names, method signatures, how the pieces call
into each other — matches the real MajorDom interfaces described in
[Implementing a Controller](controller.md), [Storing Data](storing_data.md), and
[Data Models Reference](data_models.md). Read those pages for the full explanation of any
piece you don't recognize below; this page is meant to be read *alongside* them, not
instead of them.

If this is your first integration, don't worry about understanding every line the first
time through. Copy this folder, rename `Acme` to your protocol's name, and start replacing
the `# pseudo` bits with calls into your actual device library one at a time.

## Module Layout

```
services/controller/acme/
├── controller.py     # AbstractController subclass — the only file the Hub actually calls into
├── models.py          # typed integration_data schemas — what MajorDom persists to disk for you
└── mapper.py          # protocol <-> MajorDom conversions — pure functions, no I/O
```

## `models.py`

`integration_data` is a free-form field MajorDom lets every integration attach to its own
`Device`/`Parameter` records, for storing whatever protocol-specific bookkeeping you need
(an auth token, an internal device id, etc.). Here we're using it to remember the device's
network hostname and an auth token the Acme protocol gave us during pairing.

```python
from majordom_hub.schemas.base import Base
from majordom_hub.schemas.device import Device, DeviceState
from majordom_hub.schemas.parameter import Parameter, ParameterState

class AcmeDeviceIntegrationData(Base):
    # Hostname, not IP address — see the big comment on zeroconf_did_update_service
    # below for why that distinction actually matters and isn't just a style choice.
    device_hostname: str
    auth_token: str | None = None

class AcmeParameterIntegrationData(Base):
    # The name Acme's own API uses for this property, e.g. "brightness_pct".
    # We need to remember this so send_command() below knows what to call when the
    # Hub asks us to change this parameter's value.
    acme_property_name: str

# Device/DeviceState and Parameter/ParameterState are pairs: the "State" version carries
# the same fields plus the actual live value(s). You need both — see Storing Data for why.

class AcmeDevice(Device):
    integration_data: AcmeDeviceIntegrationData

class AcmeDeviceState(DeviceState):
    integration_data: AcmeDeviceIntegrationData

class AcmeParameter(Parameter):
    integration_data: AcmeParameterIntegrationData

class AcmeParameterState(ParameterState):
    integration_data: AcmeParameterIntegrationData
```

## `mapper.py`

Keep pure protocol↔domain conversions here — functions that turn "whatever your device
library gives you" into MajorDom's `Parameter`/`Device` types. No I/O, no
`self.dependencies` access, nothing that talks to the network or the database. That way
you (or a test) can call these functions directly without needing a real device connected.

`device_uuid`/`parameter_uuid` (used below) are helper methods provided by
`AbstractController` — see [Implementing a Controller: Helper Methods](controller.md#helper-methods).
They're only available on the controller itself, not on this mapper, so in real code
you'd pass them in or call them from the controller before invoking the mapper.

```python
from majordom_hub.schemas.parameter import ParameterDataType, ParameterRole, ParameterVisibility
from .models import AcmeParameter, AcmeParameterIntegrationData

class AcmeMapper:
    def parameter_from_acme_property(self, parameter_id, acme_property: dict) -> AcmeParameter:
        # acme_property is a made-up shape for this example:
        # {"name": str, "kind": "bool" | "percent", "writable": bool}
        # A real device library will hand you something else — the whole point of this
        # method is translating whatever THAT shape is into MajorDom's Parameter shape.

        # "kind" tells us what data type to declare. Real protocols often use similar
        # small enums/strings for their own type systems — map each one you support.
        if acme_property["kind"] == "bool":
            data_type = ParameterDataType.bool
        else:
            data_type = ParameterDataType.integer

        # "writable" properties are ones the user can change (role=control, e.g.
        # brightness); read-only ones are just sensor readings (role=sensor, e.g. a
        # battery level you can look at but not set).
        if acme_property["writable"]:
            role = ParameterRole.control
        else:
            role = ParameterRole.sensor

        return AcmeParameter(
            id=parameter_id,
            name=acme_property["name"],
            data_type=data_type,
            role=role,
            # ParameterVisibility.user = show this on the device's main screen/widget.
            # See Data Models Reference for the other options (setting, system) and when
            # to use them instead.
            visibility=ParameterVisibility.user,
            integration_data=AcmeParameterIntegrationData(acme_property_name=acme_property["name"]),
        )
```

## `controller.py`

This is the file the Hub actually instantiates and calls methods on. Everything above
exists to support this file.

```python
import asyncio
from uuid import UUID

from majordom_hub.schemas.automation.events import DeviceParameterChangedEvent
from majordom_hub.schemas.base import NonEmptyStr
from majordom_hub.schemas.command import DeviceCommand
from majordom_hub.schemas.device import CredentialsType, Discovery, ProvidedCredentials
from majordom_hub.services.controller.framework.abstract_controller import AbstractController
from majordom_hub.services.controller.framework.discovery.zeroconf_discovery import (
    ZeroconfDiscoveryInfo,
    ZeroconfDiscoveryService,
)

from .mapper import AcmeMapper
from .models import AcmeDevice, AcmeDeviceIntegrationData, AcmeDeviceState, AcmeParameter, AcmeParameterState

class AcmeController(AbstractController[AcmeDevice, AcmeParameter]):
    # A mapper instance shared across all methods on this controller. It's stateless
    # (no I/O, remember), so one instance for the whole controller is fine.
    _mapper = AcmeMapper()

    @property
    def name(self) -> str:
        # Shown to the user in the app as this integration's display name.
        return "Acme"

    @property
    def device_type(self):
        # Tells the Hub to give you AcmeDevice instances (with your integration_data
        # type already parsed) instead of the generic base Device class.
        return AcmeDevice

    @property
    def parameter_type(self):
        return AcmeParameter

    @property
    def discoveries(self) -> dict:
        # The Hub polls this property to show "devices available to pair" in the app.
        # Just return whatever you've been accumulating — don't do any scanning here,
        # that happens in the zeroconf_did_* callbacks below.
        return self._discoveries

    # -------------------------------------------------------------------------
    # Lifecycle — start() runs once when the Hub boots (or when you enable this
    # integration); stop() runs once when the Hub shuts down (or you disable it).
    # -------------------------------------------------------------------------

    async def start(self):
        # Plain dict, keyed by discovery id — this is what the `discoveries` property
        # above returns.
        self._discoveries = {}

        # `AcmeClient` is pseudo-code standing in for whatever SDK your protocol
        # actually provides (a Python library, a subprocess you talk to, raw sockets...).
        self._client = AcmeClient()

        # Ask MajorDom's shared mDNS/Zeroconf service to tell us whenever a device
        # advertising this service type appears/changes/disappears on the network.
        # "_acme._tcp.local." is a made-up service type — yours will be whatever your
        # protocol actually advertises. register() returns a "cancel closure": call it
        # in stop() to unregister, which we do below.
        self._cancel_discovery = self.dependencies.zeroconf_discovery_service.register(
            self, {"_acme._tcp.local."}
        )

        # IMPORTANT: on every Hub restart, start() is the only place you get to
        # reconnect to devices that were already paired before the restart. If you
        # skip this, paired devices will look "stuck" until the user re-pairs them.
        #
        # controller_did_connect_device isn't just for "just finished pairing" — call
        # it any time a device transitions to connected/reachable, which includes
        # right here at Hub boot. That's what actually flips device.available back to
        # True and lets the app show the device as reachable again after a restart.
        async with self.dependencies.make_device_repository() as repo:
            for device in await repo.get_all(self.name, AcmeDevice):
                self._subscribe(device)
                await self.dependencies.output.controller_did_connect_device(self, device.id)

    async def stop(self):
        # Undo everything start() set up, in roughly reverse order.
        self._cancel_discovery()
        await self._client.close()

    # -------------------------------------------------------------------------
    # ZeroconfDiscoveryListener — the Hub's mDNS service calls these three methods
    # on us because we passed `self` to register() above. See Discovery Services
    # for the full protocol definition.
    #
    # A quick note on identifiers: `info.name` is the mDNS service's fully qualified
    # instance name (e.g. "Living Room Lamp._acme._tcp.local."). It's the one field
    # that stays the same across discover/update/remove for the same physical device,
    # so it's what we use to compute a stable discovery_id. We deliberately do NOT use
    # the device's IP address for this — see zeroconf_did_update_service below.
    # -------------------------------------------------------------------------

    async def zeroconf_did_discover_service(self, zeroconf: ZeroconfDiscoveryService, info: ZeroconfDiscoveryInfo):
        # A brand-new device just appeared on the network.
        discovery_id = self.device_uuid(info.name)
        discovery = self._discovery_from_info(discovery_id, info)
        self._discoveries[discovery_id] = discovery
        # Tell the Hub about it so the app can show it as "available to pair".
        await self.dependencies.output.controller_did_receive_discovery(self, discovery)

    async def zeroconf_did_update_service(self, zeroconf: ZeroconfDiscoveryService, info: ZeroconfDiscoveryInfo):
        # An already-discovered (still unpaired) device changed something about its
        # advertisement — most commonly its IP address, because its DHCP lease
        # renewed and the router handed it a different address.
        #
        # This is exactly why we keyed discovery_id off info.name instead of the IP:
        # if we'd used the IP as the identifier, a DHCP renewal would make the Hub
        # think a *new* device just appeared (wrong id!) instead of recognizing it as
        # the same device it already knew about.
        #
        # It also matters after pairing: our stored integration_data.device_hostname
        # (see models.py above) is a *hostname* like "acme-lamp-42.local", which your
        # router/OS resolves to the current IP for you automatically. Because of that,
        # a paired device's IP changing doesn't affect us at all — we never stored the
        # IP in the first place, so there's nothing to update.
        #
        # If you used an IP address instead of a hostname in integration_data, you would
        # need to do two extra things every time this fires for a device that's already
        # paired: (1) update the stored IP in that device's integration_data, and
        # (2) actually verify the device is reachable at the new IP before assuming the
        # update is safe to use (a stale/incorrect update could otherwise silently break
        # control of the device). Using a hostname sidesteps both problems entirely.
        discovery_id = self.device_uuid(info.name)
        if discovery_id not in self._discoveries:
            # Either this device is already paired (not in our discoveries dict
            # anymore), or we somehow never saw the initial discover event for it.
            # Either way, there's no discovery to update.
            return
        discovery = self._discovery_from_info(discovery_id, info)
        self._discoveries[discovery_id] = discovery
        await self.dependencies.output.controller_did_update_discovery(self, discovery)

    async def zeroconf_did_remove_service(self, zeroconf: ZeroconfDiscoveryService, type_: str, name: str):
        # The device went offline or stopped advertising (mDNS "goodbye" packet, or
        # its records simply expired). Note we only get `name` here, not a full `info`
        # object — that's all mDNS gives you on removal.
        discovery_id = self.device_uuid(name)
        if self._discoveries.pop(discovery_id, None) is None:
            # Wasn't in our discoveries dict (already paired, or never seen) — nothing to do.
            return
        await self.dependencies.output.controller_did_lose_discovery(self, discovery_id)

    def _discovery_from_info(self, discovery_id: UUID, info: ZeroconfDiscoveryInfo) -> Discovery:
        # Shared by discover/update above, since they build the exact same shape.
        return Discovery(
            id=discovery_id,
            integration=NonEmptyStr(self.name),
            # Every credentials type a caller could use to pair THIS device. See Data
            # Models Reference for why this is a list and not a single value.
            expected_credentials_options=[CredentialsType.code.with_mask("DDD-DDD")],
            expiration=None,
            transport=NonEmptyStr("IP"),
            device_name=NonEmptyStr(info.decoded_properties.get("name", info.name)),
            device_manufacturer="Acme Corp",
            device_category=None,
            device_icon=None,
        )

    # -------------------------------------------------------------------------
    # Hub -> Device: the Hub calls these when the user takes an action in the app.
    # -------------------------------------------------------------------------

    async def pair_device(self, discovery: Discovery, credentials: ProvidedCredentials | None):
        # ALWAYS validate this. Never assume the caller sent the right kind of
        # credentials just because your own discovery advertised it as an option —
        # validate what was actually sent, every time.
        if not credentials or credentials.type not in discovery.expected_credentials_options:
            raise ValueError("Unsupported or missing credentials for this discovery")

        # Actually pair with the device over the network — this is the one real call
        # to your protocol's SDK that does meaningful I/O in this whole method.
        acme_device = await self._client.pair(discovery.id, code=credentials.value)  # pseudo

        # The device now has a permanent id, separate from its (possibly-temporary)
        # discovery id. Not every protocol needs this distinction — Zigbee, for
        # example, can reuse the same id for both — but many do, so it's worth
        # understanding: `acme_device.serial` here stands in for whatever stable,
        # hardware-level identifier your protocol gives you post-pairing (a serial
        # number, a MAC address, an internal device id — anything guaranteed to never
        # change for this physical device again).
        device_id = self.device_uuid(acme_device.serial)

        async with self.dependencies.make_device_repository() as repo:
            # `repo.state(discovery.id, ...)` fetches the placeholder device row the
            # Hub already created under the discovery id before calling pair_device.
            device = await repo.state(discovery.id, AcmeDeviceState)

            # Give it its real, permanent id.
            device.id = device_id

            device.integration_data = AcmeDeviceIntegrationData(
                device_hostname=acme_device.hostname,  # not an IP — see the note above
                auth_token=acme_device.token,
            )

            # Ask the (now-paired) device what properties/parameters it has, and
            # convert each one via the mapper.
            device.parameters = [
                AcmeParameterState(
                    **self._mapper.parameter_from_acme_property(
                        self.parameter_uuid(device_id, p["name"]), p
                    ).__dict__,
                    value=b"",  # no value fetched yet — fetch() below will fill this in later
                )
                for p in acme_device.properties
            ]

            # save(device, discovery.id) does something subtle: it renames the row
            # that currently exists under discovery.id to live under device.id
            # instead (since we just changed device.id above). One call handles both
            # "save all this new data" and "this device now has a different id".
            await repo.save(device, discovery.id)

        # It's paired now, so it's no longer an available-to-pair discovery.
        self._discoveries.pop(discovery.id)

        # Start listening for live updates from this device (see _subscribe below).
        self._subscribe(device)

        # Tell the Hub pairing succeeded so the app can show the device as connected.
        await self.dependencies.output.controller_did_connect_device(self, device_id)
        return device_id

    async def unpair(self, device: AcmeDevice):
        # Tell the device (or your local bookkeeping) to forget this pairing. The Hub
        # handles removing the device from its own database — you only need to clean
        # up whatever your protocol/SDK needs on its side.
        await self._client.forget(device.integration_data.device_hostname)

    async def identify(self, device: AcmeDevice):
        # Called when the user taps "identify" in the app — make the physical device
        # do something noticeable (blink an LED, play a sound) so they can find it.
        await self._client.blink(device.integration_data.device_hostname)

    async def fetch(self, device: AcmeDevice):
        # Called when the Hub wants a full, fresh snapshot of every parameter's
        # current value — e.g. right after pairing, or if a periodic refresh is
        # configured. Ask the device for everything, then report it all at once.
        properties = await self._client.get_properties(device.integration_data.device_hostname)
        events = [
            DeviceParameterChangedEvent(
                device_id=device.id,
                parameter_id=self.parameter_uuid(device.id, p.name),
                value=p.value,
            )
            for p in properties
        ]
        await self.dependencies.output.controller_did_receive_device_events(self, events)

    async def send_command(self, command: DeviceCommand, device: AcmeDevice, parameter: AcmeParameter):
        # Called when the user changes something in the app (e.g. drags a brightness
        # slider). `command.value` is the new value they chose; `parameter` tells you
        # which of the device's properties they're changing.
        await self._client.set_property(
            device.integration_data.device_hostname,
            parameter.integration_data.acme_property_name,
            command.value,
        )

    # -------------------------------------------------------------------------
    # Device -> Hub: the reverse direction — the physical device tells us
    # something changed, and we need to tell the Hub. See "Device -> Hub" in
    # Implementing a Controller for the full list of things you can report.
    # -------------------------------------------------------------------------

    def _subscribe(self, device: AcmeDevice):
        # Called once per device: right after pairing (from pair_device above), and
        # once per already-paired device on every Hub restart (from start() above).
        # Real protocols differ a lot here — some let you open one persistent
        # connection per device (like this pseudo-code assumes), others require you to
        # poll periodically instead. Either way, the goal is the same: whenever the
        # device's own state changes, tell the Hub about it.

        def on_property_changed(acme_property_name: str, value):
            # This pseudo-callback fires whenever Acme's SDK notices a property
            # changed on the device (e.g. someone flipped a physical switch on it).
            event = DeviceParameterChangedEvent(
                device_id=device.id,
                parameter_id=self.parameter_uuid(device.id, acme_property_name),
                value=value,
            )
            # We're inside a plain (non-async) callback here, so we can't `await`
            # directly — schedule the actual async call as a background task instead.
            asyncio.create_task(
                self.dependencies.output.controller_did_receive_device_events(self, [event])
            )

        def on_availability_changed(is_available: bool):
            # Mid-session availability tracking: some protocols can tell you when a
            # *paired* device goes offline (e.g. someone unplugged it) or comes back,
            # separately from the Hub-restart reconciliation in start() above. If your
            # protocol can detect this, report it — the app can then show the device
            # as unreachable instead of pretending everything's fine.
            #
            # Not every protocol supports this kind of live connectivity signal. If
            # yours doesn't, just don't implement this callback — it's fine to only
            # ever detect availability changes at Hub-restart time via start().
            if is_available:
                asyncio.create_task(
                    self.dependencies.output.controller_did_connect_device(self, device.id)
                )
            else:
                asyncio.create_task(
                    self.dependencies.output.controller_did_lose_device(self, device.id)
                )

        # pseudo: hand both callbacks to the SDK so it can call them whenever
        # something happens on this device.
        self._client.subscribe(
            device.integration_data.device_hostname,
            on_property_changed=on_property_changed,
            on_availability_changed=on_availability_changed,
        )
```

## What's Deliberately Left Out

This example skips a few things your real integration will likely need, so it doesn't
obscure the shape of the interface itself:

- **Error handling** — set `discovery.last_error` / `device.last_error` on failures (see
  [Implementing a Controller: `last_error`](controller.md#last_error)).
- **`start_pairing_window`** — only implement it if your protocol needs an explicit,
  short-lived scan mode (Zigbee permit-join, BLE burst scan). Always-on discovery (mDNS,
  SSDP, like this example) doesn't need it.
- **Retry/backoff, connection pooling, rate limiting** — whatever your protocol's client
  library needs; the Hub doesn't prescribe anything here.
- **Implementing the protocol yourself** — this example assumes `AcmeClient` already
  exists as a ready-made SDK with a high-level API (`pair`, `get_properties`,
  `set_property`, ...). Real protocols don't always have one. If yours doesn't, you may
  need to implement it directly: managing the connection(s), the transport layer, two-way
  message serialization, and so on, all inside your integration's code instead of calling
  out to a library that does it for you. For a simple protocol this might not look very
  different from the pseudo-calls above — a thin client class living in your own
  integration instead of an imported package. For a complex one, it can be a substantial
  amount of work on its own, separate from writing the MajorDom-facing side of things.
  That's fine, and expected. 
  The integration framework (`AbstractController`, the discovery services, the `Device`/
  `Parameter` models) is deliberately kept independent of any particular protocol's
  implementation details, so it doesn't get in your way whichever situation you're in.
  As a side effect of that same independence, everything except the device
  repository and the Hub's own lifecycle wiring — discovery services and the data models
  in particular — is plain public SDK with no hard dependency on MajorDom Hub itself, and
  can be reused standalone (e.g. to build a protocol library outside of MajorDom) once
  you've supplied those few missing pieces yourself.

## Testing

See [Testing](index.md#testing) for the simulated-device test pattern this example would
follow in practice.
