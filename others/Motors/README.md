### Motor Driver Connections  

We make use of 3 NEMA-17 stepper motors, one each for R, Theta and Z respectively. These are supplied power by the 12V SMPS (through the TB6600 motor drivers). The motor drivers make use of microstepping, and can be configured using the DIP Switches to change their current draw and microstep count.  

Since the motor driver inputs are differential, we connect one of +/- to GND and the other to a GPIO Pin of the RPi 5.
