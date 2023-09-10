## Create a Custom Device Model  

1. Open the MajorDom mobile app.
2. Navigate to `Settings` and enable `Developers Mode`.
3. Return to the home screen and tap the `+` button located in the top-right corner.
4. Alongside the existing options "Create a Room" and "Add a Device", a new option, "Create a Device Model", will now be available.
5. Choose `Create a Device Model`.
6. Provide a name for your custom device model and define a set of parameters. Custom parameters can also be added.
7. After creation, the device model and its parameters will be stored on the Hub.
8. You can now use this custom device model with new devices in your home by specifying the device model UUID in the sketch and implementing parameter handling.

## Write Device Sketch  

### Using Merlin Framework  

#### Merlin24 C++  

Merlin24 works with low-power, long-range nrf24l01 radio modules operating on the 2.4GHz band.

Here's an example sketch for controlling a relay:

```cpp
#include <Merlin24.h>

// Define pin numbers
#define RELAY_PIN 3
#define BUTTON_PIN 4

// Variables to store the state
byte relay_state = LOW;
byte last_button_state = HIGH; // Assuming pull-up

// Define constants for function codes
#define RELAY_PARAMETER 1

// Initialize Merlin24 object with device model uuid and parameter value handler function
Merlin24 device("10359220-c504-40d0-bed7-f254cc85e75c", [](byte parameter_index, byte value) {
    switch (parameter_index) {
        case RELAY_PARAMETER:
	        // toggle the relay and save new state
            relay_state = value;
            digitalWrite(RELAY_PIN, value);
            break;
        // You can add more cases here for other parameters
        default:
            break; // Handle unknown function code here (optional)
    }
});

void setup() {
    pinMode(RELAY_PIN, OUTPUT);
    pinMode(BUTTON_PIN, INPUT_PULLUP);
}

void loop() {
    /*
        tick() is required for Merlin24 to work
        it should be called as often as possible
        avoid delays and other blocking code
    */
    device.tick();

    /* 
        Toggle the relay on the button press
        Just an example, in real life you would probably want to debounce the button
    */

    // Read the button state
    byte current_button_state = digitalRead(BUTTON_PIN);

    // Check for button press (LOW when pressed because of pull-up resistor)
    if (last_button_state == HIGH && current_button_state == LOW) {
        
        // Toggle the relay, save the state and send it to hub
        digitalWrite(RELAY_PIN, relay_state);
        relay_state = !relay_state;
        device.send(RELAY_PARAMETER, relay_state);
    }

    // Update last button state
    last_button_state = current_button_state;
}
```

#### MerlinWiFi (MerlinHttp) C++  

The `MerlinHttp` class provides a way to connect your device to a hub over HTTP, making it a great choice for devices that require internet access or advanced capabilities. It is particularly suitable for ESP32/ESP8266 boards.

To switch from `Merlin24` to `MerlinHttp`, all you need to do is change the included header and initialize `MerlinHttp` instead. In most cases, this should be sufficient.

```cpp
#include <MerlinHttp.h>
// ... (other parts remain unchanged)
MerlinHttp device("10359220-c504-40d0-bed7-f254cc85e75c", [](byte parameter_index, byte value) {
// ... (other parts remain unchanged)
```

### Manually (MerlinHttp Protocol Overview)

If you want to use other technologies, hardware, or software—e.g., a Raspberry Pi with a Python program and FastAPI server—you can still communicate with the Hub over HTTP by implementing the required endpoints manually. Below is an overview of how the Hub-to-Device and Device-to-Hub communication occurs.

#### Hub-to-Device Communication

Your device should host an HTTP server and expose the following RESTful API endpoints:

`POST /api/v1/merlin`: Used by the Hub to send parameter updates to the device.
  
**Request Payload:**
```json
{
"index": "<parameter_index: int in 0...255>",
"value": "<parameter_value: int in 0...255>"
}
```

`POST /api/v1/credentials`: Used by the Hub to send network and authentication credentials to the device on initial setup.

**Request Payload:**
```json
{
"ssid": "<Wi-Fi SSID>",
"psk": "<Wi-Fi Password>",
"hub_host": "<Hub Host Address>",
"token": "<JWT Token>"
}
```

#### Device-to-Hub Communication

To communicate with the Hub, the device should make HTTP requests to the Hub's  API endpoints:

Send Parameter Updates: `{hub_host}/api/merlin/state`
  
  **Request Payload:**
```json
{
"index": "<parameter_index: int in 0...255>",
"value": "<parameter_value: int in 0...255>"
}
```

Update Device Host (ip:port) Address: `{hub_host}/api/merlin/host`
  
**Request Payload:**
```json
{
"host": "<device_host_address>"
}
```

#### Authorization

Authentication is implemented using a long-lived JWT token included in the `Authorization` header of each HTTP request:

```json
"Authorization": "Bearer <JWT Token>"
```
