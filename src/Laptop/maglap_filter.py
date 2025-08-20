import sys
import threading
import time
import socket
import ast
import numpy as np
import math
import cv2
import subprocess
import json

import tkinter as tk
from tkinter import ttk, messagebox
from collections import deque
from datetime import datetime
from PIL import Image, ImageTk
import signal
import paramiko
from matplotlib import colors

# For the 3D plot embedding
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import gridspec, cm
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk


# ------------------------------- Utility
def to_signed(val):
    return val - 0x10000 if val & 0x8000 else val


def extract_xyz_pixel(word):
    word1 = (word >> 32) & 0xFFFFFFFF
    word0 = word & 0xFFFFFFFF
    pix_id_upper = (word1 >> 28) & 0x7
    timestamp = (word1 >> 20) & 0xFF
    z_data = (word1 >> 4) & 0xFFFF
    y_upper = word1 & 0xF
    pix_id_lower = (word0 >> 28) & 0x7
    y_lower = (word0 >> 16) & 0xFFF
    x_data = word0 & 0xFFFF
    y_data = (y_upper << 12) | y_lower
    pixel = (pix_id_upper << 3) | pix_id_lower
    x_signed = to_signed(x_data)
    y_signed = to_signed(y_data)
    z_signed = to_signed(z_data)
    return x_signed, y_signed, z_signed, pixel


# convert 1 frame (location + 64 sensor data) into cartesian coordinates
def parse_data(in_data):
    coord, sensor_data = in_data
    for word in sensor_data:
        Bx, By, Bz, pixel = extract_xyz_pixel(word)
        Bx, By, Bz = Bx * MAG_CONVERSION, By * MAG_CONVERSION, Bz * MAG_CONVERSION
        tc, rc, zc = coord[0], coord[1] + (pixel // 8) * PIXEL_JUMP_R, coord[2] + (pixel % 8) * PIXEL_JUMP_Z

        x = rc * math.sin(math.radians(1.8 * tc)) * STEP_CONVERSION
        y = rc * math.cos(math.radians(1.8 * tc)) * STEP_CONVERSION
        z = zc * STEP_CONVERSION

    return ((x, y, z), (Bx, By, Bz), pixel)


# ------------------------------- Global variables

SIMULATION = 1  #Variable for our simulation interface, if it is 1 we run a simulation of a file acting like the Rpi else 0 for the original code
mag_data = []
udp_mag_data = None
udp_heatmap_image = None
file_lock = threading.Lock()
MAG_CONVERSION = 1 / 137 #Conversion from LSB to mT

# Rate measurement
UDP_RATE_WINDOW = 5  # seconds to calculate average rate
udp_packet_times = deque(maxlen=1000)
udp_rate = 0  # packets per second

# OpenCV window flag
opencv_window_active = True
MAG_TRESHOLD = 12 # Threshold to avoid noise in plots
SCALE = 300
magchoice = "M"


# ------------------------------- Remote Launch

def handle_sigint(signum, frame):
    global remote_shell
    print("\n[Main] SIGINT received in main thread.")
    if remote_shell is not None:
        try:
            print("[Main] Sending Ctrl+C to remote process...")
            remote_shell.send("\x03")
        except Exception as ex:
            print("[Main] Error sending Ctrl+C:", ex)
    else:
        print("[Main] No remote shell established.")


signal.signal(signal.SIGINT, handle_sigint)

#Gets Laptop IP
def get_laptop_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception as e:
        print("Error obtaining laptop IP address:", e)
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

#Gets RPi ip
def get_pi_ip(pi_hostname, username, password):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(pi_hostname, username=username, password=password)
        stdin, stdout, stderr = client.exec_command("hostname -I")
        ip_output = stdout.read().decode().strip()
        client.close()
        pi_ip = ip_output.split()[0] if ip_output else None
        return pi_ip
    except Exception as e:
        print("Failed to get Raspberry Pi IP address:", e)
        return None

#Connects to Rpi using SSH and launches program in RPi in a proper manner
def ssh_execute(pi_ip, remote_script_path, laptop_ip):
    global remote_shell, ssh_client
    remote_command = remote_script_path + " " + laptop_ip + " " + str(LAPTOP_RECEIVE_PORT) + " " + str(LAPTOP_COMMAND_PORT) + " " + str(UDP_HEATMAP_PORT)  # Pass laptop IP as argument
    output_file = "rpi_output.txt"
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print("Connecting to Raspberry Pi...")
        ssh_client.connect(hostname=PI_HOSTNAME, port=22, username=PI_USERNAME, password=PI_PASSWORD)
        print("Connected. Launching remote command...")
        remote_shell = ssh_client.invoke_shell()
        time.sleep(0.5)
        remote_shell.send(remote_command + "\n")

        def log_remote_output(shell, output_file):
            with open(output_file, "w") as f:
                try:
                    while True:
                        if shell.recv_ready():
                            output = shell.recv(1024).decode("utf-8")
                            sys.stdout.write(output)
                            sys.stdout.flush()
                            f.write(output)
                            f.flush()
                        time.sleep(0.1)
                except Exception as e:
                    print("Error in reading remote output:", e)

        threading.Thread(target=log_remote_output, args=(remote_shell, output_file), daemon=True).start()
    except Exception as e:
        print("An error occurred in ssh_execute:", e)

#Initialisation
def initializer(pi_hostname, pi_username, pi_password, remote_script_path):
    laptop_ip = get_laptop_ip()
    print("Laptop IP Address:", laptop_ip)
    pi_ip = get_pi_ip(pi_hostname, pi_username, pi_password)
    if not pi_ip:
        raise Exception("Could not retrieve Raspberry Pi IP address")
    print("Raspberry Pi IP Address:", pi_ip)
    ssh_execute(pi_ip, remote_script_path, laptop_ip)



# ------------------------------- Network Config
#Finds a free port on laptop
def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# -------------------------------------------------------

# Configuration for Remote Execution
PI_HOSTNAME = "raspberrypi.local"
PI_USERNAME = "raunak"
PI_PASSWORD = "123"
#REMOTE_SCRIPT_PATH = "python /home/raunak/p2.py "
REMOTE_SCRIPT_PATH = "python /home/raunak/magpi1.py"
BUFFER_SIZE = 1024
DATA_FILE = "plot.txt"  # We'll also write out completed blocks here (optional)

UPDATE_INTERVAL = 33  # update interval in ms
STEP_CONVERSION = 0.01
MAG_CONVERSION = 1 / 137
PIXEL_JUMP_R = 560
PIXEL_JUMP_Z = 560

LAPTOP_RECEIVE_PORT = get_free_port()
LAPTOP_COMMAND_PORT = get_free_port()
UDP_HEATMAP_PORT = get_free_port()
if SIMULATION==1:
    RPi_IP = "127.0.0.1"
else:
    RPi_IP = get_pi_ip(PI_HOSTNAME, PI_USERNAME, PI_PASSWORD)

# At startup, clear and recreate the output file.
with open(DATA_FILE, 'w') as f:
    f.truncate(0)
print(f"[INIT] {DATA_FILE} has been recreated.")

# ------------------------------- Start Simulated p1.py (once only)
if SIMULATION==1:
    if __name__ == '__main__':
        subprocess.Popen([
            sys.executable, "simulation.py",
            RPi_IP,
            str(LAPTOP_RECEIVE_PORT),
            str(LAPTOP_COMMAND_PORT),
            str(UDP_HEATMAP_PORT)
        ])


# ------------------------------- Command Sender
def send_command(cmd):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((RPi_IP, LAPTOP_COMMAND_PORT))
            s.sendall(cmd.encode())
            response = s.recv(1024).decode()
            print(f"[COMMAND] Sent: {cmd}, Received: {response.strip()}")
    except Exception as e:
        print(f"[COMMAND] Error sending '{cmd}': {e}")


# ------------------------------- TCP Receiver

def persistent_receiver():
    global mag_data
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", LAPTOP_RECEIVE_PORT))
    server.listen(1)
    while True:
        try:
            conn, addr = server.accept()
            with conn:
                # Create a file-like object for reading incoming lines.
                with conn.makefile() as f:
                    for line in f:
                        try:
                            tcpdata = ast.literal_eval(line.strip())
                            parsed = parse_data(tcpdata)
                            mag_data.append(parsed)
                            # Append parsed data to the file
                            with open(log_filename, "a") as log_file:
                                log_file.write(f"{tcpdata}\n")

                        except Exception as e:
                            print("[TCP RECEIVER] Parsing error:", e)
        except Exception as e:
            print(f"[TCP RECEIVER] Exception: {e}")
            time.sleep(1)


# ------------------------------- UDP Receiver
def udp_persistent_receiver():
    global udp_mag_data, udp_rate, udp_packet_times
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_sock.bind(("0.0.0.0", UDP_HEATMAP_PORT))

    # Set non-blocking mode
    udp_sock.setblocking(False)

    while True:
        try:
            try:
                data, addr = udp_sock.recvfrom(65535)
                # Record timestamp for rate calculation
                now = datetime.now()
                udp_packet_times.append(now)

                # Calculate current rate
                if len(udp_packet_times) > 1:
                    # Remove old packets outside our window
                    while udp_packet_times and (now - udp_packet_times[0]).total_seconds() > UDP_RATE_WINDOW:
                        udp_packet_times.popleft()

                    # Calculate rate
                    if len(udp_packet_times) > 1:
                        time_diff = (udp_packet_times[-1] - udp_packet_times[0]).total_seconds()
                        if time_diff > 0:
                            udp_rate = (len(udp_packet_times) - 1) / time_diff

                try:
                    frames = json.loads(data.decode("utf-8"))
                    udp_mag_data = frames
                except Exception as e:
                    print("[UDP RECEIVER] Error parsing UDP:", e)
            except BlockingIOError:
                # No data available, just continue
                time.sleep(0.001)
            except Exception as e:
                print("[UDP RECEIVER] Exception in receive:", e)
                time.sleep(0.01)
        except Exception as e:
            print("[UDP RECEIVER] Outer exception:", e)
            time.sleep(1)


# ------------------------------- Laptop Key Handler
def on_arrow_key(event):
    global magchoice

    # Get current coordinate values from the input fields; default to 0 if empty.
    current_r=0
    current_z=0
    current_theta=0
    # Update coordinates based on the key pressed.
    #to move up in z
    if event.keysym == "Up":
        current_z += 100
    #To move down in z
    elif event.keysym == "Down":
        current_z -= 100
    #To move up in r
    elif event.keysym == "Left":
        current_r += 100
    #To move down in r
    elif event.keysym == "Right":
        current_r -= 100
    #To plot Bx on our GUI
    elif event.keysym.lower() == "x":
        magchoice = "X"
    #To plot By on our GUI
    elif event.keysym.lower() == "y":
        magchoice = "Y"
    #To plot Bz on our GUI
    elif event.keysym.lower() == "z":
        magchoice = "Z"
    #To plot modB on our GUI
    elif event.keysym.lower() == "m":
        magchoice = "M"

    # Form the command string and send it.
    command_string = f"update acoordinates,{current_r},{current_theta},{current_z}"
    send_command(command_string)
    #app.status_var.set(f"Updated via arrow key: r={current_r}, θ={current_theta}, z={current_z}")






# ------------------------------- Tkinter App Class -------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Magnetic Field Viewer")
        self.geometry("1200x950")  # Adjusted window size
        #self.attributes('-fullscreen', True)

        # --- Top Control Frames ---
        self.control_frame = ttk.Frame(self)
        self.control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        self.start_btn = ttk.Button(self.control_frame, text="Start",
                                    command=lambda: threading.Thread(target=self.button_command, args=("start",),
                                                                     daemon=True).start())
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(self.control_frame, text="Stop",
                                   command=lambda: threading.Thread(target=self.button_command, args=("stop",),
                                                                    daemon=True).start())
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.pause_btn = ttk.Button(self.control_frame, text="Pause",
                                    command=lambda: threading.Thread(target=self.button_command, args=("pause",),
                                                                     daemon=True).start())
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        self.reset_btn = ttk.Button(self.control_frame, text="Reset",
                                    command=lambda: threading.Thread(target=self.button_command, args=("reset",),
                                                                     daemon=True).start())
        self.reset_btn.pack(side=tk.LEFT, padx=5)
        self.update_field_btn = ttk.Button(self.control_frame, text="Update Distribution",
                                           command=self.update_field_distribution)
        self.update_field_btn.pack(side=tk.LEFT, padx=5)

        # Coordinates update controls
        self.coords_frame = ttk.Frame(self)
        self.coords_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        ttk.Label(self.coords_frame, text="r:").pack(side=tk.LEFT, padx=2)
        self.input_r = ttk.Entry(self.coords_frame, width=10)
        self.input_r.pack(side=tk.LEFT, padx=2)
        ttk.Label(self.coords_frame, text="θ (theta):").pack(side=tk.LEFT, padx=2)
        self.input_theta = ttk.Entry(self.coords_frame, width=10)
        self.input_theta.pack(side=tk.LEFT, padx=2)
        ttk.Label(self.coords_frame, text="z:").pack(side=tk.LEFT, padx=2)
        self.input_z = ttk.Entry(self.coords_frame, width=10)
        self.input_z.pack(side=tk.LEFT, padx=2)
        self.update_coords_btn = ttk.Button(self.coords_frame, text="Update Coordinates",
                                            command=lambda: threading.Thread(target=self.button_command,
                                                                             args=("update_coords",),
                                                                             daemon=True).start())
        self.update_coords_btn.pack(side=tk.LEFT, padx=5)
        self.status_var = tk.StringVar(value="Idle")
        self.status_label = ttk.Label(self.coords_frame, textvariable=self.status_var, font=("Helvetica", 12))
        self.status_label.pack(side=tk.LEFT, padx=15)

        # --- Main Display Frame ---
        self.display_frame = ttk.Frame(self)
        self.display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left Panel: OpenCV Heatmap and UDP Rate
        self.left_frame = ttk.Frame(self.display_frame)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        ttk.Label(self.left_frame, text="Live Sensor Array Heatmap", font=("Helvetica", 14)).pack(anchor="center", pady=(100, 5))

        # Use a frame to hold the heatmap and its colorbar side-by-side.
        self.heatmap_frame = ttk.Frame(self.left_frame)
        self.heatmap_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.heatmap_label = ttk.Label(self.heatmap_frame)
        self.heatmap_label.pack(side=tk.LEFT, padx=5, pady=5)
        self.heatmap_colorbar_label = ttk.Label(self.heatmap_frame)
        self.heatmap_colorbar_label.pack(side=tk.LEFT, padx=5, pady=5)
        self.rate_var = tk.StringVar()
        self.rate_label = ttk.Label(self.left_frame, textvariable=self.rate_var, font=("Helvetica", 12))
        self.rate_label.pack(side=tk.TOP, pady=5)

        # Right Panel: 3D Field Distribution Plot
        self.right_frame = ttk.Frame(self.display_frame)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)
        ttk.Label(self.right_frame, text="3D plot", font=("Helvetica", 14)).pack(pady=5)
        self.fig3d = Figure(figsize=(5, 4), dpi=100)
        self.ax3d = self.fig3d.add_subplot(111, projection="3d")
        self.ax3d.set_xlabel("X")
        self.ax3d.set_ylabel("Y")
        self.ax3d.set_zlabel("Z")
        self.ax3d.dist = 5  # Lower values zoom in, default is 10
        self.canvas3d = FigureCanvasTkAgg(self.fig3d, master=self.right_frame)
        self.canvas3d.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.toolbar3d = NavigationToolbar2Tk(self.canvas3d, self.right_frame)
        self.toolbar3d.update()
        self.toolbar3d.pack(fill=tk.X)

        self.sm = cm.ScalarMappable(cmap="viridis_r", norm=colors.Normalize(0, MAG_TRESHOLD))
        self.ax3d.dist = 5  # default zoom (closer)
        self.sm = cm.ScalarMappable(cmap="viridis_r", norm=colors.Normalize(0, MAG_TRESHOLD))
        self.field_colorbar = self.fig3d.colorbar(self.sm, ax=self.ax3d, pad=0.1, aspect=10)
        self.field_colorbar.set_label("|B| (magnetic field strength)")

        # Bottom Panel: 2D Heatmap Plot
        self.bottom_frame = ttk.Frame(self.display_frame)
        self.bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(self.bottom_frame, text="Projections", font=("Helvetica", 14)).pack(pady=5)

        # Instead of a matplotlib canvas, we use a Label to display the processed image.
        self.heatmap1_label = ttk.Label(self.bottom_frame)
        self.heatmap1_label.pack(fill=tk.BOTH, expand=True, pady=5)

        self.heatmap2_label = ttk.Label(self.bottom_frame)
        self.heatmap2_label.pack(fill=tk.BOTH, expand=True, pady=5)

        self.heatmap3_label = ttk.Label(self.bottom_frame)
        self.heatmap3_label.pack(fill=tk.BOTH, expand=True, pady=5)

        # Bind the Enter key to launch the main application
        self.bind("<Escape>", self.close_app)

        # Begin periodic updates
        self.update_opencv_heatmap()
        self.update_rate()
        self.update_field_distribution()  # Initial update for 3D plot
        self.update_2d_heatmap()  # Initial update for 2D heatmap
        self.update_2d_heatmap1()
        self.update_2d_heatmap2()

    # ---------------- Button Command Handler ----------------
    def button_command(self, command_type):
        if command_type == "start":
            send_command("start")
            self.status_var.set("Acquisition Started")
        elif command_type == "stop":
            send_command("stop")
            self.status_var.set("Acquisition Stopped")
        elif command_type == "pause":
            send_command("pause")
            self.status_var.set("Acquisition Paused")
        elif command_type == "reset":
            with file_lock:
                try:
                    open(DATA_FILE, 'w').close()
                    print("[RESET] Data file cleared.")
                except Exception as e:
                    print(f"[RESET] Error: {e}")
            send_command("reset")
            self.status_var.set("Acquisition Reset")
        elif command_type == "update_coords":
            r = self.input_r.get()
            theta = self.input_theta.get()
            z = self.input_z.get()
            if r and theta and z:
                send_command(f"update coordinates,{r},{theta},{z}")
                self.status_var.set(f"Updated coordinates: r={r}, θ={theta}, z={z}")
            else:
                self.status_var.set("Please enter all coordinates (r, theta, z).")
        else:
            self.status_var.set("Idle")

    # ---------------- OpenCV Heatmap Update ----------------
    def update_opencv_heatmap(self):
        global udp_mag_data

        # MAG_THRESHOLD = 12     # Fixed maximum scale for heatmap
        Z_THRESH = 2.5         # Z-score threshold for detecting local outliers
        MIN_FRAME_STD = 0.3    # Lowered threshold for std dev since scale is smaller now

        # Initialize heatmap buffer
        if not hasattr(self, 'heatmap_data'):
            self.heatmap_data = np.zeros((8, 8), dtype=float)

        # Process new UDP data
        if udp_mag_data:
            for word in udp_mag_data:
                try:
                    Bx, By, Bz, pixel = extract_xyz_pixel(word)
                    Bx *= MAG_CONVERSION
                    By *= MAG_CONVERSION
                    Bz *= MAG_CONVERSION

                    # Choose magnitude based on selection
                    if magchoice == "M":
                        mag = math.sqrt(Bx ** 2 + By ** 2 + Bz ** 2)
                    elif magchoice == "X":
                        mag = -Bx
                    elif magchoice == "Y":
                        mag = By
                    elif magchoice == "Z":
                        mag = Bz
                    else:
                        mag = math.sqrt(Bx ** 2 + By ** 2 + Bz ** 2)

                    row = 7 - (pixel // 8)
                    col = pixel % 8
                    if 0 <= row < 8 and 0 <= col < 8 and mag != 0:
                        self.heatmap_data[row, col] = mag
                except Exception:
                    continue

        # Skip frame if it's likely invalid or too weak
        if np.count_nonzero(self.heatmap_data) < 10 or np.std(self.heatmap_data) < MIN_FRAME_STD:
            self.after(UPDATE_INTERVAL, self.update_opencv_heatmap)
            return

        # Outlier filtering: smooth extreme pixels based on local neighborhood
        filtered_data = self.heatmap_data.copy()
        for i in range(8):
            for j in range(8):
                neighborhood = self.heatmap_data[max(0, i-1):min(8, i+2), max(0, j-1):min(8, j+2)]
                local_mean = np.mean(neighborhood)
                local_std = np.std(neighborhood)
                if local_std > 0 and abs(self.heatmap_data[i, j] - local_mean) / local_std > Z_THRESH:
                    filtered_data[i, j] = local_mean

        # Resize and normalize using absolute scale
        resized = cv2.resize(filtered_data, (400, 400), interpolation=cv2.INTER_NEAREST)
        norm_img = np.clip(resized / MAG_THRESHOLD * 255, 0, 255).astype(np.uint8)

        # Invert and colorize for display
        inv_img = 255 - norm_img
        colored = cv2.applyColorMap(inv_img, cv2.COLORMAP_VIRIDIS)
        colored_rgb = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)

        # Display updated heatmap
        img = Image.fromarray(colored_rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        self.heatmap_label.imgtk = imgtk
        self.heatmap_label.configure(image=imgtk)

        # Reschedule the update
        self.after(UPDATE_INTERVAL, self.update_opencv_heatmap)


    # ---------------- UDP Rate Update ----------------
    def update_rate(self):
        global udp_rate, udp_packet_times, UDP_RATE_WINDOW
        self.rate_var.set(
            f"UDP Rate: {udp_rate:.2f} packets/sec | Count (last {UDP_RATE_WINDOW}s): {len(udp_packet_times)}")
        self.after(500, self.update_rate)

    # ---------------- 3D Field Distribution Plot Update ----------------
    def update_field_distribution(self):
        global magchoice
        global mag_data
        self.ax3d.clear()
        self.ax3d.set_xlabel("X")
        self.ax3d.set_ylabel("Y")
        self.ax3d.set_zlabel("Z")

        points = []
        for frame in mag_data:
            if isinstance(frame, tuple) and len(frame) == 3:
                try:
                    coords, B_vector, pixel = frame
                    x, y, z = coords
                    Bx, By, Bz = B_vector
                    if magchoice == "M":
                        mag = math.sqrt(Bx ** 2 + By ** 2 + Bz ** 2)
                    elif magchoice == "X":
                        mag = -Bx
                    elif magchoice == "Y":
                        mag = By
                    elif magchoice == "Z":
                        mag = Bz
                    else:
                        mag = math.sqrt(Bx ** 2 + By ** 2 + Bz ** 2)

                    if mag <= MAG_TRESHOLD:
                        points.append((x, y, z, mag))
                except Exception as e:
                    print("Error processing frame:", e)
                    continue

        if points:
            x_vals, y_vals, z_vals, mag_vals = zip(*points)
            mag_array = np.array(mag_vals)
            # Normalize on an absolute scale [0, MAG_TRESHOLD].
            norm = np.clip(mag_array / MAG_TRESHOLD, 0, 1)
            cmap = cm.get_cmap("viridis_r")
            colors = cmap(norm)
            # Set alpha proportional to intensity (low intensity nearly transparent)
            colors[:, 3] = 0.5+norm*0.5
            self.ax3d.scatter(x_vals, y_vals, z_vals, c=colors, s=10, edgecolors='none')
            # Update colorbar without removing it
            self.sm.set_array(mag_array)
            self.sm.set_clim(0, MAG_TRESHOLD)
            self.field_colorbar.update_normal(self.sm)

        else:
            self.ax3d.text2D(0.5, 0.5, "No valid points", horizontalalignment='center', transform=self.ax3d.transAxes)
        self.canvas3d.draw()
        self.after(100, self.update_field_distribution)

    # ---------------- 2D Heatmap projection for xy plane  Plot Update ----------------
    def update_2d_heatmap(self):

        global mag_data

        data_points = []
        try:
            for frame in mag_data:
                if isinstance(frame, tuple) and len(frame) == 3:
                    try:
                        coords, B_vector, pixel = frame
                        x, y, z = coords
                        Bx, By, Bz = B_vector
                        mag = math.sqrt(Bx ** 2 + By ** 2 + Bz ** 2)
                        data_points.append((x, y, mag))
                    except Exception as e:
                        print("Error processing frame:", e)
                        continue
        except Exception as e:
            print("[2D Heatmap] Data parsing error:", e)

        # Define grid resolution (50x50 by default)
        grid_size = 50
        if data_points:
            xs = [pt[0] for pt in data_points]
            ys = [pt[1] for pt in data_points]
            mags = [pt[2] for pt in data_points]
            # Define bins based on the range of x and y values.
            x_bins = np.linspace(min(xs), max(xs), grid_size + 1)
            y_bins = np.linspace(min(ys), max(ys), grid_size + 1)
            # Create two 2D histograms: one for the sum of magnitudes and one for counting.
            sum_grid, _, _ = np.histogram2d(xs, ys, bins=[x_bins, y_bins], weights=mags)
            count_grid, _, _ = np.histogram2d(xs, ys, bins=[x_bins, y_bins])
            # Compute the average magnitude per bin.
            with np.errstate(divide='ignore', invalid='ignore'):
                avg_grid = np.divide(sum_grid, count_grid, out=np.zeros_like(sum_grid), where=count_grid != 0)
            avg_grid = np.nan_to_num(avg_grid)
        else:
            avg_grid = np.zeros((grid_size, grid_size), dtype=float)

        # Use OpenCV functions (like in update_opencv_heatmap) to generate an image:
        resized = cv2.resize(avg_grid, (200, 200), interpolation=cv2.INTER_NEAREST)
        norm_img = cv2.normalize(resized, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        colored = cv2.applyColorMap(norm_img, cv2.COLORMAP_VIRIDIS)
        colored_rgb = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(colored_rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        self.heatmap1_label.imgtk = imgtk  # Keep a reference to avoid GC.
        self.heatmap1_label.configure(image=imgtk)
        self.after(100, self.update_2d_heatmap)
    # ---------------- 2D Heatmap projection for yz plane  Plot Update ----------------
    def update_2d_heatmap1(self):

        global mag_data

        data_points = []
        try:
            for frame in mag_data:
                if isinstance(frame, tuple) and len(frame) == 3:
                    try:
                        coords, B_vector, pixel = frame
                        x, y, z = coords
                        Bx, By, Bz = B_vector
                        mag = math.sqrt(Bx ** 2 + By ** 2 + Bz ** 2)
                        data_points.append((y, z, mag))
                    except Exception as e:
                        print("Error processing frame:", e)
                        continue
        except Exception as e:
            print("[2D Heatmap] Data parsing error:", e)

        # Define grid resolution (50x50 by default)
        grid_size = 50
        if data_points:
            xs = [pt[0] for pt in data_points]
            ys = [pt[1] for pt in data_points]
            mags = [pt[2] for pt in data_points]
            # Define bins based on the range of x and y values.
            x_bins = np.linspace(min(xs), max(xs), grid_size + 1)
            y_bins = np.linspace(min(ys), max(ys), grid_size + 1)
            # Create two 2D histograms: one for the sum of magnitudes and one for counting.
            sum_grid, _, _ = np.histogram2d(xs, ys, bins=[x_bins, y_bins], weights=mags)
            count_grid, _, _ = np.histogram2d(xs, ys, bins=[x_bins, y_bins])
            # Compute the average magnitude per bin.
            with np.errstate(divide='ignore', invalid='ignore'):
                avg_grid = np.divide(sum_grid, count_grid, out=np.zeros_like(sum_grid), where=count_grid != 0)
            avg_grid = np.nan_to_num(avg_grid)
        else:
            avg_grid = np.zeros((grid_size, grid_size), dtype=float)

        # Use OpenCV functions (like in update_opencv_heatmap) to generate an image:
        resized = cv2.resize(avg_grid, (200, 200), interpolation=cv2.INTER_NEAREST)
        norm_img = cv2.normalize(resized, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        colored = cv2.applyColorMap(norm_img, cv2.COLORMAP_VIRIDIS)
        colored_rgb = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(colored_rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        self.heatmap2_label.imgtk = imgtk  # Keep a reference to avoid GC.
        self.heatmap2_label.configure(image=imgtk)
        self.after(100, self.update_2d_heatmap1)


    # ---------------- 2D Heatmap projection for zx plane  Plot Update ----------------
    def update_2d_heatmap2(self):

        global mag_data
        # Use the current z-slice value if needed for filtering (optional)

        # Gather data points: (x, y, magnetic intensity) from mag_data.
        # (Here we ignore z, but you could filter on z_slice_val if desired.)
        data_points = []
        try:
            for frame in mag_data:
                if isinstance(frame, tuple) and len(frame) == 3:
                    try:
                        coords, B_vector, pixel = frame
                        x, y, z = coords
                        Bx, By, Bz = B_vector
                        mag = math.sqrt(Bx ** 2 + By ** 2 + Bz ** 2)
                        data_points.append((z, x, mag))
                    except Exception as e:
                        print("Error processing frame:", e)
                        continue
        except Exception as e:
            print("[2D Heatmap] Data parsing error:", e)

        # Define grid resolution (50x50 by default)
        grid_size = 50
        if data_points:
            xs = [pt[0] for pt in data_points]
            ys = [pt[1] for pt in data_points]
            mags = [pt[2] for pt in data_points]
            # Define bins based on the range of x and y values.
            x_bins = np.linspace(min(xs), max(xs), grid_size + 1)
            y_bins = np.linspace(min(ys), max(ys), grid_size + 1)
            # Create two 2D histograms: one for the sum of magnitudes and one for counting.
            sum_grid, _, _ = np.histogram2d(xs, ys, bins=[x_bins, y_bins], weights=mags)
            count_grid, _, _ = np.histogram2d(xs, ys, bins=[x_bins, y_bins])
            # Compute the average magnitude per bin.
            with np.errstate(divide='ignore', invalid='ignore'):
                avg_grid = np.divide(sum_grid, count_grid, out=np.zeros_like(sum_grid), where=count_grid != 0)
            avg_grid = np.nan_to_num(avg_grid)
        else:
            avg_grid = np.zeros((grid_size, grid_size), dtype=float)

        # Use OpenCV functions (like in update_opencv_heatmap) to generate an image:
        resized = cv2.resize(avg_grid, (200, 200), interpolation=cv2.INTER_NEAREST)
        norm_img = cv2.normalize(resized, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        colored = cv2.applyColorMap(norm_img, cv2.COLORMAP_VIRIDIS)
        colored_rgb = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(colored_rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        self.heatmap3_label.imgtk = imgtk  # Keep a reference to avoid GC.
        self.heatmap3_label.configure(image=imgtk)
        self.after(100, self.update_2d_heatmap2)
    
    def close_app(self, event=None):
        self.destroy()

# ------ INTRO SCREEN

class IntroScreen(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Configure the window for fullscreen
        self.title("Welcome")
        self.attributes('-fullscreen', True)
        
        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Create a frame to hold everything
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Load and resize background image
        # Replace 'background.jpg' with your image path
        try:
            img = Image.open("mira1_bg.png")
            img = img.resize((screen_width, screen_height), Image.LANCZOS)
            self.bg_image = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Error loading image: {e}")
            # Fallback - create a gradient background
            self.bg_image = None
        
        # Create a canvas for the background
        self.canvas = tk.Canvas(self.main_frame, width=screen_width, height=screen_height)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Set the background image or fallback gradient
        if self.bg_image:
            self.canvas.create_image(0, 0, image=self.bg_image, anchor=tk.NW)
        else:
            # Create gradient background as fallback
            for i in range(screen_height):
                # Create a blue to black gradient
                color = f'#{0:02x}{0:02x}{max(0, 150-i//4):02x}'
                self.canvas.create_line(0, i, screen_width, i, fill=color)
        
        # Bind the Enter key to launch the main application
        self.bind("<Return>", self.launch_main_app)
        self.bind("<Escape>", self.close_app)
        
    
    def launch_main_app(self, event=None):
        self.destroy()  # Close the intro screen
        app = App()  # Launch your main application
        app.bind("<KeyPress>", on_arrow_key)
        app.mainloop()
    
    def close_app(self, event=None):
        self.destroy()


# ---------------- Starting Threads ----------------
def start_network_threads():
    threading.Thread(target=persistent_receiver, daemon=True).start()  # TCP receiver
    threading.Thread(target=udp_persistent_receiver, daemon=True).start()  # UDP receiver


#########################
# Main Execution        #
#########################
if __name__ == '__main__':
    log_filename = "parsed_data.txt"
    start_network_threads()
    if SIMULATION=="0":
    # Start remote command initialization.
        remote_thread = threading.Thread(
            target=initializer,
            args=(PI_HOSTNAME, PI_USERNAME, PI_PASSWORD, REMOTE_SCRIPT_PATH),
            daemon=True
        )
        remote_thread.start()
    intro = IntroScreen()
    intro.mainloop()
    print("[MAIN]: Network threads started")

