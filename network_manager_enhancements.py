"""
This file contains instructions for enhancing the NetworkManager class.
To apply these changes, add the following to your NetworkManager class:

1. In NetworkManager.__init__(), add:
   self.connection_age = 0
   self.connection_start_time = 0
   
2. In the method where connections are established (likely in connect_to_server or when a client connects), add:
   self.connection_start_time = time.time()
   self.connection_age = 0
   
3. Start a timer to periodically update the connection age:
   # At the end of __init__
   self.age_timer = QTimer()
   self.age_timer.timeout.connect(self.update_connection_age)
   self.age_timer.start(1000)  # Update every second

4. Add the update_connection_age method:
   def update_connection_age(self):
       if self.valid_connection and self.connection_start_time > 0:
           self.connection_age = time.time() - self.connection_start_time

5. When stopping connections, reset the timer:
   # In stop() method
   self.connection_start_time = 0
   self.connection_age = 0
"""

import time
from PyQt5.QtCore import QTimer

def enhance_network_manager(network_manager):
    """
    Apply enhancements to an existing NetworkManager instance
    """
    network_manager.connection_age = 0
    network_manager.connection_start_time = 0
    
    # Create a method to update connection age
    def update_connection_age(self):
        if hasattr(self, 'valid_connection') and self.valid_connection and self.connection_start_time > 0:
            self.connection_age = time.time() - self.connection_start_time
    
    # Add the method to the network manager
    network_manager.update_connection_age = update_connection_age.__get__(network_manager)
    
    # Create and start the age timer
    age_timer = QTimer()
    age_timer.timeout.connect(network_manager.update_connection_age)
    age_timer.start(1000)
    
    # Store the timer
    network_manager.age_timer = age_timer
    
    # Mark connection start time
    network_manager.connection_start_time = time.time() if hasattr(network_manager, 'valid_connection') and network_manager.valid_connection else 0
    
    print("NetworkManager enhanced with connection age tracking")
    
    return network_manager
