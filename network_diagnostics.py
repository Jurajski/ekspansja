import socket
import subprocess
import platform
import threading
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QPushButton, QTextEdit, QLineEdit, QFormLayout, 
                           QGroupBox, QProgressBar, QComboBox, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

class NetworkTester(QThread):
    """Thread for running network tests"""
    update_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, host, port, test_type="ping"):
        super().__init__()
        self.host = host
        self.port = port
        self.test_type = test_type
        self.running = False
        
    def run(self):
        self.running = True
        
        if self.test_type == "ping":
            self.test_ping()
        elif self.test_type == "connection":
            self.test_connection()
        elif self.test_type == "port":
            self.test_port()
        
        self.running = False
        
    def test_ping(self):
        """Test if the host is reachable via ping"""
        self.update_signal.emit(f"Starting ping test to {self.host}...")
        
        try:
            # Determine the correct ping command based on platform
            system = platform.system().lower()
            
            if system == "windows":
                ping_cmd = ["ping", "-n", "4", self.host]
            else:  # Linux, macOS, etc.
                ping_cmd = ["ping", "-c", "4", self.host]
                
            self.update_signal.emit(f"Running: {' '.join(ping_cmd)}")
            
            # Run the ping command
            process = subprocess.Popen(
                ping_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Get output
            stdout, stderr = process.communicate()
            
            # Check results
            if process.returncode == 0:
                self.update_signal.emit(f"Ping successful!\n{stdout}")
                self.finished_signal.emit(True, "Ping test successful")
            else:
                self.update_signal.emit(f"Ping failed with return code {process.returncode}.\n{stdout}\n{stderr}")
                self.finished_signal.emit(False, f"Ping test failed: {stderr}")
                
        except Exception as e:
            self.update_signal.emit(f"Error during ping test: {str(e)}")
            self.finished_signal.emit(False, f"Ping test error: {str(e)}")
            
    def test_connection(self):
        """Test basic TCP connection to the host"""
        self.update_signal.emit(f"Testing connection to {self.host}...")
        
        try:
            # Try to resolve the hostname
            self.update_signal.emit(f"Resolving hostname {self.host}...")
            ip_address = socket.gethostbyname(self.host)
            self.update_signal.emit(f"Hostname resolved: {ip_address}")
            
            # Try to connect to the host on common ports
            test_ports = [80, 443, 8080]
            connected = False
            
            for test_port in test_ports:
                try:
                    self.update_signal.emit(f"Testing connection to {ip_address}:{test_port}...")
                    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    test_socket.settimeout(3)
                    result = test_socket.connect_ex((ip_address, test_port))
                    test_socket.close()
                    
                    if result == 0:
                        self.update_signal.emit(f"Successfully connected to {ip_address}:{test_port}")
                        connected = True
                        break
                    else:
                        self.update_signal.emit(f"Could not connect to {ip_address}:{test_port} (Error: {result})")
                except Exception as e:
                    self.update_signal.emit(f"Error testing port {test_port}: {str(e)}")
            
            if connected:
                self.finished_signal.emit(True, "Connection test successful")
            else:
                self.update_signal.emit("Could not connect to any test port.")
                self.finished_signal.emit(False, "Connection test failed")
                
        except Exception as e:
            self.update_signal.emit(f"Error during connection test: {str(e)}")
            self.finished_signal.emit(False, f"Connection test error: {str(e)}")
    
    def test_port(self):
        """Test if the specific port is open on the host"""
        self.update_signal.emit(f"Testing if port {self.port} is open on {self.host}...")
        
        try:
            # Try to connect to the specific port
            self.update_signal.emit(f"Attempting to connect to {self.host}:{self.port}...")
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(3)
            
            # Get host's IP address
            try:
                ip_address = socket.gethostbyname(self.host)
                self.update_signal.emit(f"Hostname resolved: {ip_address}")
            except:
                # If resolution fails, use the host directly (might be an IP already)
                ip_address = self.host
                self.update_signal.emit(f"Using IP address directly: {ip_address}")
            
            # Try to connect
            result = test_socket.connect_ex((ip_address, self.port))
            test_socket.close()
            
            if result == 0:
                self.update_signal.emit(f"Success! Port {self.port} is open on {self.host}")
                self.finished_signal.emit(True, f"Port {self.port} is open")
            else:
                error_msg = self.get_socket_error_message(result)
                self.update_signal.emit(f"Failed! Port {self.port} is not accessible on {self.host} (Error: {result} - {error_msg})")
                self.finished_signal.emit(False, f"Port test failed: {error_msg}")
                
        except Exception as e:
            self.update_signal.emit(f"Error during port test: {str(e)}")
            self.finished_signal.emit(False, f"Port test error: {str(e)}")
    
    def get_socket_error_message(self, error_code):
        """Convert socket error code to readable message"""
        error_messages = {
            10061: "Connection refused (server not running)",
            10060: "Connection timed out",
            10049: "Cannot assign requested address",
            10035: "Resource temporarily unavailable",
            10051: "Network is unreachable",
            10065: "No route to host",
            111: "Connection refused (Linux)",
            113: "No route to host (Linux)",
            115: "Operation now in progress (Linux)",
        }
        
        return error_messages.get(error_code, f"Unknown error code: {error_code}")

class NetworkDiagnosticsDialog(QDialog):
    """Dialog for diagnosing network connection issues"""
    
    def __init__(self, parent=None, host="127.0.0.1", port=5000):
        super().__init__(parent)
        self.setWindowTitle("Network Diagnostics")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        self.host = host
        self.port = port
        self.network_tester = None
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Target settings
        target_group = QGroupBox("Target")
        target_layout = QFormLayout()
        
        # Host input
        self.host_input = QLineEdit(self.host)
        target_layout.addRow("Host:", self.host_input)
        
        # Port input
        self.port_input = QLineEdit(str(self.port))
        target_layout.addRow("Port:", self.port_input)
        
        # Test type selection
        self.test_type = QComboBox()
        self.test_type.addItems(["Ping Test", "Connection Test", "Port Test"])
        target_layout.addRow("Test Type:", self.test_type)
        
        target_group.setLayout(target_layout)
        layout.addWidget(target_group)
        
        # Test results area
        results_group = QGroupBox("Test Results")
        results_layout = QVBoxLayout()
        
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        results_layout.addWidget(self.results_text)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.hide()
        results_layout.addWidget(self.progress_bar)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.run_button = QPushButton("Run Test")
        self.run_button.clicked.connect(self.run_test)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def run_test(self):
        """Run the selected network test"""
        # Get current values
        self.host = self.host_input.text().strip()
        
        try:
            self.port = int(self.port_input.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid Port", "Port must be a number between 1-65535.")
            return
            
        if self.port < 1 or self.port > 65535:
            QMessageBox.warning(self, "Invalid Port", "Port must be between 1-65535.")
            return
            
        # Clear previous results
        self.results_text.clear()
        
        # Get test type
        test_index = self.test_type.currentIndex()
        test_types = ["ping", "connection", "port"]
        selected_test = test_types[test_index]
        
        # Disable UI during test
        self.run_button.setEnabled(False)
        self.progress_bar.show()
        
        # Create and start test thread
        self.network_tester = NetworkTester(self.host, self.port, selected_test)
        self.network_tester.update_signal.connect(self.update_results)
        self.network_tester.finished_signal.connect(self.test_finished)
        self.network_tester.start()
        
    def update_results(self, text):
        """Update the results text area"""
        self.results_text.append(text)
        # Auto-scroll to bottom
        scrollbar = self.results_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def test_finished(self, success, message):
        """Handle test completion"""
        # Re-enable UI
        self.run_button.setEnabled(True)
        self.progress_bar.hide()
        
        # Show test result
        result_color = "green" if success else "red"
        self.results_text.append(f"\n<span style='color:{result_color};font-weight:bold;'>Test completed: {message}</span>")
        
        # Recommendations if test failed
        if not success:
            self.results_text.append("\n<b>Recommendations:</b>")
            
            if "Connection refused" in message or "Port test failed" in message:
                self.results_text.append("• Make sure the server application is running")
                self.results_text.append("• Check if a firewall is blocking the connection")
                self.results_text.append("• Verify the port number is correct")
                self.results_text.append("• Try temporarily disabling Windows Defender Firewall")
                self.results_text.append("• Make sure the port is not blocked by antivirus software")
            
            elif "Ping test failed" in message:
                self.results_text.append("• Check if the host is online")
                self.results_text.append("• Verify your internet connection")
                self.results_text.append("• Some servers may block ping requests")
                self.results_text.append("• Check Windows Firewall settings")
            
            else:
                self.results_text.append("• Verify the hostname/IP address is correct")
                self.results_text.append("• Check your internet connection")
                self.results_text.append("• Try with a different port number")
                
            self.results_text.append("• If you're behind a router, ensure port forwarding is configured properly")
            self.results_text.append("• Windows error code 10061 typically means the server is not running or listening on that port")
            
            if "error code: 800" in message.lower():
                self.results_text.append("\n<b>Error 800:</b>")
                self.results_text.append("• This error is typically related to Windows Socket initialization problems")
                self.results_text.append("• Try restarting your computer")
                self.results_text.append("• Check for network adapter driver updates")
                self.results_text.append("• Run 'netsh winsock reset' in an Administrator Command Prompt")
