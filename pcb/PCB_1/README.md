# TMAG3001 Sensor Array PCB

This repository contains the design files and documentation for the **TMAG3001 Sensor Array PCB**. This is the **main PCB** of the project, designed for high-resolution magnetic field sensing using a dense grid of magnetometers.

## Overview

- **Sensor Type**: TMAG3001 3-axis magnetometers  
- **Array Size**: 8x8 grid (64 sensors)  
- **Inter-sensor Spacing**: 3.5 mm  
- **PCB Type**: 4-layer board  
- **Communication Protocol**: I2C  

---

## Design Details

### I2C Bus Structure

Each group of **4 sensors** forms a **single I2C bus**.  
- Each **TMAG3001** uses **3 I2C lines**: `SCL`, `SDA`, and `INT`.
- A single bus handles 4 sensors, with address selection via the `ADD` pin.
- The `ADD` pin is tied to one of: `VCC`, `GND`, `SCL`, or `SDA` — enabling 4 unique addresses per bus.

> **Note**: To reduce the number of GPIOs, the `INT` lines from every **2 buses are shorted** together.

### Electrical Components

- **Pull-up Resistors**: 1.8 kΩ on all I2C lines  
- **Decoupling Capacitors**:
  - 0.1 µF per IC
  - 2 × 1 µF bulk capacitors at the power input  
- **Power Supply Pins** (per IC): `VCC`, `GND`, `INT`, `SCL`, `SDA`, `ADD`

### Physical Layout

- **IC Placement**: Only TMAG3001 ICs are placed on the **top** layer to avoid magnetic interference.
- **Other Components**: All resistors, capacitors, connectors, etc., are placed on the **bottom** layer.
- **Test Points**: 10 test points on the **bottom** for signal probing and ground testing.

### Grounding and Layer Design

- All 4 layers have **solid ground pours** for noise suppression and signal integrity.

---

## Files & Resources

The repository folders include:
- **Schematic**
- **PCB Layout**
- **3D Renders**
- **Assembled PCB Images**

---
