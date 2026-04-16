"""
Plate reader measurement experiments.

Experiment templates for running measurements on the plate reader
without OT-2 involvement.
"""

import os
import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..utils.logging import log_msg
from .base import BaseExperiment


class PlateReaderMeasurementExperiment(BaseExperiment):
    """
    Simple plate reader measurement experiment.
    
    Collects background and runs a single measurement at a specified
    wavelength.
    
    Example:
        from ot2_controller.instruments import PlateReaderInstrument
        from ot2_controller.experiments import PlateReaderMeasurementExperiment
        
        with PlateReaderInstrument() as reader:
            exp = PlateReaderMeasurementExperiment(
                user_name="Lachlan",
                wavelength=600,
                plate_reader=reader
            )
            metadata = exp.run()
            
            print(f"Measurement saved to: {metadata.data_files[0]}")
    """
    
    EXPERIMENT_TYPE = "PlateReaderMeasurement"
    REQUIRED_INSTRUMENTS = ["plate_reader"]
    
    def __init__(
        self,
        user_name: str,
        wavelength: int = 600,
        collect_background: bool = True,
        experiment_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        **instruments
    ):
        """
        Initialize plate reader measurement experiment.
        
        Args:
            user_name: Name of the user
            wavelength: Measurement wavelength in nm
            collect_background: Whether to collect empty plate background
            experiment_name: Human-readable name
            output_dir: Output directory
            **instruments: Must include plate_reader=PlateReaderInstrument()
        """
        super().__init__(
            user_name=user_name,
            experiment_name=experiment_name or f"Measurement at {wavelength}nm",
            output_dir=output_dir,
            **instruments
        )
        
        self.wavelength = wavelength
        self.collect_background = collect_background
        self.background_path: Optional[str] = None
        self.measurement_path: Optional[str] = None
        
        self.metadata.add_parameter("wavelength", wavelength)
        self.metadata.add_parameter("collect_background", collect_background)
    
    def setup(self) -> None:
        """Collect plate background if requested."""
        if self.collect_background:
            reader = self.instruments["plate_reader"]
            
            log_msg("Please insert empty plate for background measurement.")
            input("Press Enter when ready...")
            
            self.background_path = reader.collect_background(
                self.wavelength,
                self.metadata.output_directory
            )
            
            if self.background_path:
                self.metadata.add_data_file(self.background_path)
                self.metadata.add_result("background_collected", True)
                self.log_event("measurement", "Background collected", {
                    "path": self.background_path
                })
            else:
                log_msg("Warning: Background collection failed")
                self.metadata.add_result("background_collected", False)
    
    def execute(self) -> None:
        """Run the measurement."""
        reader = self.instruments["plate_reader"]
        
        log_msg("Please insert sample plate for measurement.")
        input("Press Enter when ready...")
        
        self.measurement_path = reader.run_measurement(
            self.wavelength,
            self.metadata.output_directory,
            filename_prefix=f"measurement_{self.wavelength}nm"
        )
        
        if self.measurement_path:
            self.metadata.add_data_file(self.measurement_path)
            self.metadata.add_result("measurement_path", self.measurement_path)
            self.metadata.add_result("success", True)
            self.log_event("measurement", "Measurement completed", {
                "path": self.measurement_path
            })
        else:
            self.metadata.add_result("success", False)
            raise RuntimeError("Measurement failed")


class PlateReaderTimeCourseExperiment(BaseExperiment):
    """
    Plate reader time course experiment.
    
    Takes multiple measurements at specified intervals.
    
    Example:
        with PlateReaderInstrument() as reader:
            exp = PlateReaderTimeCourseExperiment(
                user_name="Lachlan",
                wavelength=600,
                num_measurements=10,
                interval_seconds=300,  # 5 minutes
                plate_reader=reader
            )
            exp.run()
    """
    
    EXPERIMENT_TYPE = "PlateReaderTimeCourse"
    REQUIRED_INSTRUMENTS = ["plate_reader"]
    
    def __init__(
        self,
        user_name: str,
        wavelength: int = 600,
        num_measurements: int = 10,
        interval_seconds: float = 300.0,
        experiment_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        **instruments
    ):
        """
        Initialize time course experiment.
        
        Args:
            user_name: Name of the user
            wavelength: Measurement wavelength in nm
            num_measurements: Number of measurements to take
            interval_seconds: Time between measurements in seconds
            experiment_name: Human-readable name
            output_dir: Output directory
            **instruments: Must include plate_reader=PlateReaderInstrument()
        """
        super().__init__(
            user_name=user_name,
            experiment_name=experiment_name or f"Time Course at {wavelength}nm",
            output_dir=output_dir,
            **instruments
        )
        
        self.wavelength = wavelength
        self.num_measurements = num_measurements
        self.interval_seconds = interval_seconds
        self.measurements: List[Dict[str, Any]] = []
        
        self.metadata.add_parameter("wavelength", wavelength)
        self.metadata.add_parameter("num_measurements", num_measurements)
        self.metadata.add_parameter("interval_seconds", interval_seconds)
    
    def setup(self) -> None:
        """Collect background and prepare."""
        reader = self.instruments["plate_reader"]
        
        log_msg("Please insert empty plate for background measurement.")
        input("Press Enter when ready...")
        
        background_path = reader.collect_background(
            self.wavelength,
            self.metadata.output_directory
        )
        
        if background_path:
            self.metadata.add_data_file(background_path)
            self.metadata.add_result("background_path", background_path)
        
        log_msg("Please insert sample plate.")
        input("Press Enter to start time course...")
    
    def execute(self) -> None:
        """Run the time course measurements."""
        reader = self.instruments["plate_reader"]
        
        for i in range(self.num_measurements):
            measurement_num = i + 1
            log_msg(f"\nMeasurement {measurement_num}/{self.num_measurements}")
            
            # Take measurement
            start_time = datetime.now()
            measurement_path = reader.run_measurement(
                self.wavelength,
                self.metadata.output_directory,
                filename_prefix=f"timecourse_{measurement_num:03d}"
            )
            
            if measurement_path:
                self.metadata.add_data_file(measurement_path)
                self.measurements.append({
                    "measurement_number": measurement_num,
                    "timestamp": start_time.isoformat(),
                    "path": measurement_path
                })
                self.log_event("measurement", f"Measurement {measurement_num} completed")
            else:
                log_msg(f"Warning: Measurement {measurement_num} failed")
                self.measurements.append({
                    "measurement_number": measurement_num,
                    "timestamp": start_time.isoformat(),
                    "path": None,
                    "error": "Measurement failed"
                })
            
            # Wait for next measurement (except after last)
            if i < self.num_measurements - 1:
                log_msg(f"Waiting {self.interval_seconds}s until next measurement...")
                time.sleep(self.interval_seconds)
        
        self.metadata.add_result("measurements", self.measurements)
        self.metadata.add_result("successful_measurements", 
                                 sum(1 for m in self.measurements if m.get("path")))


class PlateReaderTemperatureRampExperiment(BaseExperiment):
    """
    Plate reader experiment with temperature ramping.
    
    Takes measurements at different temperatures, useful for
    thermal stability or LCST-type studies.
    
    Example:
        with PlateReaderInstrument() as reader:
            exp = PlateReaderTemperatureRampExperiment(
                user_name="Lachlan",
                wavelength=600,
                start_temp=25.0,
                end_temp=45.0,
                step_size=2.0,
                plate_reader=reader
            )
            exp.run()
    """
    
    EXPERIMENT_TYPE = "PlateReaderTemperatureRamp"
    REQUIRED_INSTRUMENTS = ["plate_reader"]
    
    def __init__(
        self,
        user_name: str,
        wavelength: int = 600,
        start_temp: float = 25.0,
        end_temp: float = 45.0,
        step_size: float = 2.0,
        stabilization_time: float = 60.0,
        bidirectional: bool = False,
        experiment_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        **instruments
    ):
        """
        Initialize temperature ramp experiment.
        
        Args:
            user_name: Name of the user
            wavelength: Measurement wavelength in nm
            start_temp: Starting temperature in Celsius
            end_temp: Ending temperature in Celsius
            step_size: Temperature step size in Celsius
            stabilization_time: Time to wait after reaching temp (seconds)
            bidirectional: If True, ramp up then back down
            experiment_name: Human-readable name
            output_dir: Output directory
            **instruments: Must include plate_reader=PlateReaderInstrument()
        """
        super().__init__(
            user_name=user_name,
            experiment_name=experiment_name or f"Temp Ramp {start_temp}-{end_temp}C",
            output_dir=output_dir,
            **instruments
        )
        
        self.wavelength = wavelength
        self.start_temp = start_temp
        self.end_temp = end_temp
        self.step_size = step_size
        self.stabilization_time = stabilization_time
        self.bidirectional = bidirectional
        self.measurements: List[Dict[str, Any]] = []
        
        self.metadata.add_parameter("wavelength", wavelength)
        self.metadata.add_parameter("start_temp", start_temp)
        self.metadata.add_parameter("end_temp", end_temp)
        self.metadata.add_parameter("step_size", step_size)
        self.metadata.add_parameter("stabilization_time", stabilization_time)
        self.metadata.add_parameter("bidirectional", bidirectional)
    
    def _generate_temperatures(self) -> List[float]:
        """Generate list of temperatures to measure at."""
        temps = []
        
        # Ramp up (or down if start > end)
        current = self.start_temp
        if self.start_temp <= self.end_temp:
            while current <= self.end_temp:
                temps.append(current)
                current += self.step_size
        else:
            while current >= self.end_temp:
                temps.append(current)
                current -= self.step_size
        
        # Ramp back if bidirectional
        if self.bidirectional:
            reverse = temps[-2::-1]  # All except last, reversed
            temps.extend(reverse)
        
        return temps
    
    def setup(self) -> None:
        """Collect background and prepare."""
        reader = self.instruments["plate_reader"]
        
        log_msg("Please insert empty plate for background measurement.")
        input("Press Enter when ready...")
        
        background_path = reader.collect_background(
            self.wavelength,
            self.metadata.output_directory
        )
        
        if background_path:
            self.metadata.add_data_file(background_path)
            self.metadata.add_result("background_path", background_path)
        
        log_msg("Please insert sample plate.")
        input("Press Enter to start temperature ramp...")
    
    def execute(self) -> None:
        """Run the temperature ramp."""
        reader = self.instruments["plate_reader"]
        temperatures = self._generate_temperatures()
        
        log_msg(f"Temperature ramp: {len(temperatures)} measurements")
        log_msg(f"Temperatures: {temperatures}")
        
        for i, temp in enumerate(temperatures):
            measurement_num = i + 1
            log_msg(f"\nStep {measurement_num}/{len(temperatures)}: {temp}°C")
            
            # Set temperature and wait for stabilization
            reader.set_and_stabilize(
                temp,
                tolerance=0.2,
                stable_time=self.stabilization_time
            )
            
            # Take measurement
            measurement_path = reader.run_measurement(
                self.wavelength,
                self.metadata.output_directory,
                filename_prefix=f"tempramp_{temp:.1f}C_{measurement_num:03d}"
            )
            
            # Record current temperature
            temp1, temp2 = reader.get_temperature()
            
            measurement_record = {
                "step": measurement_num,
                "target_temp": temp,
                "actual_temp1": temp1,
                "actual_temp2": temp2,
                "timestamp": datetime.now().isoformat(),
                "path": measurement_path
            }
            
            if measurement_path:
                self.metadata.add_data_file(measurement_path)
                self.log_event("measurement", f"Measurement at {temp}°C completed")
            else:
                measurement_record["error"] = "Measurement failed"
                log_msg(f"Warning: Measurement at {temp}°C failed")
            
            self.measurements.append(measurement_record)
        
        self.metadata.add_result("measurements", self.measurements)
        self.metadata.add_result("successful_measurements",
                                 sum(1 for m in self.measurements if m.get("path")))
        self.metadata.add_result("temperatures_measured", 
                                 [m["target_temp"] for m in self.measurements])
