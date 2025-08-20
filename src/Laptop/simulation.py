import socket
import threading
import json
import time
import sys
import math
import random
import queue

# Dummy GPIO definitions for simulation
class GPIO:
    BCM = OUT = HIGH = 1
    LOW = 0

    @staticmethod
    def setmode(x): pass
    @staticmethod
    def setwarnings(x): pass
    @staticmethod
    def setup(x, y): pass
    @staticmethod
    def output(pin, value): pass
    @staticmethod
    def cleanup(): pass

DATA_FILE = "data.txt"
# Simulated global queues
tcp_message_queue = queue.Queue()
udp_message_queue = queue.Queue()
tcp_send_queue = queue.Queue()

acquisition_enabled = False
running = True
motor_stable_event = threading.Event()

n_theta = 0
n_r = 2800 * 7
n_z = 0
counter = 0

# GPIO Pin Definitions
THETA_DIR = 24 
THETA_STEP = 23
R_DIR = 27
R_STEP = 17
Z_DIR = 6
Z_STEP = 5

# Motor sweep parameters
theta_jump = 1
full_revolution_theta = 200
r_jump = 2800
full_revolution_r = 2800 * 7
z_jump = 2800



GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for DIR, STEP in [(THETA_DIR, THETA_STEP), (R_DIR, R_STEP), (Z_DIR, Z_STEP)]:
    GPIO.setup(DIR, GPIO.OUT)
    GPIO.setup(STEP, GPIO.OUT)

# ----------------- Motor Control and Sweep -----------------
def move_motor(DIR_PIN, STEP_PIN, steps, delay=0.001, direction=True):
    GPIO.output(DIR_PIN, GPIO.HIGH if direction else GPIO.LOW)
    for _ in range(steps):
        GPIO.output(STEP_PIN, GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(STEP_PIN, GPIO.LOW)
        time.sleep(delay)

def sweep():
    """
    Perform a sweep step. When theta resets to 0 (i.e. full revolution),
    signal that the motor is stable.
    """
    global n_theta, n_r, n_z
    # Move theta motor one step
    move_motor(THETA_DIR, THETA_STEP, theta_jump)
    n_theta += theta_jump
    if n_theta >= full_revolution_theta:
        n_theta = 0
        jump_count = n_z // z_jump
        if jump_count % 2 == 0:
            if n_r - r_jump < 0:
                move_motor(Z_DIR, Z_STEP, z_jump)
                n_z += z_jump
            else:
                move_motor(R_DIR, R_STEP, r_jump, direction=False)
                n_r -= r_jump
        else:
            if n_r + r_jump > full_revolution_r:
                move_motor(Z_DIR, Z_STEP, z_jump)
                n_z += z_jump
            else:
                move_motor(R_DIR, R_STEP, r_jump, direction=True)
                n_r += r_jump
    # Motor has completed a sweep; signal stability
    print(f"[sweep]: {n_theta}, {n_r}, {n_z}")
    motor_stable_event.set()

def reset_r_z():
    global n_r, n_z
    if n_r < full_revolution_r:
        move_motor(R_DIR, R_STEP, full_revolution_r - n_r, direction=True)
    elif n_r > full_revolution_r:
        move_motor(R_DIR, R_STEP, n_r - full_revolution_r, direction=False)
    n_r = full_revolution_r
    if n_z > 0:
        move_motor(Z_DIR, Z_STEP, n_z, direction=False)
    elif n_z < 0:
        move_motor(Z_DIR, Z_STEP, abs(n_z), direction=True)
    n_z = 0
    print(f"[RESET] r reset to {n_r} and z reset to {n_z}")

#---------------------- SPI -----------------------------------

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

def read_frame(n=64):
    """
    Read n frames from SPI. For simplicity, we assume the same format as simulation.
    Returns a list of 64 frames.
    """
    frames = []
    for _ in range(n):
        raw = spi.readbytes(8)
        if len(raw) != 8:
            print("Error: Incomplete frame received.")
            return None
        word = 0
        for b in raw:
            word = (word << 8) | b
        frames.append(word)
    return frames

def continuous_frame_reader():
    global running
    while running:
        if acquisition_enabled:
            frames = simulate_spi()
            if frames:
                udp_message_queue.put(frames)
                tcp_message_queue.put(frames)
            time.sleep(0.01)
        else:
            time.sleep(0.1)

def frame_writer():
    global counter, n_theta, n_r, n_z
    while running:
        motor_stable_event.wait()
        frames = []
        try:
            frame = tcp_message_queue.get(timeout=2)
        except queue.Empty:
            print("[FRAME_WRITER] Not enough frames received.")
        location_tuple = (n_theta, n_r, n_z, counter)
        tcp_send_queue.put((location_tuple, frame))
        motor_stable_event.clear()


def udp_sender(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while running:
        try:
            frames = udp_message_queue.get(timeout=1)
            sock.sendto(json.dumps(frames).encode(), (ip, port))
        except queue.Empty:
            pass

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

def acquisition_thread():
    global counter
    while running:
        if acquisition_enabled:
            sweep()
            counter += 1
            time.sleep(0.01)
        else:
            time.sleep(0.1)

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
            elif cmd == "stop":
                acquisition_enabled = False
                tcp_message_queue.queue.clear()
                udp_message_queue.queue.clear()
                tcp_send_queue.queue.clear()
                conn.send(b"stopped\n")
            else:
                conn.send(b"unknown\n")

if __name__ == "__main__":
    ip = sys.argv[1]
    tcp_port = int(sys.argv[2])
    cmd_port = int(sys.argv[3])
    udp_port = int(sys.argv[4])
    
    try:
        with open(DATA_FILE, "w") as f:
            f.write(f"[INIT] {DATA_FILE} created.\n")
        print(f"[INIT] {DATA_FILE} created.")
    except Exception as e:
        print(f"[INIT] Error creating {DATA_FILE}: {e}")

    threading.Thread(target=command_listener, args=(cmd_port,), daemon=True).start()
    threading.Thread(target=continuous_frame_reader, daemon=True).start()
    threading.Thread(target=frame_writer, daemon=True).start()
    threading.Thread(target=tcp_sender, args=(ip, tcp_port), daemon=True).start()
    threading.Thread(target=udp_sender, args=(ip, udp_port), daemon=True).start()
    threading.Thread(target=acquisition_thread, daemon=True).start()

    print("[p1.py] Fully integrated acquisition system running.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        running = False
        print("[p1.py] Shutting down.")
