"""
Base experiment class for standardized experiment execution.

Provides a framework for building experiments with consistent
lifecycle management, metadata recording, and instrument handling.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any, Type
import os

from ..instruments.base import BaseInstrument
from ..utils.logging import log_msg
from ..utils.file_io import ensure_directory
from .metadata import ExperimentMetadata, ExperimentStatus


class BaseExperiment(ABC):
    """
    Base class for all experiments.
    
    Provides standardized lifecycle management and metadata recording.
    Subclass this to create new experiment types.
    
    Lifecycle:
        1. __init__: Configure experiment and instruments
        2. run(): Execute full lifecycle:
            a. Connect instruments
            b. setup(): Collect inputs, prepare resources
            c. execute(): Main experiment logic
            d. finalize(): Save results, cleanup
            e. Disconnect instruments
    
    Example:
        class MyExperiment(BaseExperiment):
            EXPERIMENT_TYPE = "CustomExperiment"
            REQUIRED_INSTRUMENTS = ["ot2"]
            
            def setup(self) -> None:
                # Prepare for experiment
                self.metadata.add_parameter("my_param", 42)
            
            def execute(self) -> None:
                # Main experiment logic
                ot2 = self.instruments["ot2"]
                ot2.run_protocol("my_protocol.py")
                self.metadata.add_result("success", True)
        
        # Run the experiment
        with OT2Instrument() as ot2:
            exp = MyExperiment(
                user_name="Lachlan",
                experiment_name="Test Run",
                ot2=ot2
            )
            metadata = exp.run()
    
    Attributes:
        EXPERIMENT_TYPE: String identifying this experiment type
        REQUIRED_INSTRUMENTS: List of instrument keys that must be provided
        OPTIONAL_INSTRUMENTS: List of instrument keys that may be provided
    """
    
    # Override in subclasses
    EXPERIMENT_TYPE: str = "Base"
    REQUIRED_INSTRUMENTS: List[str] = []
    OPTIONAL_INSTRUMENTS: List[str] = []
    
    def __init__(
        self,
        user_name: str,
        experiment_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        **instruments
    ):
        """
        Initialize experiment.
        
        Args:
            user_name: Name of the user running the experiment
            experiment_name: Human-readable name for this experiment run
            output_dir: Directory for output files (auto-created if needed)
            **instruments: Instrument instances keyed by name
                          (e.g., ot2=OT2Instrument(), plate_reader=PlateReaderInstrument())
        """
        # Set default output directory if not provided
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(
                os.getcwd(),
                "experiment_output",
                f"{self.EXPERIMENT_TYPE}_{timestamp}"
            )
        
        # Create metadata
        self.metadata = ExperimentMetadata.create(
            experiment_type=self.EXPERIMENT_TYPE,
            experiment_name=experiment_name or self.EXPERIMENT_TYPE,
            user_name=user_name,
            output_directory=output_dir
        )
        
        # Store and validate instruments
        self.instruments: Dict[str, BaseInstrument] = {}
        self._validate_and_store_instruments(instruments)
        
        # Track if we need to manage instrument connections
        self._instruments_connected_by_us: List[str] = []
    
    def _validate_and_store_instruments(self, instruments: Dict[str, BaseInstrument]) -> None:
        """
        Validate that required instruments are provided and store them.
        
        Args:
            instruments: Dictionary of instrument instances
            
        Raises:
            ValueError: If a required instrument is missing
        """
        # Check required instruments
        for required in self.REQUIRED_INSTRUMENTS:
            if required not in instruments:
                raise ValueError(
                    f"Required instrument '{required}' not provided. "
                    f"This experiment requires: {self.REQUIRED_INSTRUMENTS}"
                )
        
        # Store all provided instruments
        self.instruments = instruments
        
        # Record instruments in metadata
        for key, inst in instruments.items():
            self.metadata.register_instrument(
                key=key,
                name=inst.name,
                instrument_type=inst.instrument_type,
                config=inst.get_config_dict()
            )
    
    def _connect_instruments(self) -> None:
        """Connect all instruments that aren't already connected."""
        for key, inst in self.instruments.items():
            status = inst.status()
            if not status.connected:
                log_msg(f"Connecting to {inst.name}...")
                try:
                    inst.connect()
                    self._instruments_connected_by_us.append(key)
                    self.metadata.update_instrument_status(key, True)
                    self.metadata.log_instrument_operation(key, "connected")
                except Exception as e:
                    self.metadata.log_event(
                        "error",
                        f"Failed to connect to {inst.name}: {e}"
                    )
                    raise
            else:
                self.metadata.update_instrument_status(key, True)
    
    def _disconnect_instruments(self) -> None:
        """Disconnect instruments that we connected."""
        for key in self._instruments_connected_by_us:
            if key in self.instruments:
                inst = self.instruments[key]
                try:
                    log_msg(f"Disconnecting from {inst.name}...")
                    inst.disconnect()
                    self.metadata.update_instrument_status(key, False)
                    self.metadata.log_instrument_operation(key, "disconnected")
                except Exception as e:
                    log_msg(f"Error disconnecting {inst.name}: {e}")
        
        self._instruments_connected_by_us.clear()
    
    def run(self) -> ExperimentMetadata:
        """
        Execute the full experiment lifecycle.
        
        This method handles:
        1. Creating output directory
        2. Connecting instruments
        3. Running setup(), execute(), and finalize()
        4. Handling errors and updating status
        5. Disconnecting instruments
        6. Saving metadata
        
        Returns:
            ExperimentMetadata with all recorded information
        """
        try:
            # Create output directory
            ensure_directory(self.metadata.output_directory)
            
            # Update status
            self.metadata.set_status(ExperimentStatus.RUNNING)
            self.metadata.log_event("lifecycle", "Experiment starting")
            
            # Connect instruments
            self._connect_instruments()
            
            # Setup phase
            self.metadata.log_event("lifecycle", "Running setup")
            self.setup()
            
            # Execute phase
            self.metadata.log_event("lifecycle", "Running main experiment")
            self.execute()
            
            # Finalize phase
            self.metadata.log_event("lifecycle", "Finalizing")
            self.finalize()
            
            # Mark success
            self.metadata.mark_completed()
            
        except KeyboardInterrupt:
            self.metadata.status = ExperimentStatus.CANCELLED.value
            self.metadata.log_event("lifecycle", "Experiment cancelled by user")
            raise
            
        except Exception as e:
            self.metadata.mark_failed(str(e))
            log_msg(f"Experiment failed: {e}")
            raise
            
        finally:
            # Disconnect instruments we connected
            self._disconnect_instruments()
            
            # Ensure end time is set
            if self.metadata.end_time is None:
                self.metadata.end_time = datetime.now().isoformat()
            
            # Save metadata
            try:
                metadata_path = self.metadata.save()
                log_msg(f"Metadata saved to: {metadata_path}")
            except Exception as e:
                log_msg(f"Warning: Failed to save metadata: {e}")
        
        return self.metadata
    
    @abstractmethod
    def setup(self) -> None:
        """
        Setup phase - collect inputs, prepare files, etc.
        
        Override this method to perform any setup before the main
        experiment execution. This is a good place to:
        - Collect user input
        - Prepare files
        - Upload protocols
        - Collect background measurements
        """
        pass
    
    @abstractmethod
    def execute(self) -> None:
        """
        Main experiment execution.
        
        Override this method with the core experiment logic.
        All instruments are connected and ready when this runs.
        """
        pass
    
    def finalize(self) -> None:
        """
        Finalization phase - save results, cleanup, etc.
        
        Override this method to perform any cleanup after the main
        experiment execution. This is a good place to:
        - Save additional result files
        - Generate summary reports
        - Clean up temporary files
        
        The default implementation does nothing.
        """
        pass
    
    def add_parameter(self, name: str, value: Any) -> None:
        """Convenience method to add a parameter to metadata."""
        self.metadata.add_parameter(name, value)
    
    def add_result(self, name: str, value: Any) -> None:
        """Convenience method to add a result to metadata."""
        self.metadata.add_result(name, value)
    
    def add_data_file(self, path: str) -> None:
        """Convenience method to record a data file."""
        self.metadata.add_data_file(path)
    
    def log_event(self, event_type: str, message: str, data: Dict = None) -> None:
        """Convenience method to log an event."""
        self.metadata.log_event(event_type, message, data)
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"type='{self.EXPERIMENT_TYPE}', "
            f"user='{self.metadata.user_name}', "
            f"status='{self.metadata.status}')"
        )
