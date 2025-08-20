# TMAG5170 Sensor Array PCB

This PCB serves as a **backup** to the main TMAG3001-based board, utilizing **TMAG5170** sensors to form an 8×8 magnetometer array. It is a **2-layer** board designed for ease of hand assembly and SPI-based communication.

## Overview

- **Sensor Type**: TMAG5170 3-axis magnetometers  
- **Array Size**: 8×8 grid (64 sensors)  
- **Inter-sensor Spacing**: 4.625 mm  
- **PCB Type**: 2-layer board  
- **Communication Protocol**: SPI  

---

## Design Details

### SPI Bus Structure

Each **bus** handles 8 sensors (as seen in the schematic).  
- Required lines per bus: `INT`, `SCLK`, `MOSI`, `MISO`  
- Compatible with the same CMOD PCB interface used by the TMAG3001 board  
- Pins per TMAG5170 IC:
  - `VCC`, `GND`, `ALERT`, `SCLK`, `MOSI`, `MISO`, `TEST`, `CS`

> **Note**: Pin mapping ensures drop-in compatibility with existing CMOD interface hardware.

### Electrical Components

- **Pull-up Resistors**: 1.8 kΩ on all lines  
- **Decoupling Capacitors**:
  - 0.1 µF for each sensor IC  
  - 2 × 1 µF bulk capacitors at the input supply

### Physical Layout

- **IC Placement**: Only the TMAG5170 ICs are on the **front** of the PCB  
- **Other Components**: All resistors, capacitors, and connectors are on the **back**, minimizing interference during sensor operation   
- **Test Points**: 8 test points at the **bottom** of the PCB for signal and ground verification

### Assembly & Grounding

- Designed for **hand-soldering** – large enough component footprints  
- Both PCB layers are filled with **ground planes** for signal integrity

---

## Files & Resources

The repository folders include:
- **Schematic**
- **PCB Layout**
- **3D Renders**
- **Assembled PCB Images**

---


