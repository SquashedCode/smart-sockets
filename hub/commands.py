# commands.py
import connection
# from firebase_admin import db

def queue_base_power(base_name, state):
    state = state.upper() 
    with connection.registry_lock:
        if base_name in connection.device_registry:
            code = connection.device_registry[base_name]['code']
            # NFR4 Format: BASE_ID:COMMAND
            cmd = f"{code}:{state}" 
            connection.device_registry[base_name]['pending_cmd'] = cmd
            
            # Updated to 3 Nodes (NFR4/Consistency)
            for n in range(1, 4):
                connection.device_registry[base_name]['nodes'][n] = state
            
            status_ref = db.reference(f'/status/{base_name}/nodes')
            payload = {f"node_{i}": state for i in range(1, 4)}
            status_ref.update(payload)
            return True
    return False

def queue_node_power(base_name, node_num, state):
    state = state.upper()
    with connection.registry_lock:
        if base_name in connection.device_registry:
            code = connection.device_registry[base_name]['code']
            # NFR4 Format: BASE_ID:NODE_X_STATE
            cmd = f"{code}:NODE_{node_num}_{state}"
            
            connection.device_registry[base_name]['pending_cmd'] = cmd
            connection.device_registry[base_name]['nodes'][node_num] = state

            #status_ref = db.reference(f'/status/{base_name}/nodes')
            #status_ref.update({str(node_num): state})
            return True
    return False
