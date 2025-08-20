# MIRA-M1 User Manual

### Setup
This manual assumes the mechanical rig is fully setup and ready to use.  
Once this is done, the first step is to provide 5V, 3.3V and GND connections to the CMOD PCB as showing in the appropriate wiring diagram.  
If this is completed, the CMOD can be powered on. If properly configure, the Orange and Blue LEDs near the FPGA should glow, and pressing BTN0 should trigger LD0. If this doesn't occur, the FPGA may need to have its flash programmed, the appropriate guides for which can be found in the Digilent CMOD A7 Documentation.

If the FPGA boots succesfully, the SPI cables can be connected to the Raspberry Pi 5 and the entire system can be powered on. The power-on sequence should be as follows:  
1. First, the CMOD A7 should be powered on.
2. After this, the Raspberry Pi 5 can be powered on.
3. Finally, the sensors can be turned on.

To connect to the RPi 5, the user must first connect to a WiFi network (Mobile hotspots tend to work best, IITB Wireless does not work). After this, the user must configure their laptop's mobile hotspot as follows:  
Username: 'asusr'
Password: 'qwerty123'.

Once this is done, reboot the RPi and wait for connection. If it doesn't connect, retry with a different network.

After the RPi is connected, use MobaXTerm to ssh with user 'raunak', hostname 'raspberrypi.local' and password '123' . If the connection is succesfull, exit the SSH session.

### Running the system
After successfull SSH connection, run the script 'maglap.py' on the laptop, entering the SSH password '123' when prompted. If the connections to the CMOD are proper, the ACK Packets 'ACCACCBE21A1A1A1', 'ACCACCBEFFFF00A1' and 'ACCACCBE51515151' should appear in this order. If not, please verify the SPI connections and restart the system.

If the ACKs appear, pan to the GUI window which should appear and press Login. 

### Magnetic Configurations
The test magnet should be secured appropriately to the turntable. The user can use the keyboard arrow keys, left and right for R, up and down for Z respectively to position the origin of the rig for scanning. This ideally should be as close to the magnet as possible, but can be changed if the user wants a different scan.

Once the sensor head is properly positioned, press 'Start Acqusition'. The heatmaps and scatter plots will update in real time, and the 8x8 Live |B-z| feed should also be visible. 

After acquisition is completed, the 3D heatmap will show all scanned points. The raw data will be available in plots.txt. To setup a new scan with the same origin, press the Reset button, wait for recentering and follow the same steps again.
