import socket
import json
import time

PORT = 50000
BROADCAST_IP = "255.255.255.255"

# Create UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Allow broadcast
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

# Allow reuse
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Bind listener
sock.bind(("", PORT))

print("UDP tester started")
print("Listening on port", PORT)

# Discovery packet
packet = {
    "type": "DISCOVERY",
    "sender": "PiTestHub"
}

data = json.dumps(packet).encode()

# Send broadcast
sock.sendto(data, (BROADCAST_IP, PORT))

print("Broadcast sent")
print("Waiting for responses...\n")

while True:
    data, addr = sock.recvfrom(4096)

    ip = addr[0]

    print("Packet received from:", ip)

    try:
        decoded = json.loads(data.decode())
        print("JSON:", decoded)
    except:
        print("Raw:", data)

    print("----------")
