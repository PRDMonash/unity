"""
Standardized experiment metadata for all experiments.

Provides a consistent structure for recording experiment information,
regardless of which instruments are used.
"""

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional


class ExperimentStatus(Enum):
    """Status of an experiment."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class InstrumentRecord:
    """Record of an instrument used in an experiment."""
    name: str
    instrument_type: str  # "OT2", "PlateReader", etc.
    connected: bool = False
    config: Dict[str, Any] = field(default_factory=dict)
    operations_performed: List[str] = field(default_factory=list)
    
    def log_operation(self, operation: str) -> None:
        """Log an operation performed by this instrument."""
        self.operations_performed.append(operation)


@dataclass
class ExperimentMetadata:
    """
    Standardized metadata for ALL experiments.
    
    Every experiment must populate this structure regardless of
    which instruments are used. This ensures consistent data
    recording and enables cross-experiment analysis.
    
    Example:
        metadata = ExperimentMetadata.create(
            experiment_type="LCST",
            experiment_name="Temperature Ramp Test",
            user_name="Lachlan",
            output_directory="C:/data/experiments"
        )
        
        metadata.log_event("setup", "Starting experiment")
        metadata.add_parameter("target_temp", 45.0)
        metadata.add_data_file("measurement_001.csv")
        
        metadata.save()
    """
    
    # Identity
    experiment_id: str
    experiment_type: str  # "LCST", "BayesianOptimization", "OT2Protocol", etc.
    experiment_name: str
    
    # User & timestamps
    user_name: str
    start_time: str  # ISO format string
    end_time: Optional[str] = None
    
    # Status
    status: str = "pending"  # String for JSON serialization
    error_message: Optional[str] = None
    
    # Instruments used
    instruments: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Parameters (experiment-specific)
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Results summary
    results_summary: Dict[str, Any] = field(default_factory=dict)
    
    # File paths
    output_directory: str = ""
    data_files: List[str] = field(default_factory=list)
    
    # History/log
    event_log: List[Dict[str, Any]] = field(default_factory=list)
    
    # Package version for reproducibility
    package_version: str = ""
    
    @classmethod
    def create(
        cls,
        experiment_type: str,
        experiment_name: str,
        user_name: str,
        output_directory: str = "",
        **additional_params
    ) -> "ExperimentMetadata":
        """
        Factory method to create new experiment metadata.
        
        Args:
            experiment_type: Type of experiment (e.g., "LCST", "BayesianOptimization")
            experiment_name: Human-readable name for this run
            user_name: Name of the user running the experiment
            output_directory: Base directory for output files
            **additional_params: Additional parameters to add
            
        Returns:
            New ExperimentMetadata instance
        """
        from .. import __version__
        
        metadata = cls(
            experiment_id=str(uuid.uuid4())[:8],
            experiment_type=experiment_type,
            experiment_name=experiment_name,
            user_name=user_name,
            start_time=datetime.now().isoformat(),
            output_directory=output_directory,
            package_version=__version__
        )
        
        # Add any additional parameters
        for key, value in additional_params.items():
            metadata.parameters[key] = value
        
        return metadata
    
    def log_event(
        self,
        event_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a timestamped event to the log.
        
        Args:
            event_type: Category of event (e.g., "lifecycle", "measurement", "error")
            message: Description of the event
            data: Optional additional data
        """
        self.event_log.append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "message": message,
            "data": data or {}
        })
    
    def add_parameter(self, name: str, value: Any) -> None:
        """Add or update a parameter."""
        self.parameters[name] = value
    
    def add_result(self, name: str, value: Any) -> None:
        """Add or update a result in the summary."""
        self.results_summary[name] = value
    
    def add_data_file(self, file_path: str) -> None:
        """Record a data file path."""
        self.data_files.append(file_path)
    
    def register_instrument(
        self,
        key: str,
        name: str,
        instrument_type: str,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register an instrument used in this experiment.
        
        Args:
            key: Key to identify this instrument (e.g., "ot2", "plate_reader")
            name: Display name of the instrument
            instrument_type: Type category (e.g., "OT2", "PlateReader")
            config: Configuration dictionary
        """
        self.instruments[key] = {
            "name": name,
            "instrument_type": instrument_type,
            "connected": False,
            "config": config or {},
            "operations_performed": []
        }
    
    def update_instrument_status(self, key: str, connected: bool) -> None:
        """Update the connection status of an instrument."""
        if key in self.instruments:
            self.instruments[key]["connected"] = connected
    
    def log_instrument_operation(self, key: str, operation: str) -> None:
        """Log an operation performed by an instrument."""
        if key in self.instruments:
            self.instruments[key]["operations_performed"].append(operation)
    
    def set_status(self, status: ExperimentStatus) -> None:
        """Update experiment status."""
        self.status = status.value
        self.log_event("status_change", f"Status changed to {status.value}")
    
    def mark_completed(self) -> None:
        """Mark experiment as completed."""
        self.status = ExperimentStatus.COMPLETED.value
        self.end_time = datetime.now().isoformat()
        self.log_event("lifecycle", "Experiment completed successfully")
    
    def mark_failed(self, error_message: str) -> None:
        """Mark experiment as failed."""
        self.status = ExperimentStatus.FAILED.value
        self.end_time = datetime.now().isoformat()
        self.error_message = error_message
        self.log_event("error", f"Experiment failed: {error_message}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def save(self, path: Optional[str] = None) -> str:
        """
        Save metadata to JSON file.
        
        Args:
            path: Optional path to save to. If not provided, saves to
                  output_directory with auto-generated filename.
                  
        Returns:
            Path to saved file
        """
        if path is None:
            if not self.output_directory:
                raise ValueError("No output directory specified")
            
            # Ensure directory exists
            os.makedirs(self.output_directory, exist_ok=True)
            
            # Generate filename
            timestamp = self.start_time.replace(":", "-").replace(".", "-")
            filename = f"{self.experiment_type}_{self.experiment_id}_{timestamp}.json"
            path = os.path.join(self.output_directory, filename)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        
        self.log_event("file", f"Metadata saved to {path}")
        return path
    
    @classmethod
    def load(cls, path: str) -> "ExperimentMetadata":
        """
        Load metadata from JSON file.
        
        Args:
            path: Path to JSON file
            
        Returns:
            ExperimentMetadata instance
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls(**data)
    
    def __str__(self) -> str:
        """Human-readable summary."""
        duration = ""
        if self.end_time:
            start = datetime.fromisoformat(self.start_time)
            end = datetime.fromisoformat(self.end_time)
            duration = f" (duration: {end - start})"
        
        instruments_str = ", ".join(self.instruments.keys()) or "none"
        
        return (
            f"Experiment: {self.experiment_name} ({self.experiment_type})\n"
            f"  ID: {self.experiment_id}\n"
            f"  User: {self.user_name}\n"
            f"  Status: {self.status}{duration}\n"
            f"  Instruments: {instruments_str}\n"
            f"  Data files: {len(self.data_files)}"
        )
