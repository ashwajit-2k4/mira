# Code for RPi 5

## Setup Instructions:
1. Acquire and configure your Rpi 5 with the full or lite debian OS.
2. Connect the Rpi 5 to the same WiFi network as your laptop. Ensure there is no client isolation. A possible way to work around networks with client isolation is to configure the Rpi 5 to always connect to a specified hotspot setup on your laptop. Eg: my Rpi 5 always connects to my hotspot "asusr".
3. Enable SPI on your Rpi 5:
   - Run sudo raspi-config
   - Use the arrow key to select Interfacing Options -> SPI -> Yes, when it prompts you to enable SPI.
   - Select yes if it asks about automatically loading the kernel module.
   - Right arrow to select the <Finish> button.

## Functioning
The RPi 5 code performs 5 major functions in independent threads:
1. `cmd_list`: Listens to commands from the Rpi 5 and performs one of the following:
   - `start`: Begins sweeping space and data acquisition.
   - `pause`: Pause data acquisition and sweeping.
   - `reset`: Bring the sensor head back to the origin.
   - `update_coordinates`: Move to a specific location in space.
   - `stop`: Completely stop the system. Note that you must restart your application once stop has been used. 
3. `frame_reader`: Read data using SPI from the FPGA continuously and push it to the TCP and UDP queues.
4. `frame_writer`: Wait for motor stability before coupling the magnetic field data with the current location and make it ready to send.
5. `tcpsend`: Send packets of mag field data with location for the 3D plot via TCP to the laptop.
6. `udpsend`: Send packets of only mag field data for the live heatmap via UDP to the laptop.
7. `acq`: The sweeping and data acquisition thread that sweeps 3D space and sets a motor stability event that controls when magnetic field data is coupled with a specific location.

