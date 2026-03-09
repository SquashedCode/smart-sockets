import connection # Link to Harrison's registry

def queue_base_power(base_name, state):
    """Toggles all 8 nodes at once for a specific base"""
    state = state.upper()
    with connection.registry_lock:
        if base_name in connection.device_registry:
            code = connection.device_registry[base_name]['code']
            # Format: "BASE 87654321 OFF"
            cmd = f"BASE {code} {state}\n"
            connection.device_registry[base_name]['pending_cmd'] = cmd
            # Update local tracking for Dylan's display
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
            connection.device_registry[base_name]['pending_cmd'] = cmd
            connection.device_registry[base_name]['nodes'][node_num] = state
            return True
    return False
