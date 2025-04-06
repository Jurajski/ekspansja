from PyQt5.QtCore import QObject, QTimer, pyqtSignal
import logging
import time

class GameHistoryRecorder(QObject):
    """Records and manages game history"""
    
    playback_finished = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.history = []
        self.is_recording = True
        self.playback_index = 0
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.play_next_move)
    
    def clear_history(self):
        """Clear all recorded history"""
        self.history = []
    
    def record_move(self, move_type, data):
        """Record a game move
        
        Args:
            move_type: String type of move (e.g., 'connect', 'disconnect', 'transfer')
            data: Dictionary containing move details
        """
        if not self.is_recording:
            return
            
        move = {
            "type": move_type,
            **data
        }
        self.history.append(move)
    
    def record_connection(self, unit1_id, unit2_id):
        """Record a connection between two units"""
        self.record_move("connect", {
            "from_id": unit1_id,
            "to_id": unit2_id
        })
    
    def record_disconnect(self, unit1_id, unit2_id):
        """Record a disconnection between two units"""
        self.record_move("disconnect", {
            "from_id": unit1_id,
            "to_id": unit2_id
        })
    
    def record_turn_switch(self, current_turn):
        """Record a turn switch"""
        self.record_move("turn_switch", {
            "turn": current_turn
        })
    
    def record_unit_change(self, unit_id, changes):
        """Record changes to a unit"""
        self.record_move("unit_change", {
            "unit_id": unit_id,
            **changes
        })
    
    def get_history(self):
        """Get the complete history"""
        return self.history
    
    def load_history(self, history):
        """Load a previously saved history"""
        self.history = history
    
    def start_playback(self, main_window, speed=1.0):
        """Start playback of recorded history"""
        if not self.history:
            main_window.statusBar().showMessage("No history to play back!")
            self.playback_finished.emit()
            return
            
        self.is_recording = False
        self.playback_index = 0
        self.main_window = main_window
        self.error_count = 0
        self.move_count = len(self.history)
        
        # Reset the game to initial state and prepare for playback
        self.main_window.reset_level()
        self.main_window.prepare_for_playback()
        
        # Calculate interval based on speed (default interval is 1000ms)
        interval = int(1000 / speed)
        main_window.statusBar().showMessage(f"Starting playback with {len(self.history)} moves at {speed}x speed")
        
        # Use a single-shot timer for the first move to allow UI to update
        QTimer.singleShot(500, self.play_next_move)
        self.playback_timer.setInterval(interval)
    
    def play_next_move(self):
        """Play the next move in the history"""
        if self.playback_index >= len(self.history):
            self.playback_timer.stop()
            self.is_recording = True
            self.main_window.statusBar().showMessage(f"Playback complete: {self.playback_index} moves played, {self.error_count} errors")
            self.playback_finished.emit()
            return
        
        try:
            move = self.history[self.playback_index]
            success = self.execute_move(move)
            
            if not success:
                self.error_count += 1
                if self.error_count > 10:  # Stop if too many errors
                    self.playback_timer.stop()
                    self.main_window.statusBar().showMessage(f"Too many errors, playback stopped at move {self.playback_index}")
                    self.is_recording = True
                    self.playback_finished.emit()
                    return
            
            self.playback_index += 1
            
            # Update status message every few moves
            if self.playback_index % 5 == 0 or self.playback_index == 1:
                self.main_window.statusBar().showMessage(
                    f"Playing move {self.playback_index}/{len(self.history)}"
                )
                
            # Start the timer for subsequent moves if it's not already running
            if not self.playback_timer.isActive():
                self.playback_timer.start()
                
        except Exception as e:
            logging.error(f"Error during playback: {e}")
            self.main_window.statusBar().showMessage(f"Playback error: {str(e)}")
            self.error_count += 1
            if self.error_count > 10:
                self.playback_timer.stop()
                self.is_recording = True
                self.playback_finished.emit()
                return
                
            # Continue with next move despite error
            self.playback_index += 1
            
            # If timer not running (single shot), start it
            if not self.playback_timer.isActive():
                self.playback_timer.start()
    
    def execute_move(self, move):
        """Execute a move during playback
        
        Returns:
            bool: True if move was executed successfully
        """
        move_type = move.get("type")
        
        try:
            if move_type == "connect":
                # Get position-based unit IDs for more reliable mapping
                from_id = int(float(move.get("from_id", 0)))
                to_id = int(float(move.get("to_id", 0)))
                return self.main_window.execute_connection(from_id, to_id)
            elif move_type == "disconnect":
                from_id = int(float(move.get("from_id", 0)))
                to_id = int(float(move.get("to_id", 0)))
                return self.main_window.execute_disconnection(from_id, to_id)
            elif move_type == "turn_switch":
                self.main_window.current_turn = str(move.get("turn", "player"))
                self.main_window.start_turn()
                return True
            elif move_type == "unit_change":
                unit_id = int(float(move.get("unit_id", 0)))
                return self.main_window.update_unit(unit_id, move)
            return False
        except Exception as e:
            logging.error(f"Error executing move {move_type}: {e}")
            return False
    
    def stop_playback(self):
        """Stop the current playback"""
        if self.playback_timer.isActive():
            self.playback_timer.stop()
            self.is_recording = True
