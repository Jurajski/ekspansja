import socket
import threading
import json
import time
import uuid
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

class NetworkMessage:
    """Message types for network communication"""
    CONNECT = 1
    DISCONNECT = 2
    GAME_STATE = 3
    ACTION = 4
    TURN_CHANGE = 5
    HANDSHAKE_REQUEST = 6
    HANDSHAKE_RESPONSE = 7
    ERROR = 99
    def __init__(self, msg_type, data=None):
        self.type = msg_type
        self.data = data or {}
        
    def to_json(self):
        return json.dumps({
            "type": self.type,
            "data": self.data
        })
    
    @staticmethod
    def from_json(json_str):
        try:
            msg_dict = json.loads(json_str)
            return NetworkMessage(msg_dict["type"], msg_dict["data"])
        except (json.JSONDecodeError, KeyError):
            return NetworkMessage(NetworkMessage.ERROR, {"error": "Invalid message format"})

class NetworkManager(QObject):
    """Handles network communication for multiplayer games"""
    
    # Define signals
    connected = pyqtSignal(bool, str)  # success, message
    disconnected = pyqtSignal(str)  # message
    message_received = pyqtSignal(object)  # NetworkMessage object
    error = pyqtSignal(str)  # error message
    server_status_changed = pyqtSignal(bool, str)  # is_running, status_message
    
    def __init__(self):
        super().__init__()
        self.server_socket = None
        self.client_socket = None
        self.client_address = None
        self.server_thread = None
        self.client_thread = None
        self.running = False
        self.buffer_size = 4096
        self.retry_attempts = 3
        self.retry_delay = 1.0  # seconds
        self.server_is_running = False
        self.server_host = "127.0.0.1"
        self.server_port = 5000
        self.valid_connection = False  # Track if we have a valid connection
        self.connection_processed = False  # Track if we've already processed the connection
        
        # Connection state tracking
        self.handshake_completed = False
        self.connection_verified = False
        self.connection_id = str(uuid.uuid4())[:8]  # Shorter unique ID
        
        self.debug_mode = True  # Enable console logging
        
        # Initialize the server status timer
        self.server_status_timer = QTimer(self)
        self.server_status_timer.timeout.connect(self.check_server_status)
    
    def log(self, message):
        """Log messages to console for debugging"""
        if self.debug_mode:
            print(f"[NETWORK] {message}")
    
    def start_server(self, host, port):
        """Start a server to accept client connections"""
        if self.running:
            self.stop()
            
        self.running = True
        self.server_host = host
        self.server_port = port
        self.valid_connection = False
        self.connection_processed = False
        self.handshake_completed = False
        self.connection_verified = False
        
        self.log(f"Starting server on {host}:{port}")
        
        def server_thread_func():
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                # Set socket timeout to prevent blocking forever
                self.server_socket.settimeout(1.0)
                
                try:
                    self.server_socket.bind((host, port))
                    self.server_socket.listen(1)  # Only accept one client
                    self.server_is_running = True
                    self.server_status_changed.emit(True, f"Server running on {host}:{port}")
                    self.log(f"Server bound to {host}:{port} and listening")
                except socket.error as e:
                    if e.errno == 10048:  # Address already in use
                        self.error.emit(f"Port {port} is already in use. Try a different port.")
                    elif e.errno == 10049:  # Cannot assign requested address
                        self.error.emit(f"Cannot bind to {host}. Try using 127.0.0.1 instead.")
                    else:
                        self.error.emit(f"Socket error: {str(e)}")
                    self.running = False
                    self.server_is_running = False
                    self.server_status_changed.emit(False, f"Server failed to start on {host}:{port}")
                    self.log(f"Server failed to start: {str(e)}")
                    return
                
                self.connected.emit(True, f"Server started on {host}:{port}. Waiting for client...")
                
                # Accept client connection
                while self.running:
                    try:
                        self.log("Waiting for client connection...")
                        client_sock, client_addr = self.server_socket.accept()
                        self.client_socket = client_sock
                        self.client_address = client_addr
                        
                        # Set client socket timeout
                        self.client_socket.settimeout(0.5)
                        
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
        
        self.server_thread = threading.Thread(target=server_thread_func)
        self.server_thread.daemon = True
        self.server_thread.start()
    
    def connect_to_server(self, host, port):
        """Connect to a server as a client"""
        if self.running:
            self.stop()
            
        self.running = True
        self.server_host = host
        self.server_port = port
        self.valid_connection = False
        self.connection_processed = False
        self.handshake_completed = False
        self.connection_verified = False
        
        self.log(f"Attempting to connect to server at {host}:{port}")
        
        def client_thread_func():
            attempts = 0
            connected = False
            
            while attempts < self.retry_attempts and self.running and not connected:
                try:
                    self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.client_socket.settimeout(5.0)  # 5 second timeout for connection
                    
                    self.client_socket.connect((host, port))
                    connected = True
                    self.valid_connection = True
                    
                    # Connection successful
                    self.connected.emit(True, f"Connected to server at {host}:{port}")
                    
                    # Start handshake - send client handshake request
                    self.send_handshake_request()
                    
                    # Wait for handshake response in handle_client
                    self.handle_client()
                    
                except socket.error as e:
                    attempts += 1
                    
                    # Handle specific errors
                    if e.errno == 10061:  # Connection refused
                        error_msg = f"Connection refused (Error 10061). The server at {host}:{port} is not running or not accepting connections."
                        if attempts < self.retry_attempts:
                            self.error.emit(f"{error_msg} Retrying in {self.retry_delay} seconds... (Attempt {attempts}/{self.retry_attempts})")
                            time.sleep(self.retry_delay)
                        else:
                            self.connected.emit(False, f"{error_msg} All retry attempts failed.")
                    else:
                        # Other socket errors
                        error_msg = f"Socket error: {str(e)}"
                        if attempts < self.retry_attempts:
                            self.error.emit(f"{error_msg} Retrying in {self.retry_delay} seconds... (Attempt {attempts}/{self.retry_attempts})")
                            time.sleep(self.retry_delay)
                        else:
                            self.connected.emit(False, f"{error_msg} All retry attempts failed.")
            
            if not connected and self.running:
                self.running = False
                self.valid_connection = False
                self.connection_verified = False
                
        self.client_thread = threading.Thread(target=client_thread_func)
        self.client_thread.daemon = True
        self.client_thread.start()
    
    def send_handshake_request(self):
        """Send a handshake request to establish a verified connection"""
        if not self.client_socket:
            return False
            
        try:
            # Create handshake request
            handshake_req = NetworkMessage(
                NetworkMessage.HANDSHAKE_REQUEST, 
                {"client_id": self.connection_id, "game": "ExpansionWar", "version": "1.0"}
            )
            
            # Send the handshake request
            data = handshake_req.to_json().encode('utf-8')
            self.client_socket.sendall(data)
            self.statusMessage("Handshake request sent...")
            return True
        except socket.error as e:
            self.error.emit(f"Error sending handshake request: {str(e)}")
            return False
    
    def send_handshake_response(self, client_id):
        """Send a handshake response to verify the connection"""
        if not self.client_socket:
            return False
            
        try:
            # Create handshake response
            handshake_resp = NetworkMessage(
                NetworkMessage.HANDSHAKE_RESPONSE, 
                {
                    "server_id": self.connection_id,
                    "client_id": client_id,
                    "status": "accepted",
                    "game": "ExpansionWar",
                    "version": "1.0"
                }
            )
            
            # Send the handshake response
            data = handshake_resp.to_json().encode('utf-8')
            self.client_socket.sendall(data)
            self.statusMessage("Handshake response sent...")
            return True
        except socket.error as e:
            self.error.emit(f"Error sending handshake response: {str(e)}")
            return False
    
    def handle_client(self):
        """Handle messages from client/server"""
        self.log("Starting message handler")
        
        while self.running and self.client_socket:
            try:
                # Try to receive data
                data = self.client_socket.recv(self.buffer_size)
                if not data:
                    # Connection closed
                    self.log("Connection closed by remote host (received empty data)")
                    self.disconnected.emit("Connection closed by remote host")
                    self.valid_connection = False
                    self.connection_processed = False
                    self.connection_verified = False
                    break
                
                # Process message
                try:
                    message_text = data.decode('utf-8')
                    self.log(f"Received data: {message_text[:50]}...")
                    message = NetworkMessage.from_json(message_text)
                    
                    # Handle special messages internally
                    if message.type == NetworkMessage.HANDSHAKE_REQUEST:
                        # Server receives handshake request from client
                        client_id = message.data.get("client_id", "unknown")
                        game = message.data.get("game", "unknown")
                        version = message.data.get("version", "unknown")
                        
                        # Validate game and version
                        if game != "ExpansionWar":
                            self.error.emit(f"Invalid game in handshake: {game}")
                            self.client_socket.close()
                            self.client_socket = None
                            break
                            
                        # Send back handshake response
                        self.statusMessage(f"Received handshake request from client {client_id}")
                        self.send_handshake_response(client_id)
                        
                        # Mark connection as validated
                        self.valid_connection = True
                        self.connection_verified = True
                        
                        # Wait a moment to ensure the response is sent before notifying
                        time.sleep(0.1)
                        
                        # Now notify about the real verified connection
                        if self.client_address:
                            self.message_received.emit(NetworkMessage(
                                NetworkMessage.CONNECT, 
                                {"address": self.client_address[0], "port": self.client_address[1], "client_id": client_id}
                            ))
                        
                    elif message.type == NetworkMessage.HANDSHAKE_RESPONSE:
                        # Client receives handshake response from server
                        server_id = message.data.get("server_id", "unknown")
                        client_id = message.data.get("client_id", "unknown")
                        status = message.data.get("status", "unknown")
                        
                        # Verify it's our handshake
                        if client_id != self.connection_id:
                            self.error.emit(f"Handshake error: Client ID mismatch")
                            self.client_socket.close()
                            self.client_socket = None
                            break
                            
                        # Check status
                        if status != "accepted":
                            self.error.emit(f"Handshake rejected by server: {status}")
                            self.client_socket.close()
                            self.client_socket = None
                            break
                            
                        # Mark connection as validated
                        self.statusMessage(f"Handshake accepted by server {server_id}")
                        self.valid_connection = True
                        self.connection_verified = True
                        self.handshake_completed = True
                        
                        # Notify about successful connection
                        self.connected.emit(True, f"Successfully connected and verified with server")
                        
                    else:
                        # Only pass messages along if connection is verified
                        if self.connection_verified:
                            self.message_received.emit(message)
                        else:
                            self.error.emit("Received message before connection verification was complete")
                        
                except Exception as e:
                    self.error.emit(f"Error processing message: {str(e)}")
                    self.log(f"Error processing message: {str(e)}")
                
            except socket.timeout:
                # This is expected due to the timeout we set
                continue
            except socket.error as e:
                if self.running:  # Only emit if we're still supposed to be running
                    self.error.emit(f"Socket error: {str(e)}")
                    self.log(f"Socket error in handle_client: {str(e)}")
                self.valid_connection = False
                self.connection_verified = False
                break
        
        self.log("Message handler ended")
    
    def send_message(self, message):
        """Send a message to the connected client/server"""
        if not self.client_socket or not self.valid_connection:
            self.error.emit("Not connected")
            return False
        
        self.log(f"Sending message: Type={message.type}")
        
        try:
            data = message.to_json().encode('utf-8')
            self.client_socket.sendall(data)
            # Add a small delay after sending to help with synchronization
            import time
            time.sleep(0.05)
            return True
        except socket.error as e:
            self.error.emit(f"Error sending message: {str(e)}")
            self.valid_connection = False
            return False
    
    def broadcast_game_state(self, game_state):
        """Send game state to the connected client"""
        message = NetworkMessage(NetworkMessage.GAME_STATE, game_state)
        return self.send_message(message)
    
    def send_action(self, action_data):
        """Send an action to the connected client/server"""
        message = NetworkMessage(NetworkMessage.ACTION, action_data)
        return self.send_message(message)
    
    def send_turn_change(self, next_turn):
        """Send turn change notification"""
        message = NetworkMessage(NetworkMessage.TURN_CHANGE, {"next_turn": next_turn})
        return self.send_message(message)
    
    def check_server_status(self, host=None, port=None):
        """Check if server is running and accessible"""
        if not host:
            host = self.server_host if hasattr(self, 'server_host') else "127.0.0.1"
        if not port:
            port = self.server_port if hasattr(self, 'server_port') else 5000
            
        try:
            # Create a socket to test connection
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(1.0)  # Short timeout for quick check
            
            # Try to connect
            result = test_socket.connect_ex((host, port))
            is_running = (result == 0)
            
            # Update status
            old_state = self.server_is_running
            self.server_is_running = is_running
            
            # Only emit if state changed
            if old_state != is_running:
                status = f"Server at {host}:{port} is {'running' if is_running else 'not running'}"
                self.server_status_changed.emit(is_running, status)
                
            test_socket.close()
            
            # Add logging
            if is_running:
                self.log(f"Server detected at {host}:{port}")
            else:
                self.log(f"No server detected at {host}:{port}")
                
            return is_running
            
        except Exception as e:
            self.server_is_running = False
            self.server_status_changed.emit(False, f"Error checking server status: {str(e)}")
            return False
    
    def start_server_status_monitor(self, host, port, interval=5000):
        """Start periodic server status monitoring"""
        self.server_host = host
        self.server_port = port
        self.server_status_timer.start(interval)
        # Do an immediate check
        self.check_server_status(host, port)
        
    def stop_server_status_monitor(self):
        """Stop server status monitoring"""
        if hasattr(self, 'server_status_timer') and self.server_status_timer.isActive():
            self.server_status_timer.stop()
    
    def stop(self):
        """Stop all network activities"""
        self.log("Stopping network manager")
        self.running = False
        self.valid_connection = False
        self.connection_processed = False
        self.connection_verified = False
        self.handshake_completed = False
        self.stop_server_status_monitor()
        self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
            
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
    
    def statusMessage(self, message):
        """Helper to log status messages (for debugging)"""
        # Uncomment to enable verbose logging:
        # print(f"[NetworkManager] {message}")
        pass

