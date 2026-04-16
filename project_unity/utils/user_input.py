"""
User input utilities for consistent prompt handling.

Provides typed input methods with validation and default fallbacks.
"""

from typing import Optional, List
from .logging import log_msg


class UserInputHandler:
    """Handler for user input with validation and defaults."""
    
    @staticmethod
    def get_float(prompt: str, default: float) -> float:
        """
        Get a float value from user input.
        
        Args:
            prompt: The prompt to display.
            default: Default value if input is invalid.
            
        Returns:
            User-provided float or default.
        """
        try:
            return float(input(f">>> {prompt}: \n>>> "))
        except ValueError:
            log_msg(f"Invalid input, using default: {default}")
            return default
    
    @staticmethod
    def get_int(prompt: str, default: int) -> int:
        """
        Get an integer value from user input.
        
        Args:
            prompt: The prompt to display.
            default: Default value if input is invalid.
            
        Returns:
            User-provided integer or default.
        """
        try:
            return int(input(f">>> {prompt}: \n>>> "))
        except ValueError:
            log_msg(f"Invalid input, using default: {default}")
            return default
    
    @staticmethod
    def get_string(prompt: str, default: str = "") -> str:
        """
        Get a string value from user input.
        
        Args:
            prompt: The prompt to display.
            default: Default value if input is empty.
            
        Returns:
            User-provided string or default.
        """
        value = input(f">>> {prompt}: \n>>> ").strip()
        return value if value else default
    
    @staticmethod
    def wait_for_confirmation(prompt: str) -> bool:
        """
        Wait for yes/no confirmation from user.
        
        Args:
            prompt: The prompt to display.
            
        Returns:
            True if user confirms with 'yes', False otherwise.
        """
        while True:
            response = input(f">>> {prompt} (yes/no): \n>>> ").lower()
            if response in ["yes", "no"]:
                return response == "yes"
            log_msg("Invalid input. Please enter 'yes' or 'no'.")
    
    @staticmethod
    def wait_for_ready(prompt: str) -> None:
        """
        Wait for user to press Enter when ready.
        
        Args:
            prompt: The prompt to display.
        """
        input(f"\n>>> {prompt}\n>>> ")
    
    @staticmethod
    def get_float_required(prompt: str) -> float:
        """
        Get a float value, retrying until valid input is provided.
        
        Args:
            prompt: The prompt to display.
            
        Returns:
            Valid float value from user.
        """
        while True:
            try:
                return float(input(f">>> {prompt}: \n>>> "))
            except ValueError:
                log_msg("Invalid input. Please enter a numeric value.")
    
    @staticmethod
    def get_choice(prompt: str, options: List[str]) -> str:
        """
        Get a choice from a list of options.
        
        Args:
            prompt: The prompt to display.
            options: List of valid options.
            
        Returns:
            Selected option.
        """
        options_str = "/".join(options)
        while True:
            response = input(f">>> {prompt} ({options_str}): \n>>> ").lower()
            if response in [o.lower() for o in options]:
                return response
            log_msg(f"Invalid input. Please enter one of: {options_str}")
