"""
Base instrument abstraction.

Provides the abstract base class that all instrument implementations
must inherit from, ensuring a consistent interface across all hardware.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class InstrumentStatus:
    """
    Standardized instrument status information.
    
    Attributes:
        connected: Whether the instrument is currently connected
        ready: Whether the instrument is ready to accept commands
        last_checked: When the status was last verified
        details: Additional instrument-specific status information
    """
    connected: bool
    ready: bool
    last_checked: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        status = "connected" if self.connected else "disconnected"
        ready = "ready" if self.ready else "busy"
        return f"{status}, {ready}"


class BaseInstrument(ABC):
    """
    Abstract base class for all laboratory instruments.
    
    Provides a consistent interface for instrument control, including
    connection management, status checking, and context manager support.
    
    Subclasses must implement:
        - name (property): Identifier for the instrument
        - instrument_type (property): Category of instrument
        - connect(): Establish connection to hardware
        - disconnect(): Clean up connection
        - status(): Get current status
        - test_connection(): Verify connection is working
    
    Example:
        class MyInstrument(BaseInstrument):
            name = "My Instrument"
            instrument_type = "CustomType"
            
            def connect(self) -> bool:
                # Connect to hardware
                return True
            
            def disconnect(self) -> None:
                # Clean up
                pass
            
            def status(self) -> InstrumentStatus:
                return InstrumentStatus(connected=True, ready=True)
            
            def test_connection(self) -> bool:
                return True
        
        # Use as context manager
        with MyInstrument() as inst:
            print(inst.status())
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable instrument name."""
        pass
    
    @property
    @abstractmethod
    def instrument_type(self) -> str:
        """Instrument category (e.g., 'OT2', 'PlateReader')."""
        pass
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the instrument.
        
        Returns:
            True if connection was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """
        Disconnect from the instrument and clean up resources.
        
        Should be safe to call multiple times.
        """
        pass
    
    @abstractmethod
    def status(self) -> InstrumentStatus:
        """
        Get current instrument status.
        
        Returns:
            InstrumentStatus with current connection and ready state.
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test that the connection is working.
        
        Performs a simple operation to verify the instrument is responsive.
        
        Returns:
            True if connection is working, False otherwise.
        """
        pass
    
    def __enter__(self) -> "BaseInstrument":
        """Context manager entry - connect to instrument."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - disconnect from instrument."""
        self.disconnect()
    
    def get_config_dict(self) -> Dict[str, Any]:
        """
        Get configuration as a dictionary.
        
        Useful for recording in experiment metadata.
        
        Returns:
            Dictionary of configuration values.
        """
        if hasattr(self, 'config') and self.config is not None:
            if hasattr(self.config, '__dict__'):
                return {k: v for k, v in self.config.__dict__.items() 
                       if not k.startswith('_')}
        return {}
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
