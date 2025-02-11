import socket
import time

import lib.Common.Utils.Log as Log

def check_udp_port_is_open(target, port, timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((target, int(port)))
        s.shutdown(socket.SHUT_RDWR)
        return True
    except: #TODO: Add to Handle timeouts returning None
        return False
    finally:
        s.close()

def check_tcp_port_is_open(target, port, timeout):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex((target, int(port)))
    sock.close()
    Log.logger.debug(f"Attempting to do TCP connect to {target} at port {port} with timeout {timeout} with response {result}")

    if result == 0:
        return True
    elif result == 110: # Timeout
        return None
    else:
        return False

def check_port_is_opened(target, port, protocol, timeout, delay=3, retries=1):
    import socket

    for i in range(retries):
        if protocol == "tcp":
            port_is_opened = check_tcp_port_is_open(target, port, timeout)
        elif protocol == "udp":
            port_is_opened = check_udp_port_is_open(target, port, timeout)
        else:
            raise ValueError(f"Unknown protocol {protocol}")
        Log.logger.debug(f"Result for healtcheck is {port_is_opened}")

        if port_is_opened is not None:
            return port_is_opened
        elif i < retries - 1:
            Log.logger.debug(f"Target {target} has port {port} of protocol {protocol} closed, will try again after {delay} seconds")
            time.sleep(delay)

    return False

def check_os_name_and_port(os_name, os_flavor):
    # Check os_name
    if len(os_name) > 20 and os_name.count(' ') < 2:
        Log.logger.warn(f"Bad os_name {os_name} will default to unknown")
        os_name = "unknown"

    # Check os_flavor
    if len(os_flavor) > 20 and os_flavor.count(' ') < 2:
        Log.logger.warn(f"Bad os_flavor {os_flavor} will default to unknown")
        os_flavor = "unknown"

    return os_name, os_flavor

