import socket
import threading
import json
import time
from PyQt5.QtCore import QObject, pyqtSignal, QThread

class NetworkMessage:
    # Message types
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"
    GAME_STATE = "GAME_STATE"
    ACTION = "ACTION"
    TURN_CHANGE = "TURN_CHANGE"
    CHAT = "CHAT"
    ERROR = "ERROR"
    
    def __init__(self, msg_type, data=None):
        self.type = msg_type
        self.data = data if data is not None else {}
        self.timestamp = time.time()
    
    def to_json(self):
        return json.dumps({
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp
        })
    
    @staticmethod
    def from_json(json_str):
        try:
            data = json.loads(json_str)
            return NetworkMessage(data["type"], data["data"])
        except (json.JSONDecodeError, KeyError):
            return NetworkMessage(NetworkMessage.ERROR, {"message": "Invalid message format"})


class NetworkManager(QObject):
    # Define signals
    connected = pyqtSignal(bool, str)  # success, message
    disconnected = pyqtSignal(str)     # message
    message_received = pyqtSignal(object)  # NetworkMessage object
    error = pyqtSignal(str)            # error message
    
    def __init__(self):
        super().__init__()
        self.server_socket = None
        self.client_socket = None
        self.is_server = False
        self.is_connected = False
        self.client_thread = None
        self.server_thread = None
        self.clients = []  # Only used by server
        
    def start_server(self, host, port):
        """Start a server that listens for client connections"""
        if self.is_connected:
            self.error.emit("Already connected")
            return
        
        self.is_server = True
        
        def server_thread_func():
            try:
                # Create a TCP/IP socket
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                # Bind the socket to the port
                self.server_socket.bind((host, port))
                
                # Listen for incoming connections
                self.server_socket.listen(1)  # Only one client for this game
                self.connected.emit(True, f"Server started on {host}:{port}")
                self.is_connected = True
                
                # Wait for a connection
                self.client_socket, client_address = self.server_socket.accept()
                self.clients.append(self.client_socket)
                self.message_received.emit(NetworkMessage(
                    NetworkMessage.CONNECT, 
                    {"address": client_address[0], "port": client_address[1]}
                ))
                
                # Start listening for messages from this client
                threading.Thread(target=self._listen_for_messages, 
                                args=(self.client_socket,), 
                                daemon=True).start()
                
            except socket.error as e:
                self.error.emit(f"Server error: {str(e)}")
                self.stop()
        
        # Start server in a separate thread
        self.server_thread = threading.Thread(target=server_thread_func, daemon=True)
        self.server_thread.start()
    
    def connect_to_server(self, host, port):
        """Connect to a server as a client"""
        if self.is_connected:
            self.error.emit("Already connected")
            return
            
        self.is_server = False
        
        def client_thread_func():
            try:
                # Create a TCP/IP socket
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                
                # Connect the socket to the server
                self.client_socket.connect((host, port))
                self.is_connected = True
                self.connected.emit(True, f"Connected to server at {host}:{port}")
                
                # Start listening for messages from the server
                self._listen_for_messages(self.client_socket)
                
            except socket.error as e:
                self.error.emit(f"Client error: {str(e)}")
                self.connected.emit(False, f"Failed to connect: {str(e)}")
                self.stop()
        
        # Start client in a separate thread
        self.client_thread = threading.Thread(target=client_thread_func, daemon=True)
        self.client_thread.start()
    
    def _listen_for_messages(self, sock):
        """Listen for messages from a socket"""
        try:
            # Continuously receive data until the connection is closed
            buffer = ""
            while True:
                data = sock.recv(4096).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                
                # Process complete messages (assuming JSON messages are separated by newlines)
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    try:
                        network_message = NetworkMessage.from_json(message)
                        self.message_received.emit(network_message)
                    except Exception as e:
                        self.error.emit(f"Error processing message: {str(e)}")
        
        except socket.error as e:
            if self.is_connected:  # Only report error if we were connected
                self.error.emit(f"Connection error: {str(e)}")
        
        finally:
            # If we get here, the connection has been closed
            if sock in self.clients:
                self.clients.remove(sock)
            
            if sock == self.client_socket:
                self.client_socket = None
            
            self.disconnected.emit("Connection closed")
            self.is_connected = False
    
    def send_message(self, message):
        """Send a message to the connected client/server"""
        if not self.is_connected:
            self.error.emit("Not connected")
            return False
        
        try:
            if self.is_server:
                # Send to all connected clients
                if not self.clients:
                    self.error.emit("No connected clients")
                    return False
                
                for client in self.clients:
                    client.sendall((message.to_json() + '\n').encode('utf-8'))
            else:
                # Send to server
                if not self.client_socket:
                    self.error.emit("Not connected to server")
                    return False
                
                self.client_socket.sendall((message.to_json() + '\n').encode('utf-8'))
            
            return True
        except socket.error as e:
            self.error.emit(f"Send error: {str(e)}")
            return False
    
    def broadcast_game_state(self, game_state):
        """Send the current game state to all connected clients"""
        message = NetworkMessage(NetworkMessage.GAME_STATE, game_state)
        return self.send_message(message)
    
    def send_action(self, action_data):
        """Send an action to the server/client"""
        message = NetworkMessage(NetworkMessage.ACTION, action_data)
        return self.send_message(message)
    
    def send_turn_change(self, next_turn):
        """Notify the other player about a turn change"""
        message = NetworkMessage(NetworkMessage.TURN_CHANGE, {"next_turn": next_turn})
        return self.send_message(message)
    
    def stop(self):
        """Close all connections and stop the network manager"""
        self.is_connected = False
        
        # Close client socket if exists
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        
        # Close all client connections if server
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        self.clients = []
        
        # Close server socket if exists
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        self.disconnected.emit("Network manager stopped")
