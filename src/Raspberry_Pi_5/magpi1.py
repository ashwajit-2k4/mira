import socket
import threading
import json
import time
import sys
import math
import random
import queue
import spidev
import RPi.GPIO as GPIO
from collections import deque


DATA_FILE = "data.txt"
# Simulated global queues
tcp_message_queue = queue.Queue()
udp_message_queue = queue.LifoQueue(maxsize=1000)
tcp_send_queue = queue.Queue()

# Global flags and counters
acquisition_enabled = False
running = True
n_theta = 0              # Theta motor step counter
n_r = 0                  # r motor current position (cumulative)
n_z = 0                  # Total number of steps moved in z direction
counter = 0              # Acquisition cycle counter

# Motor sweep parameters
r_count = 0
jump_count = 0
theta_jump = 1
full_revolution_theta = 200
r_jump = 4480
r_jump_half = 280
full_revolution_r = 22400
z_jump = 4480
z_jump_half = 280
full_revolution_z = 22400

acquisition_enabled = False
running = True
motor_stable_event = threading.Event()

DATA_FILE = "data.txt"

# GPIO Pin Definitions
THETA_DIR = 6 # 31
THETA_STEP = 5 # 29
R_DIR = 27 # 13
R_STEP = 17 # 11
Z_DIR = 24 # 18
Z_STEP = 23 # 16

"""
Z
True = Up (CW)
False - Down (ACW)

R
False - In (anticlockwise)
True - Out (clockwise)

Theta
False - ACW
True - CW

"""
# Directions for future reference
Z_UP = True
Z_DOWN = False
R_IN = False
R_OUT = True
THETA_CW = True
THETA_ACW = False

# Set GPIO pins
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for DIR, STEP in [(THETA_DIR, THETA_STEP), (R_DIR, R_STEP), (Z_DIR, Z_STEP)]:
    GPIO.setup(DIR, GPIO.OUT)
    GPIO.setup(STEP, GPIO.OUT)

last_file_pos = 0
file_lock = threading.Lock()

######## SPI CODE ##################
# SPI Setup
SPI_BUS = 0
SPI_DEVICE = 0
SPI_SPEED = 10000000
SPI_MODE = 3

spi = spidev.SpiDev()
spi.open(SPI_BUS, SPI_DEVICE)
spi.max_speed_hz = SPI_SPEED
spi.mode = SPI_MODE


#---------------------- SPI -----------------------------------
# Define a simulation of SPI for debugging
def simulate_spi():
    frames = []
    timestamp = int(time.time() * 1000) & 0xFF
    t = time.time()
    for pix_id in range(64):
        angle = (t * 10 + pix_id) % (2 * math.pi)
        x = int(1000 * math.sin(angle)) & 0xFFFF
        y = int(1000 * math.cos(angle)) & 0xFFFF
        z = int(1000 * math.sin(angle + math.pi / 4)) & 0xFFFF

        word0 = (pix_id & 0x7) << 28 | ((y & 0xFFF) << 16) | (x & 0xFFFF)
        word1 = (1 << 31) | ((pix_id >> 3) & 0x7) << 28 | (timestamp << 20) | ((z & 0xFFFF) << 4) | ((y >> 12) & 0xF)
        frame = (word1 << 32) | word0
        frames.append(frame)
    return frames

# Send commands via SPI to the FPGA to boot, shutdown, etc
# Send a 64-bit command to the FPGA as 8 separate 8-bit bytes in big-endian order.
def send_command(cmd):

    cmd_bytes = [
        (cmd >> 56) & 0xFF,
        (cmd >> 48) & 0xFF,
        (cmd >> 40) & 0xFF,
        (cmd >> 32) & 0xFF,
        (cmd >> 24) & 0xFF,
        (cmd >> 16) & 0xFF,
        (cmd >> 8)  & 0xFF,
        cmd & 0xFF
    ]
    #print(f"Sending command: 0x{cmd:08X}")
    spi.xfer2(cmd_bytes)
    time.sleep(0.1)

# Read 64 frames by default. 1 frame = 8 bytes / 64 bits from FPGA
def read_frame(n=64):
    packs = []
    for i in range(n):
        raw1 = spi.readbytes(8)
        if len(raw1) != 8:
            print("Error: Incomplete first word received.")
            return None
        word1 =(raw1[0] << 56) | (raw1[1] << 48) | (raw1[2] << 40) | (raw1[3] << 32) | (raw1[4] << 24) | (raw1[5] << 16) | (raw1[6] << 8) | raw1[7]
        if word1 != 0:
            #time.sleep(0.01)
            packs.append(word1)
        else:
            continue
    return packs

# Intialize the SPI: boot and begin readout
def init_spi(waste=5):
     # Reset FPGA
    send_command(0xA1A1A1A1A1A1A1A1)
    time.sleep(0.01)
    for i in range(2):
    # Optionally, read ACK frame (4 bytes)
        ack_bytes = spi.readbytes(8)
        ack = (ack_bytes[0] << 56) | (ack_bytes[1] << 48) | (ack_bytes[2] << 40) | (ack_bytes[3] << 32) | (ack_bytes[4] << 24) | (ack_bytes[5] << 16) | (ack_bytes[6] << 8) | ack_bytes[7]
        print(f"ACK received: 0x{ack:16X}")

    # Start readout
    send_command(0x5151515151515151)
    time.sleep(0.01)
    for i in range(1):
    # Optionally, read ACK frame (4 bytes)
        ack_bytes = spi.readbytes(8)
        ack = (ack_bytes[0] << 56) | (ack_bytes[1] << 48) | (ack_bytes[2] << 40) | (ack_bytes[3] << 32) | (ack_bytes[4] << 24) | (ack_bytes[5] << 16) | (ack_bytes[6] << 8) | ack_bytes[7]
        print(f"ACK received: 0x{ack:16X}")
    # Drop the first few frames 
    for _ in range(waste * 64):
        spi.readbytes(8)
    
# Stop readout
def stop_readout():
    send_command(0x5252525252525252)
    print("Waiting 100 ms for FPGA to stop readout...")
    time.sleep(0.1)

# Check for bit errors
def check_parity(packet):
    ones_count = bin(packet).count('1')

    # Check if ones_count % 2 equals parity_bits
    is_valid = (ones_count % 2) == 0
    return is_valid

# Count parity failures in an entire frame
def check_parity_frames(frames):
    try:
        fails = 0
        for pack in frames:
            if not(check_parity(pack)):
                fails += 1
        if fails != 0:
            print(f"[SPI]: {fails} parity errors in a frame.")
    except:
        pass

# ----------------- Motor Control and Sweep -----------------
# Move the motor - True (CW), False (ACW)
def move_motor(DIR_PIN, STEP_PIN, steps, delay=0.001, direction=True):
    GPIO.output(DIR_PIN, GPIO.HIGH if direction else GPIO.LOW)
    for _ in range(steps):
        GPIO.output(STEP_PIN, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(STEP_PIN, GPIO.LOW)
        time.sleep(delay)

# Define the sweeping code for the motors to cover 3d space
def sweep():
    global n_theta, n_r, n_z, r_count, jump_count, acquisition_enabled

    move_motor(THETA_DIR, THETA_STEP, theta_jump)
    # Update theta till a full revolution
    n_theta += theta_jump
    if n_theta >= full_revolution_theta:
        n_theta = 0
        # Decide r to sweep in or out depending on it's height
        if jump_count % 2 == 1:
            # Move r in
            if n_r - r_jump < 0:
                # Sweep completed
                if n_z + (z_jump - z_jump_half) > full_revolution_z:
                    acquisition_enabled = False
                    reset_r_z()
                    return
                else:
                # Increment z once r is done
                    move_motor(Z_DIR, Z_STEP, z_jump - z_jump_half, direction = Z_UP)
                    n_z += z_jump-z_jump_half
                    r_count = 0
                    jump_count += 1
            else:
            # Increment r
                r_count += 1
                if (r_count % 2 == 0):
                    move_motor(R_DIR, R_STEP, r_jump-r_jump_half, direction = R_IN)
                    n_r -= r_jump - r_jump_half
                else:
                    move_motor(R_DIR, R_STEP, r_jump_half, direction = R_IN)
                    n_r -= r_jump_half
        else:
            # Move r out
            if n_r + r_jump > full_revolution_r:
                # Sweep completed
                if n_z + z_jump_half > full_revolution_z:
                    acquisition_enabled = False
                    reset_r_z()
                    return
                else:
                # Increment z once r is done
                    move_motor(Z_DIR, Z_STEP, z_jump_half, direction = Z_DOWN)
                    n_z += z_jump_half
                    r_count = 0
                    jump_count += 1
            else:
                # Increment r 
                r_count += 1
                if (r_count % 2 == 0):   
                    move_motor(R_DIR, R_STEP, r_jump - r_jump_half, direction = R_OUT)
                    n_r += r_jump-r_jump_half
                else:
                    move_motor(R_DIR, R_STEP, r_jump_half, direction = R_OUT)
                    n_r += r_jump_half
    # print(f"[ACQUIRE] Sweep executed: theta={n_theta}, r={n_r}, z_steps={n_z}")

# This function resets the sensor head to the origin
def reset_r_z():
    global n_r, n_z
    move_motor(R_DIR, R_STEP, n_r, direction=R_IN)
    n_r = 0
    move_motor(Z_DIR, Z_STEP, n_z, direction=Z_DOWN)
    n_z = 0
    print(f"[RESET] r reset to {n_r} and z reset to {n_z}")

# Go to a specific r, theta, z
def go_to_r_theta_z(target_r, target_theta, target_z):
    global n_r, n_theta, n_z

    # Move in r direction (same as reset logic)
    if n_r < target_r:
        move_motor(R_DIR, R_STEP, target_r - n_r, direction=False)
    elif n_r > target_r:
        move_motor(R_DIR, R_STEP, n_r - target_r, direction=True)
    n_r = target_r

    # Move in θ direction (no reference in reset_r_z, so assuming current logic is correct)
    if n_theta < target_theta:
        move_motor(THETA_DIR, THETA_STEP, target_theta - n_theta, direction=True)
    elif n_theta > target_theta:
        move_motor(THETA_DIR, THETA_STEP, n_theta - target_theta, direction=False)
    n_theta = target_theta

    # Move in z direction (corrected to match reset_r_z logic)
    if n_z > target_z:
        move_motor(Z_DIR, Z_STEP, n_z - target_z, direction=True)
    elif n_z < target_z:
        move_motor(Z_DIR, Z_STEP, target_z - n_z, direction=False)
    n_z = target_z

    print(f"[GO TO] Reached r={n_r}, θ={n_theta}, z={n_z}")

# ---------- COMMUNICATION -----------------------
# Continuosly read frames from the FPGA and put them in the UDP and TCP queues
def continuous_frame_reader():
    global running
    init_spi()
    while running:
        if acquisition_enabled:
            #frames = simulate_spi()
            frames = read_frame()
            check_parity_frames(frames)
            if frames:
                udp_message_queue.put(frames)
                tcp_message_queue.put(frames)
            time.sleep(0.01)
        else:
            time.sleep(0.1)

# Wait till motor is stable to couple the magentic field data with a location tuple
def frame_writer():
    global counter, n_theta, n_r, n_z
    while running:
        motor_stable_event.wait()
        location_tuple = (n_theta, n_r, n_z, counter)
        frames = []
        try:
            frame = tcp_message_queue.get(timeout=2)
            if frame is not None:
                tcp_send_queue.put((location_tuple, frame))
        except queue.Empty:
            print("[FRAME_WRITER] Not enough frames received.")
        motor_stable_event.clear()

# Send the frames via UDP for the live heatmap
def udp_sender(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while running:
        try:
            frames = udp_message_queue.get(timeout=1)
            sock.sendto(json.dumps(frames).encode(), (ip, port))
        except queue.Empty:
            pass

# Send the (location, magnetic data) via TCP to the laptop
def tcp_sender(ip, port):
    while running:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))
            while running:
                try:
                    block = tcp_send_queue.get(timeout=2)
                    # Convert block to JSON, append a newline delimiter, and send it.
                    msg = json.dumps(block).encode() + b"\n"
                    sock.sendall(msg)
                    #print("[TCP SENDER]: Sent")
                except queue.Empty:
                    continue
        except Exception as e:
            print("[TCP SENDER] Connection error:", e)
            time.sleep(2)
        finally:
            try:
                sock.close()
            except:
                pass

# This thread only sweeps and makes the motor stable
def acquisition_thread():
    global counter
    while running:
        if acquisition_enabled:
            sweep()
            motor_stable_event.set()
            counter += 1
            time.sleep(0.01)
        else:
            time.sleep(0.1)

# Listen to commands from the laptop
def command_listener(port):
    global acquisition_enabled, running
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(1)
    print(f"[CMD LISTENER] Listening on port {port}")
    while running:
        conn, addr = server.accept()
        with conn:
            cmd = conn.recv(1024).decode().strip()
            print(f"[CMD RECEIVED] {cmd}")
            if cmd == "start":
                acquisition_enabled = True
                conn.send(b"started\n")
            elif cmd == "pause":
                acquisition_enabled = False
                conn.sendall(b"Acquisition paused\n")
            elif cmd == "reset":
                acquisition_enabled = False
                reset_r_z()
                conn.sendall(b"Motors reset\n")
            elif cmd[:18]=="update coordinates":
                    parts = cmd.strip().split(",")
                    r = int(parts[1])   # 100
                    theta = int(parts[2])  # 45
                    z = int(parts[3])   # 200
                    go_to_r_theta_z(r,theta,z)
            elif cmd[:19]=="update acoordinates":
                    parts = cmd.strip().split(",")
                    r = int(parts[1])  + n_r # 100
                    theta = int(parts[2]) + n_theta# 45
                    z = int(parts[3]) + n_z  # 200
                    go_to_r_theta_z(r,theta,z)
            elif cmd == "stop":
                acquisition_enabled = False
                tcp_message_queue.queue.clear()
                udp_message_queue.queue.clear()
                tcp_send_queue.queue.clear()
                conn.send(b"stopped\n")
            else:
                conn.send(b"unknown\n")

if __name__ == "__main__":
    # Extract the free ports on the laptop from the argument
    ip = sys.argv[1]
    tcp_port = int(sys.argv[2])
    cmd_port = int(sys.argv[3])
    udp_port = int(sys.argv[4])

    # Create debugging files
    try:
        with open(DATA_FILE, "w") as f:
            f.write(f"[INIT] {DATA_FILE} created.\n")
        print(f"[INIT] {DATA_FILE} created.")
    except Exception as e:
        print(f"[INIT] Error creating {DATA_FILE}: {e}")

    # Begin threads
    cmd_list = threading.Thread(target=command_listener, args=(cmd_port,), daemon=True).start()
    frame_reader = threading.Thread(target=continuous_frame_reader, daemon=True).start()
    frm_writer = threading.Thread(target=frame_writer, daemon=True).start()
    tcpsend = threading.Thread(target=tcp_sender, args=(ip, tcp_port), daemon=True).start()
    udpsend = threading.Thread(target=udp_sender, args=(ip, udp_port), daemon=True).start()
    acq = threading.Thread(target=acquisition_thread, daemon=True).start()

    print("[p1.py] Fully integrated acquisition system running.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        running = False
        print("[p1.py] Shutting down.")
    finally:
        cmd_list.join(timeout=2)
        frame_reader.join(timeout=2)
        frm_writer.join(timeout=2)
        tcpsend.join(timeout=2)
        udpsend.join(timeout=2)
        acq.join(timeout=2)
        stop_readout()
        spi.close()
        GPIO.cleanup()
        print("[MAIN] SPI connection closed, GPIO cleaned up. Exiting program.")
