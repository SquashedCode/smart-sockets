# Simulated Menu for testing Requirements
#Created by Harrison Gallo
import asyncio
import threading
import time
import sys

# Harrison's Modular Service Layer
import connection
import commands

def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def print_status_menu():
    """UI helper to show the state of all 8-node clusters"""
    clear_screen()
    print("=== SMART-SOCKET HUB: SYSTEM ARCHITECT CONSOLE ===")
    print("-" * 55)
    
    with connection.registry_lock:
        if not connection.device_registry:
            print("  [!] No Bases Registered. Please Pair a Device.")
        for name, info in connection.device_registry.items():
            print(f"[{info['status']}] {name} (ID: {info['code']})")
            # Displaying the 8-node hierarchy
            nodes = info['nodes']
            row1 = "  Nodes 1-4: " + " ".join([f"[{nodes[i]}]" for i in range(1, 5)])
            row2 = "  Nodes 5-8: " + " ".join([f"[{nodes[i]}]" for i in range(5, 9)])
            print(row1)
            print(row2)
    
    print("-" * 55)
    print("1. Pair New Base (BLE)")
    print("2. Toggle Entire Base (All 8 Nodes)")
    print("3. Toggle Specific Node (1-8)")
    print("4. Exit")
    print("-" * 55)

def main():
    # Launch Harrison's Watchdog Thread immediately on startup
    threading.Thread(target=connection.socket_watchdog, daemon=True).start()

    while True:
        print_status_menu()
        choice = input("\nSelect Option: ").strip()

        if choice == "1":
            # Pairing Process
            code = input("Enter 8-digit Base Code: ").strip()
            name = input("Enter Name (e.g., Master Bedroom): ").strip()
            print(f"Initializing BLE Pairing for {name}...")
            
            success = asyncio.run(connection.pair_new_base(code, name))
            if success:
                print(f"SUCCESS: {name} is now in the registry.")
            else:
                print("FAILURE: Base not found or BLE error.")
            time.sleep(2)

        elif choice == "2":
            # Global Base Toggle
            name = input("Target Base Name: ").strip()
            state = input("Action (ON/OFF): ").upper()
            if commands.queue_base_power(name, state):
                print(f"Command Queued: Entire {name} set to {state}")
            else:
                print("Error: Base name not recognized.")
            time.sleep(1.5)

        elif choice == "3":
            # Granular Node Toggle
            name = input("Target Base Name: ").strip()
            node = int(input("Target Node (1-8): "))
            state = input("Action (ON/OFF): ").upper()
            if commands.queue_node_power(name, node, state):
                print(f"Command Queued: {name} Node {node} set to {state}")
            else:
                print("Error: Invalid Base or Node number.")
            time.sleep(1.5)

        elif choice == "4":
            print("Shutting down Hub...")
            sys.exit()

if __name__ == "__main__":
    main()
