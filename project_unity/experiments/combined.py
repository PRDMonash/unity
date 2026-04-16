"""
Combined OT-2 and plate reader experiments.

Experiment templates that use both instruments together.
"""

import os
import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..utils.logging import log_msg
from .base import BaseExperiment


class OT2AndPlateReaderExperiment(BaseExperiment):
    """
    Basic combined experiment using both OT-2 and plate reader.
    
    Runs an OT-2 protocol to prepare samples, then measures with
    the plate reader.
    
    Example:
        from ot2_controller.instruments import OT2Instrument, PlateReaderInstrument
        from ot2_controller.experiments import OT2AndPlateReaderExperiment
        
        with OT2Instrument() as ot2, PlateReaderInstrument() as reader:
            exp = OT2AndPlateReaderExperiment(
                user_name="Lachlan",
                protocol_path="prepare_samples.py",
                wavelength=600,
                ot2=ot2,
                plate_reader=reader
            )
            exp.run()
    """
    
    EXPERIMENT_TYPE = "OT2AndPlateReader"
    REQUIRED_INSTRUMENTS = ["ot2", "plate_reader"]
    
    def __init__(
        self,
        user_name: str,
        protocol_path: str,
        wavelength: int = 600,
        additional_files: Optional[List[str]] = None,
        collect_background: bool = True,
        experiment_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        **instruments
    ):
        """
        Initialize combined experiment.
        
        Args:
            user_name: Name of the user
            protocol_path: Path to OT-2 protocol file
            wavelength: Measurement wavelength in nm
            additional_files: Additional files to upload to OT-2
            collect_background: Whether to collect plate background first
            experiment_name: Human-readable name
            output_dir: Output directory
            **instruments: Must include ot2 and plate_reader
        """
        super().__init__(
            user_name=user_name,
            experiment_name=experiment_name or "Combined OT-2 + Plate Reader",
            output_dir=output_dir,
            **instruments
        )
        
        self.protocol_path = protocol_path
        self.wavelength = wavelength
        self.additional_files = additional_files or []
        self.collect_background = collect_background
        
        self.metadata.add_parameter("protocol_path", protocol_path)
        self.metadata.add_parameter("wavelength", wavelength)
        self.metadata.add_parameter("additional_files", self.additional_files)
        self.metadata.add_parameter("collect_background", collect_background)
    
    def setup(self) -> None:
        """Collect background and upload protocol."""
        ot2 = self.instruments["ot2"]
        reader = self.instruments["plate_reader"]
        
        # Collect plate background first
        if self.collect_background:
            log_msg("Please insert empty plate for background measurement.")
            input("Press Enter when ready...")
            
            background_path = reader.collect_background(
                self.wavelength,
                self.metadata.output_directory
            )
            
            if background_path:
                self.metadata.add_data_file(background_path)
                self.metadata.add_result("background_path", background_path)
            else:
                log_msg("Warning: Background collection failed")
        
        # Upload OT-2 protocol
        log_msg(f"Uploading protocol: {os.path.basename(self.protocol_path)}")
        if not ot2.upload_protocol(self.protocol_path):
            raise RuntimeError("Failed to upload protocol")
        
        for file_path in self.additional_files:
            if os.path.exists(file_path):
                ot2.upload_file(file_path)
    
    def execute(self) -> None:
        """Run OT-2 protocol then measure."""
        ot2 = self.instruments["ot2"]
        reader = self.instruments["plate_reader"]
        
        # Run OT-2 protocol
        protocol_name = os.path.basename(self.protocol_path)
        log_msg(f"Running OT-2 protocol: {protocol_name}")
        
        protocol_success = ot2.run_protocol(protocol_name)
        self.metadata.add_result("protocol_success", protocol_success)
        
        if not protocol_success:
            log_msg("Warning: OT-2 protocol may not have completed successfully")
            response = input("Continue with measurement? (yes/no): ")
            if response.lower() != "yes":
                raise RuntimeError("Aborted by user after protocol failure")
        
        # Measure
        log_msg("Running plate reader measurement...")
        log_msg("Please ensure plate is in the reader.")
        input("Press Enter when ready...")
        
        measurement_path = reader.run_measurement(
            self.wavelength,
            self.metadata.output_directory,
            filename_prefix="measurement"
        )
        
        if measurement_path:
            self.metadata.add_data_file(measurement_path)
            self.metadata.add_result("measurement_path", measurement_path)
            self.metadata.add_result("success", True)
        else:
            self.metadata.add_result("success", False)
            raise RuntimeError("Measurement failed")


class IterativeOptimizationExperiment(BaseExperiment):
    """
    Iterative optimization experiment.
    
    Performs multiple rounds of OT-2 sample preparation and measurement,
    useful for optimization or screening workflows.
    
    Example:
        with OT2Instrument() as ot2, PlateReaderInstrument() as reader:
            exp = IterativeOptimizationExperiment(
                user_name="Lachlan",
                protocol_path="prepare_samples.py",
                volumes_csv_path="volumes.csv",
                max_iterations=5,
                ot2=ot2,
                plate_reader=reader
            )
            exp.run()
    """
    
    EXPERIMENT_TYPE = "IterativeOptimization"
    REQUIRED_INSTRUMENTS = ["ot2", "plate_reader"]
    
    def __init__(
        self,
        user_name: str,
        protocol_path: str,
        volumes_csv_path: str,
        wavelength: int = 600,
        max_iterations: int = 10,
        experiment_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        **instruments
    ):
        """
        Initialize iterative optimization experiment.
        
        Args:
            user_name: Name of the user
            protocol_path: Path to OT-2 protocol file
            volumes_csv_path: Path to volumes CSV file
            wavelength: Measurement wavelength in nm
            max_iterations: Maximum number of iterations
            experiment_name: Human-readable name
            output_dir: Output directory
            **instruments: Must include ot2 and plate_reader
        """
        super().__init__(
            user_name=user_name,
            experiment_name=experiment_name or "Iterative Optimization",
            output_dir=output_dir,
            **instruments
        )
        
        self.protocol_path = protocol_path
        self.volumes_csv_path = volumes_csv_path
        self.wavelength = wavelength
        self.max_iterations = max_iterations
        self.iterations: List[Dict[str, Any]] = []
        
        self.metadata.add_parameter("protocol_path", protocol_path)
        self.metadata.add_parameter("volumes_csv_path", volumes_csv_path)
        self.metadata.add_parameter("wavelength", wavelength)
        self.metadata.add_parameter("max_iterations", max_iterations)
    
    def setup(self) -> None:
        """Collect background and upload initial files."""
        reader = self.instruments["plate_reader"]
        ot2 = self.instruments["ot2"]
        
        # Collect background
        log_msg("Please insert empty plate for background measurement.")
        input("Press Enter when ready...")
        
        background_path = reader.collect_background(
            self.wavelength,
            self.metadata.output_directory
        )
        
        if background_path:
            self.metadata.add_data_file(background_path)
            self.metadata.add_result("background_path", background_path)
        
        # Upload protocol
        ot2.upload_protocol(self.protocol_path)
    
    def execute(self) -> None:
        """Run iterative optimization loop."""
        ot2 = self.instruments["ot2"]
        reader = self.instruments["plate_reader"]
        
        for iteration in range(1, self.max_iterations + 1):
            log_msg(f"\n{'='*60}")
            log_msg(f"ITERATION {iteration}/{self.max_iterations}")
            log_msg(f"{'='*60}")
            
            iteration_record = {
                "iteration": iteration,
                "start_time": datetime.now().isoformat()
            }
            
            # Upload volumes CSV (may have been modified)
            if os.path.exists(self.volumes_csv_path):
                ot2.upload_file(self.volumes_csv_path)
            
            # Run OT-2 protocol
            protocol_name = os.path.basename(self.protocol_path)
            log_msg(f"Running OT-2 protocol: {protocol_name}")
            
            protocol_success = ot2.run_protocol(protocol_name)
            iteration_record["protocol_success"] = protocol_success
            
            # Take measurement
            log_msg("Taking measurement...")
            input("Press Enter when plate is ready...")
            
            measurement_path = reader.run_measurement(
                self.wavelength,
                self.metadata.output_directory,
                filename_prefix=f"iteration_{iteration:03d}"
            )
            
            iteration_record["measurement_path"] = measurement_path
            iteration_record["end_time"] = datetime.now().isoformat()
            
            if measurement_path:
                self.metadata.add_data_file(measurement_path)
            
            self.iterations.append(iteration_record)
            self.log_event("iteration", f"Iteration {iteration} completed")
            
            # Check if user wants to continue
            if iteration < self.max_iterations:
                response = input("Continue to next iteration? (yes/no/done): ").lower()
                if response == "no":
                    raise RuntimeError("Aborted by user")
                elif response == "done":
                    log_msg("User indicated optimization is complete.")
                    break
        
        self.metadata.add_result("iterations", self.iterations)
        self.metadata.add_result("total_iterations", len(self.iterations))
