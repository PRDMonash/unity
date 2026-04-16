"""
Example: Creating Custom Experiments

This example shows how to create your own experiment classes
by subclassing BaseExperiment. This gives you full control
over the experiment workflow while maintaining standardized
metadata.

Usage:
    python example_custom_experiment.py
"""

import os
import sys
import time
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from project_unity import (
    BaseExperiment,
    ExperimentMetadata,
    OT2Instrument,
    PlateReaderInstrument,
)


# =============================================================================
# Example 1: Minimal Custom Experiment (OT-2 Only)
# =============================================================================

class MinimalOT2Experiment(BaseExperiment):
    """
    Minimal example of a custom OT-2 experiment.
    
    Shows the bare minimum required to create a custom experiment.
    """
    
    EXPERIMENT_TYPE = "MinimalOT2"
    REQUIRED_INSTRUMENTS = ["ot2"]
    
    def setup(self) -> None:
        """Setup is required but can be empty."""
        self.metadata.log_event("setup", "No setup required")
    
    def execute(self) -> None:
        """Main experiment logic."""
        ot2 = self.instruments["ot2"]
        
        # Do something with the OT-2
        info = ot2.get_robot_info()
        self.metadata.add_result("robot_info", info)
        
        protocols = ot2.list_protocols()
        self.metadata.add_result("available_protocols", protocols)


# =============================================================================
# Example 2: Experiment with User Input
# =============================================================================

class InteractiveExperiment(BaseExperiment):
    """
    Experiment that collects user input during execution.
    """
    
    EXPERIMENT_TYPE = "Interactive"
    REQUIRED_INSTRUMENTS = ["plate_reader"]
    
    def __init__(self, user_name: str, **instruments):
        super().__init__(user_name=user_name, **instruments)
        self.sample_names: List[str] = []
    
    def setup(self) -> None:
        """Collect sample information from user."""
        print("\n" + "=" * 50)
        print("SAMPLE SETUP")
        print("=" * 50)
        
        num_samples = int(input("How many samples? ") or "1")
        
        for i in range(num_samples):
            name = input(f"  Sample {i+1} name: ").strip() or f"Sample_{i+1}"
            self.sample_names.append(name)
        
        self.metadata.add_parameter("sample_names", self.sample_names)
        self.metadata.add_parameter("num_samples", num_samples)
        
        print(f"\nSamples: {self.sample_names}")
    
    def execute(self) -> None:
        """Measure each sample."""
        reader = self.instruments["plate_reader"]
        results = []
        
        for i, name in enumerate(self.sample_names):
            print(f"\n--- Sample {i+1}: {name} ---")
            input(f"Load sample '{name}' and press Enter...")
            
            path = reader.run_measurement(
                600,
                self.metadata.output_directory,
                filename_prefix=f"sample_{i+1}_{name}"
            )
            
            if path:
                self.metadata.add_data_file(path)
                results.append({
                    "sample": name,
                    "path": path,
                    "success": True
                })
            else:
                results.append({
                    "sample": name,
                    "success": False
                })
        
        self.metadata.add_result("sample_results", results)
        self.metadata.add_result("successful_samples", 
                                 sum(1 for r in results if r["success"]))


# =============================================================================
# Example 3: Experiment with Custom Parameters
# =============================================================================

class ParameterizedExperiment(BaseExperiment):
    """
    Experiment with many configurable parameters.
    """
    
    EXPERIMENT_TYPE = "Parameterized"
    REQUIRED_INSTRUMENTS = ["plate_reader"]
    
    def __init__(
        self,
        user_name: str,
        # Custom parameters
        wavelengths: List[int] = None,
        temperatures: List[float] = None,
        equilibration_time: float = 5.0,
        replicates: int = 1,
        **instruments
    ):
        super().__init__(user_name=user_name, **instruments)
        
        # Store parameters
        self.wavelengths = wavelengths or [600]
        self.temperatures = temperatures or [25.0]
        self.equilibration_time = equilibration_time
        self.replicates = replicates
        
        # Record in metadata
        self.metadata.add_parameter("wavelengths", self.wavelengths)
        self.metadata.add_parameter("temperatures", self.temperatures)
        self.metadata.add_parameter("equilibration_time", equilibration_time)
        self.metadata.add_parameter("replicates", replicates)
        
        # Calculate expected measurements
        total = len(self.wavelengths) * len(self.temperatures) * replicates
        self.metadata.add_parameter("expected_measurements", total)
    
    def setup(self) -> None:
        """Verify configuration and prepare."""
        print("\n" + "=" * 50)
        print("EXPERIMENT CONFIGURATION")
        print("=" * 50)
        print(f"Wavelengths: {self.wavelengths}")
        print(f"Temperatures: {self.temperatures}")
        print(f"Equilibration time: {self.equilibration_time}s")
        print(f"Replicates per condition: {self.replicates}")
        print(f"Total measurements: {self.metadata.parameters['expected_measurements']}")
        
        confirm = input("\nProceed? (yes/no): ")
        if confirm.lower() != "yes":
            raise RuntimeError("Cancelled by user")
    
    def execute(self) -> None:
        """Run the full measurement matrix."""
        reader = self.instruments["plate_reader"]
        measurements = []
        
        for temp in self.temperatures:
            print(f"\n--- Temperature: {temp}°C ---")
            
            # Set temperature
            reader.set_temperature(temp)

            tolerance = 0.2
            stable_duration = 15.0      # seconds
            poll_interval = 1.0         # seconds

            print(f"Equilibrating to {temp} °C (±{tolerance} °C)...")

            stable_start = None

            while True:
                current_temp, *_ = reader.get_temperature()

                if abs(current_temp - temp) <= tolerance:
                    if stable_start is None:
                        stable_start = time.time()
                    elif time.time() - stable_start >= stable_duration:
                        print(f"Temperature equilibrated at {current_temp:.2f} °C")
                        break
                else:
                    stable_start = None

                time.sleep(poll_interval)
     
            for wl in self.wavelengths:
                for rep in range(1, self.replicates + 1):
                    print(f"  Measuring: {temp}°C, {wl}nm, replicate {rep}")
                    
                    path = reader.run_measurement(
                        wl,
                        self.metadata.output_directory,
                        filename_prefix=f"T{temp}_WL{wl}_rep{rep}"
                    )
                    
                    measurement = {
                        "temperature": temp,
                        "wavelength": wl,
                        "replicate": rep,
                        "path": path,
                        "success": path is not None
                    }
                    measurements.append(measurement)
                    
                    if path:
                        self.metadata.add_data_file(path)
        
        self.metadata.add_result("measurements", measurements)
        self.metadata.add_result("successful", 
                                 sum(1 for m in measurements if m["success"]))


# =============================================================================
# Example 4: Experiment with Finalization
# =============================================================================

class ExperimentWithCleanup(BaseExperiment):
    """
    Experiment that does cleanup/finalization after execution.
    """
    
    EXPERIMENT_TYPE = "WithCleanup"
    REQUIRED_INSTRUMENTS = ["plate_reader"]
    
    def setup(self) -> None:
        """Standard setup."""
        print("Setup complete")
    
    def execute(self) -> None:
        """Main experiment."""
        reader = self.instruments["plate_reader"]
        
        # Take some measurements
        path = reader.run_measurement(
            600,
            self.metadata.output_directory,
            filename_prefix="main_measurement"
        )
        
        if path:
            self.metadata.add_data_file(path)
            self.metadata.add_result("measurement_path", path)
    
    def finalize(self) -> None:
        """
        Cleanup and summary generation.
        
        This runs even if execute() fails (within the try/finally block).
        """
        reader = self.instruments["plate_reader"]
        
        # Return to room temperature
        print("\nReturning to room temperature...")
        reader.set_temperature(25.0)
        
        # Generate summary
        print("\n" + "=" * 50)
        print("EXPERIMENT SUMMARY")
        print("=" * 50)
        print(f"ID: {self.metadata.experiment_id}")
        print(f"Status: {self.metadata.status}")
        print(f"Data files: {len(self.metadata.data_files)}")
        print(f"Events logged: {len(self.metadata.event_log)}")
        
        # Add summary to metadata
        self.metadata.add_result("summary_generated", True)


# =============================================================================
# Example 5: Combined Instruments Custom Experiment
# =============================================================================

class ScreeningExperiment(BaseExperiment):
    """
    Complex experiment using both OT-2 and plate reader for screening.
    """
    
    EXPERIMENT_TYPE = "Screening"
    REQUIRED_INSTRUMENTS = ["ot2", "plate_reader"]
    OPTIONAL_INSTRUMENTS = []  # Could add more instruments here
    
    def __init__(
        self,
        user_name: str,
        preparation_protocol: str,
        screening_wavelengths: List[int],
        **instruments
    ):
        super().__init__(user_name=user_name, **instruments)
        
        self.preparation_protocol = preparation_protocol
        self.screening_wavelengths = screening_wavelengths
        
        self.metadata.add_parameter("preparation_protocol", preparation_protocol)
        self.metadata.add_parameter("screening_wavelengths", screening_wavelengths)
    
    def setup(self) -> None:
        """Upload protocol and collect backgrounds."""
        ot2 = self.instruments["ot2"]
        reader = self.instruments["plate_reader"]
        
        # Upload OT-2 protocol
        print("Uploading preparation protocol to OT-2...")
        if not ot2.upload_protocol(self.preparation_protocol):
            raise RuntimeError("Failed to upload protocol")
        
        # Collect backgrounds at all wavelengths
        backgrounds = {}
        for wl in self.screening_wavelengths:
            print(f"\nCollecting background at {wl}nm...")
            print("Insert empty plate.")
            input("Press Enter when ready...")
            
            path = reader.collect_background(
                wl,
                self.metadata.output_directory
            )
            backgrounds[wl] = path
            if path:
                self.metadata.add_data_file(path)
        
        self.metadata.add_result("backgrounds", backgrounds)
    
    def execute(self) -> None:
        """Run preparation and screening."""
        ot2 = self.instruments["ot2"]
        reader = self.instruments["plate_reader"]
        
        # Run OT-2 preparation
        print("\n--- Running OT-2 Preparation ---")
        protocol_name = os.path.basename(self.preparation_protocol)
        success = ot2.run_protocol(protocol_name)
        
        self.metadata.add_result("preparation_success", success)
        
        if not success:
            if input("Preparation may have failed. Continue? (yes/no): ").lower() != "yes":
                raise RuntimeError("Aborted after preparation failure")
        
        # Screen at each wavelength
        print("\n--- Running Screening ---")
        print("Insert prepared plate.")
        input("Press Enter when ready...")
        
        screen_results = {}
        for wl in self.screening_wavelengths:
            print(f"\nScreening at {wl}nm...")
            path = reader.run_measurement(
                wl,
                self.metadata.output_directory,
                filename_prefix=f"screen_{wl}nm"
            )
            
            screen_results[wl] = path
            if path:
                self.metadata.add_data_file(path)
        
        self.metadata.add_result("screening_results", screen_results)
        self.metadata.add_result("wavelengths_measured", 
                                 [wl for wl, p in screen_results.items() if p])


# =============================================================================
# Running the Examples
# =============================================================================

def run_minimal_example():
    """Run the minimal OT-2 experiment."""
    print("\n" + "=" * 60)
    print("Running Minimal OT-2 Experiment")
    print("=" * 60)
    
    with OT2Instrument() as ot2:
        exp = MinimalOT2Experiment(
            user_name="Demo User",
            ot2=ot2
        )
        metadata = exp.run()
        print(f"\nResult: {metadata.results_summary}")


def run_parameterized_example():
    """Run the parameterized experiment."""
    print("\n" + "=" * 60)
    print("Running Parameterized Experiment")
    print("=" * 60)
    
    print("\nNote: This requires a plate reader connection.")
    print("Please start Nano_Control_Client.py first.")
    input("Press Enter when ready...")
    
    with PlateReaderInstrument(auto_launch=True) as reader:
        exp = ParameterizedExperiment(
            user_name="Demo User",
            wavelengths=[600],
            temperatures=[25.0, 25.5],
            equilibration_time=5.0,
            replicates=1,
            plate_reader=reader
        )
        metadata = exp.run()
        print(f"\nSuccessful measurements: {metadata.results_summary.get('successful')}")


if __name__ == "__main__":
    print("\nCustom Experiment Examples")
    print("=" * 60)
    print("1. Minimal OT-2 experiment")
    print("2. Parameterized plate reader experiment")
    print("3. View example code only")
    print("=" * 60)
    
    choice = input("Select (1-3): ").strip()
    
    if choice == "1":
        run_minimal_example()
    elif choice == "2":
        run_parameterized_example()
    elif choice == "3":
        print("\nReview this file to see custom experiment examples.")
        print("Key points:")
        print("  1. Subclass BaseExperiment")
        print("  2. Set EXPERIMENT_TYPE and REQUIRED_INSTRUMENTS")
        print("  3. Implement setup() and execute()")
        print("  4. Optionally implement finalize()")
        print("  5. Use self.metadata to record parameters and results")
    else:
        print("Invalid choice")
