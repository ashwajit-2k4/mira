
### EDL 2025 Project Submission Repository.

### Project Name: P-05 : Magnetic Field Camera
### Team Number: MON-08
### Team Members:
- Aditya Vema Reddy Kesari (22b3985)
- Ashwajit Singh (22b1227)
- N V Navaneeth Rajesh (22b1215)
- Raunak Mukherjee (22b3955)
- Suchet Gopal (22b1814)

### Problem Statement and Solution:

<!-- Provide a description about the project and what you've learnt and achieved in this. -->

<b> Problem Statement </b> 

High resolution magnetic imaging of objects is extremely important in industrial applications, to check for defects in manufactured parts like permanent magnets or motors. However, many current products like MAGCAM have exhorbitant costs that make them unviable for many people.

<b> Our Solution </b> 

MIRA M1 fills in this gap, as an affordable  magnetic field camera consisting of an 8x8 sensor array, that maps the field distribution in the volume around an object using an r-theta-z movement rig in just a few minutes. 

The object to be measured is placed on a rotating platform, with the sensor array itself moving in the r-z plane, thus enabling the mapping out of 3D space. The user interacts with a laptop-based GUI, to move the sensors to the starting position, and then start the pre-programmed sweep. The GUI then shows the live heatmap of the values the sensor array sees (at above 80 frames per second), along with a continuously updating scatter plot showing a 3D visualisation of the field.

<b> How It Works </b> 

The GUI starts an SSH connection to a Raspberry Pi, that controls the motors for rig movement, and communicates with the CMOD A7 FPGA that interfaces with the sensor array. When acquisition is started, the RPi rotates the theta motor by 360 degrees in 200 steps, acquiring data from sensors in every step. It then moves in the r direction in steps, repeating this process before it moves up in the z direction.

<b> Deliverables </b> 

- 2mm spatial resolution: **Achieved** (Currently with 1.75mm resolution, which can be increased further)
- 1mT sensitivity: **Achieved** (Obtained 0.2mT sensitivity)

### Key Learnings

Since our project had a lot of moving parts, with the CMOD FPGA, the Raspberry Pi microcontroller and the laptop GUI, in addition to the motor movement mechanism, communication was essential to ensure compatibility between these parts. Additionally, we had to put a lot of thought into component choice, since we could not use commonly available steel components due to interference. Since we required very high resolution, both in terms of magnetic field and spatial movement, it required careful design of PCBs and CAD models, and required adapting parts in the mechanism to ensure that we had minimum spatial error from jitter.

### Walkthrough of the repo

The source code consists of code for 3 devices: CMOD A7 FPGA, Raspberry Pi 5 and the laptop GUI. Additionally, the PCB designs for the sensor PCB we ultimately used, along with the backup PCB, and the PCB containing the FPGA are provided. The CAD models for all 3D printed and laser cut parts are also provided.


