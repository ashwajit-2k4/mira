# PCB Overview

This folder contains all the design files, layouts, schematics, and assembled images for the PCBs developed for our project.

## PCB Summary

| PCB | Description | 
|-----|-------------|
| **PCB_1** | `TMAG3001 Sensor Array` – An 8×8 array using I2C-based TMAG3001 magnetometers. Used in the final sensor head. | 
| **PCB_2** | `CMOD Interface Board` – Interfaces the TMAG sensor array (PCB_1 or PCB_3) with a CMOD FPGA module. Includes power control and signal routing. | 
| **PCB_3** | `TMAG5170 Sensor Array` – A backup 8×8 sensor array using SPI-based TMAG5170 magnetometers. Fully compatible with PCB_2. | 

---

## Sensor Head Configuration

The **sensor head** for the magnetic field camera is built using:
- **PCB_2** (CMOD Interface)
- **Either** PCB_1 **or** PCB_3 (Sensor Array)

> Note: PCB_3 serves as an alternative to PCB_1 and can be used interchangeably without any hardware modifications.

---

## Manufacturing Note

Due to the complexity and design constraints, **none of the PCBs could be fabricated in-house at IIT Bombay**.  
All boards were professionally manufactured by **PCB Power**.

---

## Folder Contents

Each PCB folder contains:
- **Schematics**
- **PCB Layouts**
- **3D Renders**
- **Assembled Board Images**

---


