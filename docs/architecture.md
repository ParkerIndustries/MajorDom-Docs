MajorDom consists of several key components: devices, hub, cloud, bridge, mobile application, and voice assistant.

Devices play a crucial role in the system as they enable control over physical parts of the home. They communicate using radio modules and the “Merlin” protocol that receive commands from the hub, and transmit events back to it.

The hub is the central element of the system. It manages the devices and coordinates their operations. The hub holds the main database with information about users, home, rooms, and devices. Through a local HTTP server and WS server, the hub provides an API for interacting with the database and for high-level control of devices.

The cloud is the server-side component and plays a vital role in user authentication. It stores the database of users, homes, hubs, and their access rights. Device models with a list of parameters and a firmware update system are also stored in the cloud.

The bridge is a WS server that provides communication between the hub and remote user over the internet. It enables sending commands and receiving information from the hub without being within the home's local network.

The system can have multiple bridges located in different places. Clients select the nearest or least loaded bridge to minimize communication delays.

One of the main features of the MajorDom is its fault tolerance. Despite the collapse of one or multiple bridges, the system perseveres and maintains its functionality. The remaining available bridges take on the tasks of the inactive bridges, ensuring uninterrupted data exchange between the hub and clients.

Even a complete loss of internet connection on the hub is not a problem. All the logic and command processing occur locally, ensuring independence from the internet connection and maintaining the ability to control devices within the local network. However, such scenarios are rare since the hub can be simultaneously connected via Wi-Fi and an Ethernet cable, and future support for cellular network will be added.

Smart home control is achieved through a mobile application that provides a user-friendly interface. However, in practice, the role of the mobile application often reduces to system configuration, while day-to-day device management is carried out using automatic scenarios and the voice assistant.

Like the hub, the voice assistant can work completely offline, ensuring security, privacy, and reliability of use.
