"""
This module provides fixes for connection lines in network mode for Expansion War.

It contains functions to force redraw of connections and ensure they're visible
between client and server.
"""

def enhance_connection_drawing(scene):
    """
    Force a complete redraw of all connections in the scene
    to ensure they're visible, especially in network games.
    """
    if not scene:
        return False
    
    try:
        # First, ensure all units are updated
        for item in scene.items():
            try:
                from unit import Unit
                if isinstance(item, Unit):
                    item.update()
            except (ImportError, AttributeError) as e:
                print(f"Error during unit update: {str(e)}")
        
        # Then force a complete scene update
        scene.update()
        return True
    except Exception as e:
        print(f"Error enhancing connection drawing: {str(e)}")
        return False

def apply_connection_fixes(main_window):
    """
    Apply fixes to ensure connection lines are properly displayed
    in network games.
    
    This should be called after loading a network game state.
    """
    if not main_window or not hasattr(main_window, 'scene'):
        return False
    
    try:
        # Perform immediate update
        enhance_connection_drawing(main_window.scene)
        
        # Schedule delayed updates to ensure all connections appear
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(500, lambda: enhance_connection_drawing(main_window.scene))
        QTimer.singleShot(1000, lambda: enhance_connection_drawing(main_window.scene))
        
        # Add debug information if connections exist
        connection_count = 0
        unit_count = 0
        try:
            from unit import Unit
            for item in main_window.scene.items():
                if isinstance(item, Unit):
                    unit_count += 1
                    if hasattr(item, 'connections'):
                        connection_count += len(item.connections)
        except (ImportError, AttributeError) as e:
            print(f"Error counting connections: {str(e)}")
        
        print(f"Connection fix applied: Found {unit_count} units with {connection_count//2} connections")
        return True
    except Exception as e:
        print(f"Error applying connection fixes: {str(e)}")
        return False

# Modified version of apply_game_state that ensures connection updates
def enhanced_apply_game_state(main_window, game_state):
    """
    Enhanced version of apply_game_state that ensures connections are properly drawn
    """
    if not hasattr(main_window, 'apply_game_state'):
        print("Error: main_window does not have apply_game_state method")
        return False
        
    # First apply the game state using the original method
    success = main_window.apply_game_state(game_state)
    
    if success:
        # Then apply connection fixes
        apply_connection_fixes(main_window)
    
    return success
