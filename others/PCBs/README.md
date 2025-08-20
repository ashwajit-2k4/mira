### PCB Descriptions  

The CMOD Interface PCB is connected the sensors by the means of 2x 30 pin FPC 0.5mm pitch connnectors, one on each side of the board respectively.  
The backside of the CMOD PCB faces the backside of the TMAG3001 PCB (i.e., the side with pullups and decoupling caps).   

The Screw terminal on the CMOD PCB is meant for power delivery to the CMOD via the 5V connection - this results in a current draw of < 100 mA in active mode. The 3.3V connection supplies the sensors and has a power draw of ~ 200 mA in active mode, ~ 23 mA in idle mode. The PMOD header connects the CMOD to the master readout device (in our case, an RPi 5).
