# MajorDom Device Integration Guide

An **integration** is a module that bridges MajorDom Hub with IoT devices of a specific protocol or vendor (e.g. HomeKit, Zigbee, Z-Wave).

---

### Concepts

| Term | Meaning |
|---|---|
| **Hub** | The MajorDom Hub core software |
| **Integration** | A protocol/vendor-specific plugin |
| **Discovery Service** | A Hub-provided transport-level service (Zeroconf/mDNS, SSDP, or BLE) that fires raw discovery events. Injected via `self.dependencies`. |
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

## Suggested Module Structure

An integration will typically need more than just a controller. Recommended minimal layout:

```
services/controller/myintegration/
├── controller.py        # AbstractController subclass — the only required file; discovery callbacks and cancel closures are typically stored here too
├── models.py            # Typed integration_data schemas for Device and Parameter subclasses, see Storing Data
├── mapper.py            # Protocol ↔ MajorDom domain model conversions, isolated from the controller for readability
└── parameters_map.py    # Supplemental metadata for parameters that the API does not expose, usually in a form of a static dictionary. For example, device might expose min/max limits for a number via device's API, but the unit is only defined in pdf specification.
```

**`controller.py`** is the only required file. The rest are a template for keeping the controller clean — separate models, pull out conversion logic into a mapper, add metadata dictionary, etc. Of course, other files can be added as needed.

---

## Implementation Checklist

- [ ] Discovery service listeners fire when devices are found, and the controller calls `self.dependencies.output.controller_did_receive_discovery`
- [ ] Discovery services registered via `self.dependencies.zeroconf_discovery_service`, `ssdp_discovery_service`, and/or `ble_discovery_service` as appropriate; cancel closures saved and called in `stop`
- [ ] Discovery of devices already paired to the Hub on reconnect, e.g. after a reboot (`self.dependencies.output.controller_did_connect_device` is called)
- [ ] `start_pairing_window` is implemented if the protocol requires an explicit scan mode
- [ ] Device pairing (`pair_device` is implemented)
- [ ] Device schema is properly mapped: device info, parameter list, and each parameter's metadata are translated to MajorDom's domain model
- [ ] Hub → Device control (`send_command` is implemented)
- [ ] Device → Hub event subscription (`self.dependencies.output.controller_did_receive_device_events` is called on incoming events)
- [ ] `identify`, `unpair`, and `fetch` are implemented
- [ ] Graceful shutdown in `stop`

See [Implementing a Controller](controller.md) for details.

## Notes

### For IP Devices

- **Handle IP changes.** DHCP can reassign addresses. Identify devices by a stable ID (MAC, serial, mDNS hostname, domain-provided id) rather than IP. Monitor ip address regularly and keep it up to date.
- **Use the Hub's provided discovery.** Register your mDNS service types via `self.dependencies.zeroconf_discovery_service.register(...)`, and similar for SSDP and BLE. See [Discovery Services](discovery/index.md) for details. Do not spin up your own discovery stack unless absolutely needed.
