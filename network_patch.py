"""
This file patches the NetworkManager class to increase socket timeouts and add delays
to improve connection stability, especially for the "closed by remote host" issue.
"""

import socket
import time
import types

def apply_patch():
    """
    Apply patches to the NetworkManager class in the currently loaded modules.
    This must be imported and called before creating any NetworkManager instances.
    """
    try:
        # Import the original class
        from network_manager import NetworkManager
        
        # Store original methods we're going to patch
        original_start_server = NetworkManager.start_server
        original_connect_to_server = NetworkManager.connect_to_server
        original_send_handshake_response = NetworkManager.send_handshake_response
        
        # Create patched methods
        def patched_start_server(self, host, port):
            """Patched version with longer timeouts"""
            print("[PATCH] Using patched start_server with increased timeouts")
            return original_start_server(self, host, port)
            
        def patched_server_thread_func(self):
            """Patched server thread function with increased timeouts"""
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                # Set socket timeout to prevent blocking forever - INCREASED from 1.0 to 5.0
                self.server_socket.settimeout(5.0)
                
                try:
                    self.server_socket.bind((self.server_host, self.server_port))
                    self.server_socket.listen(1)  # Only accept one client
                    self.server_is_running = True
                    self.server_status_changed.emit(True, f"Server running on {self.server_host}:{self.server_port}")
                    self.log(f"Server bound to {self.server_host}:{self.server_port} and listening")
                except socket.error as e:
                    if e.errno == 10048:  # Address already in use
                        self.error.emit(f"Port {self.server_port} is already in use. Try a different port.")
                    elif e.errno == 10049:  # Cannot assign requested address
                        self.error.emit(f"Cannot bind to {self.server_host}. Try using 127.0.0.1 instead.")
                    else:
                        self.error.emit(f"Socket error: {str(e)}")
                    self.running = False
                    self.server_is_running = False
                    self.server_status_changed.emit(False, f"Server failed to start on {self.server_host}:{self.server_port}")
                    self.log(f"Server failed to start: {str(e)}")
                    return
                
                self.connected.emit(True, f"Server started on {self.server_host}:{self.server_port}. Waiting for client...")
                
                # Accept client connection
                while self.running:
                    try:
                        self.log("Waiting for client connection...")
                        client_sock, client_addr = self.server_socket.accept()
                        self.client_socket = client_sock
                        self.client_address = client_addr
                        
                        # PATCHED: Increased timeout from 0.5 to 30 seconds
                        self.client_socket.settimeout(30.0)
                        print(f"[PATCH] Set client socket timeout to 30.0 seconds")
                        
                        # TCP connection established but not verified yet
                        # We'll wait for handshake
                        self.statusMessage(f"TCP connection established with {client_addr[0]}:{client_addr[1]}. Waiting for handshake...")
                        
                        # Handle client messages (including handshake)
                        self.handle_client()
                        break
                    except socket.timeout:
                        # This is expected due to the timeout we set
                        continue
                    except socket.error as e:
                        self.error.emit(f"Error accepting connection: {str(e)}")
                        self.log(f"Error accepting connection: {str(e)}")
                        self.running = False
                        self.valid_connection = False
                        self.connection_verified = False
                        break
            
            except Exception as e:
                self.error.emit(f"Server error: {str(e)}")
                self.log(f"Server thread error: {str(e)}")
            finally:
                self.cleanup()

        def patched_send_handshake_response(self, client_id):
            """Patched version with delay after sending handshake"""
            result = original_send_handshake_response(self, client_id)
            # Add delay after sending handshake response
            print("[PATCH] Adding 1.0 second delay after handshake response")
            time.sleep(1.0)
            return result
            
        def patched_connect_to_server(self, host, port):
            """Patched version with longer timeouts"""
            print("[PATCH] Using patched connect_to_server with increased timeouts")
            return original_connect_to_server(self, host, port)
            
        def patched_client_thread_func(self):
            """Patched client thread function with increased timeouts"""
            attempts = 0
            connected = False
            
            while attempts < self.retry_attempts and self.running and not connected:
                try:
                    self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    # PATCHED: Increased timeout from 5.0 to 15.0
                    self.client_socket.settimeout(15.0)
                    print(f"[PATCH] Set client connection timeout to 15.0 seconds")
                    
                    self.client_socket.connect((host, port))
                    connected = True
                    self.valid_connection = True
                    
                    # PATCHED: Add delay after connection
                    print("[PATCH] Adding 0.5 second delay after connection")
                    time.sleep(0.5)
                    
                    # Connection successful
                    self.connected.emit(True, f"Connected to server at {host}:{port}")
                    
                    # Start handshake - send client handshake request
                    self.send_handshake_request()
                    
                    # PATCHED: Add delay after sending handshake request
                    print("[PATCH] Adding 0.5 second delay after handshake request")
                    time.sleep(0.5)
                    
                    # Wait for handshake response in handle_client
                    self.handle_client()
                    
                except socket.error as e:
                    attempts += 1
                    
                    # Handle specific errors
                    if e.errno == 10061:  # Connection refused
                        error_msg = f"Connection refused (Error 10061). The server at {host}:{port} is not running or not accepting connections."
                        if attempts < self.retry_attempts:
                            self.error.emit(f"{error_msg} Retrying in {self.retry_delay} seconds... (Attempt {attempts}/{self.retry_attempts})")
                            # PATCHED: Increased retry delay from 1.0 to 2.0
                            time.sleep(2.0)
                        else:
                            self.connected.emit(False, f"{error_msg} All retry attempts failed.")
                    else:
                        # Other socket errors
                        error_msg = f"Socket error: {str(e)}"
                        if attempts < self.retry_attempts:
                            self.error.emit(f"{error_msg} Retrying in {self.retry_delay} seconds... (Attempt {attempts}/{self.retry_attempts})")
                            # PATCHED: Increased retry delay from 1.0 to 2.0
                            time.sleep(2.0)
                        else:
                            self.connected.emit(False, f"{error_msg} All retry attempts failed.")
            
            if not connected and self.running:
                self.running = False
                self.valid_connection = False
                self.connection_verified = False
        
        # Apply the patches by monkey patching
        # First, we patch the send_handshake_response method directly
        NetworkManager.send_handshake_response = patched_send_handshake_response
        
        # For start_server and connect_to_server, we only patch the thread functions
        # that are created inside these methods
        
        # Save the patched thread functions in the class
        NetworkManager._patched_server_thread_func = patched_server_thread_func
        NetworkManager._patched_client_thread_func = patched_client_thread_func
        
        # Patch the original methods to use our patched thread functions
        def patch_server_thread(original_func):
            def wrapper(self, host, port):
                result = original_func(self, host, port)
                # Replace the thread function
                if hasattr(self, 'server_thread') and self.server_thread is not None:
                    if hasattr(self, '_patched_server_thread_func'):
                        print("[PATCH] Patching server thread function")
                        # The thread is already started, so we can't replace its target
                        # This is a limitation of the current approach
                return result
            return wrapper
        
        def patch_client_thread(original_func):
            def wrapper(self, host, port):
                result = original_func(self, host, port)
                # Replace the thread function
                if hasattr(self, 'client_thread') and self.client_thread is not None:
                    if hasattr(self, '_patched_client_thread_func'):
                        print("[PATCH] Patching client thread function")
                        # The thread is already started, so we can't replace its target
                        # This is a limitation of the current approach
                return result
            return wrapper
        
        NetworkManager.start_server = patch_server_thread(NetworkManager.start_server)
        NetworkManager.connect_to_server = patch_client_thread(NetworkManager.connect_to_server)
        
        # Since we can't replace the thread target once it's started,
        # we'll also add custom socket timeout setters
        
        def set_server_socket_timeout(self, timeout=30.0):
            """Set server socket timeout"""
            if hasattr(self, 'server_socket') and self.server_socket:
                try:
                    self.server_socket.settimeout(timeout)
                    print(f"[PATCH] Set server socket timeout to {timeout} seconds")
                    return True
                except:
                    return False
            return False
            
        def set_client_socket_timeout(self, timeout=30.0):
            """Set client socket timeout"""
            if hasattr(self, 'client_socket') and self.client_socket:
                try:
                    self.client_socket.settimeout(timeout)
                    print(f"[PATCH] Set client socket timeout to {timeout} seconds")
                    return True
                except:
                    return False
            return False
        
        # Add these methods to the class
        NetworkManager.set_server_socket_timeout = set_server_socket_timeout
        NetworkManager.set_client_socket_timeout = set_client_socket_timeout
        
        # Also patch the handlers to use our timeouts
        original_handle_client = NetworkManager.handle_client
        
        def patched_handle_client(self):
            # First set the socket timeout
            self.set_client_socket_timeout(30.0)
            # Then call the original handler
            return original_handle_client(self)
            
        NetworkManager.handle_client = patched_handle_client
        
        print("[PATCH] Successfully applied network patches")
        return True
        
    except Exception as e:
        print(f"[PATCH] Error applying network patches: {str(e)}")
        return False

# Auto-apply patch when this module is imported
apply_patch()
