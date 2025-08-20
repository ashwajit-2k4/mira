# Code for Laptop

## Note:
Keep the miga1_bg.png in the same folder as mag1.py or maglap_filter.py. Additionally, use maglap.py primarily, maglap_filter.py is a version with noise filtering on the live heatmap (usage is upto consumer preference).

## Usage:
Download the python script into a directory of your choosing. Enter command prompt (on Windows) and cd to the location in which the python script is located. Launch the python script as `python mag1.py` from terminal (or any other working format). 

To close the application - go to the open terminal where the python script is running and press `Ctrl-C` to send a keyboard interrupt. Then close the terminal.

## Description

The Magnetic Field Viewer code is a Python-based system for visualizing real-time magnetic field data from remote sensors. It integrates network communication protocols to receive data via TCP and UDP channels and supports remote control of data sources using SSH through Paramiko. Data parsing routines handle incoming sensor streams, which are then visualized using a combination of graphical libraries. 2D heatmaps are rendered using OpenCV and Matplotlib, while 3D field distributions are displayed interactively using Plotly. 

## Overview

This application simulates acquiring sensor data from a remote device and provides:

1. Real-Time Data Acquisition : Listens for TCP data to parse and log the sensor readings and UDP packets for a heatmap update.
2. Visualizations : The following two methods are used
   - 2D Heatmaps: Multiple views are created by binning data and colorizing using OpenCV functions.
   - 3D Scatter Plot: Uses Matplotlib’s 3D capabilities to render a spatial distribution of the magnetic field.  
3. User Interface : A full-screen Tkinter interface provides control buttons (Start, Stop, Pause, Reset) and coordinate updates. Additionally, arrow key handlers allow real-time adjustment of the coordinates and x,y,z keys for toggling between mode of magnetic field being plotted.
4. Remote Control : Uses Paramiko for SSH connections to a Raspberry Pi to launch remote scripts that send sensor data and accept commands from the viewer application.


## Installations Rquired
Make sure you have Python 3 installed along with the following packages:
- numpy
- matplotlib
- opencv-python
- Pillow
- paramiko
- tk

## Additional Setup
- Ensure that you have a remote device (like a Raspberry Pi) configured for SSH, and the necessary scripts (for example, magpi1.py) are available on the remote system.
- The code references a simulation script (simulation.py) that should be present in the same directory. This script simulates sensor data acquisition. To use this jus toggle the SIMULATION variable in the code to 1.

## Usage

1. Configure Remote Parameters : 
  - Edit the parameters at the top of the code to match your Raspberry Pi or remote sensor settings: PI_HOSTNAME, PI_USERNAME, PI_PASSWORD
  - REMOTE_SCRIPT_PATH should point to the remote Python script (e.g., magpi1.py).
2. Run the main Python file : Use the command python maglap.py
3. Using the Interface :
   - Control Buttons: Click Start, Stop, Pause, or Reset to control data acquisition.
   - Coordinate Updates: Enter new coordinate values (r, θ, z) and click Update Coordinates. You can also use the arrow keys for quick changes.
   - Toggling mode of magnetic field: Use x key to plot Bx signed, y key to plot By signed, z key to plot Bz signed and m to plot modulus of B.

## Function Summaries

- **Utility Functions**
  - **`extract_xyz_pixel(word)`**  
    Extracts X, Y, Z components and a pixel identifier from a 64-bit data word using bitwise manipulation.
    

- **Signal and Networking Functions**
  
  - **`get_laptop_ip()`**  
    Determines the local machine’s IP address by connecting to an external server (8.8.8.8).

  - **`get_pi_ip(pi_hostname, username, password)`**  
    Connects via SSH to a remote Raspberry Pi to retrieve its IP address.

  - **`ssh_execute(pi_ip, remote_script_path, laptop_ip)`**  
    Establishes an SSH connection to the Pi, executes a remote command/script, and logs the remote output to a file

  - **`send_command(cmd)`**  
    Opens a TCP connection to send commands to the sensor system and prints the response.

- **Network Receiver Functions**
  - **`persistent_receiver()`**  
    Runs a persistent TCP server that accepts incoming sensor data, parses each received line using `parse_data`, and appends the processed data to a global list and a log file.

  - **`udp_persistent_receiver()`**  
    Sets up a non-blocking UDP receiver to read JSON-formatted heatmap data, update a global variable, and compute packet reception rate over a specified time window.

- **User Input and Event Handling**
  - **`on_arrow_key(event)`**  
    Handles arrow key inputs to adjust coordinate values (r, θ, z) in the GUI and sends an update command reflecting these changes.

- **Tkinter Application Methods (within the `App` class)**
  - **`button_command(self, command_type)`**  
    Interprets button presses (start, stop, pause, reset, coordinate update) and sends corresponding commands, updating the status display accordingly.

  - **`update_opencv_heatmap(self)`**  
    Continuously updates the OpenCV heatmap display (at ~30 FPS) by processing new UDP data, resizing, normalizing, and colorizing the heatmap.

  - **`update_rate(self)`**  
    Regularly updates the UDP data rate and packet count information in the GUI.

  - **`update_field_distribution(self)`**  
    Generates a 3D scatter plot of the magnetic field data, filtering points below a threshold, applying a colormap, and updating the plot within the GUI.

  - **`update_2d_heatmap(self)`, `update_2d_heatmap1(self)`, `update_2d_heatmap2(self)`**  
    Each function computes a 2D heatmap from sensor data along different projection slices by binning and averaging data, then uses OpenCV to generate and display colored heatmap images.

- **Thread Starter Function**
  - **`start_network_threads()`**  
    Initiates separate threads for running the TCP (`persistent_receiver`) and UDP (`udp_persistent_receiver`) receivers concurrently.

