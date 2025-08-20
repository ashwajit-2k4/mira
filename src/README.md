## Overview

This folder contains the complete codebase for the project, divided into three main components based on the hardware platform they run on:

### CMOD (FPGA)
- **Platform:** CMOD FPGA (e.g., CMOD A7)
- **Function:** Collects data from the TMAG sensor array and relays it to the Raspberry Pi via SPI.

### Raspberry Pi 5
- **Platform:** Raspberry Pi 5
- **Functions:**
  - Controls the motors and manages the motion of the sensor rig.
  - Receives sensor data from the FPGA and transmits it to the Laptop.

### Laptop
- **Platform:** PC or Laptop
- **Function:** Acts as the GUI for the project, providing visualization and user controls.

---

Each subfolder contains a more detailed description of the code and instructions on how to run it.

