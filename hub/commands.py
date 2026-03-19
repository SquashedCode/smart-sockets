# Handles On/Off commands from the Hub/App
import connection

def queue_base_power(base_name, state):
    """Toggles all 8 nodes at once for a specific base"""
    state = state.upper() # Standardize to "ON" or "OFF"
    with connection.registry_lock: # Safely updates shared registry
        if base_name in connection.device_registry:
            code = connection.device_registry[base_name]['code']
            # Format: "BASE 87654321 OFF"
            cmd = f"BASE {code} {state}\n"
            # Command will be picked up by next heartbeat
            connection.device_registry[base_name]['pending_cmd'] = cmd
            # Update local tracking for Hub display
            for n in range(1, 9):
                connection.device_registry[base_name]['nodes'][n] = state
            return True
    return False

def queue_node_power(base_name, node_num, state):
    """Toggles 1 individual node (1-8)"""
    state = state.upper()
    with connection.registry_lock:
        if base_name in connection.device_registry:
            code = connection.device_registry[base_name]['code']
            # Format: "BASE 87654321 NODE 1 ON"
            cmd = f"BASE {code} NODE {node_num} {state}\n"
            
            # Stores command in registry
            connection.device_registry[base_name]['pending_cmd'] = cmd
            # Update node state in registry
            connection.device_registry[base_name]['nodes'][node_num] = state
            return True
    return False
