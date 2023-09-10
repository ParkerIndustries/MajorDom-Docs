## Coordinator
The `coordinator.py` module provides the `Coordinator` class, which centralizes the management of various services and controllers. It takes charge of initializing services, dependency injection, setting up initial states, and facilitating communication between different services and controllers.

## Controllers

### AbstractController
This is a generic abstract class that serves as an adapter between high-level actions from applications and low-level actions for exact connection type (like radio modules, IR, etc.). If you want to add a new connection type, you need to implement this class.

### Merlin24Controller
Implementation of AbstractController for Merlin24 radio protocol.

### MerlinHttpController
Implementation of Merlin protocol via http.

## Managers
Mainly database CRUD for each model.

## Models
Database models (tables).

## Schemas
Data types for internal usage and API.

## Server
FastAPI endpoints.

## Services
Subprograms running continuously in parallel daemon threads.

### Device Relay
A service that handles the relay of information between higher-level applications to device controllers with different connection types and vice-versa.

### Client
Mainly manages websocket connection, sends and handles messages. Also can fetch data from cloud.

### Live Display
Rich live display table, cli alternative to gpio status leds. Note: other logs may disappear.

### Merlin24
Low-level listening and sending messages via merlin24 radio protocol.

### GPIO
Buttons and leds.

## Domain
All other stuff.
