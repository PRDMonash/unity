"""
Example: Combined OT-2 and Plate Reader Experiments

This example demonstrates how to use both the OT-2 and plate reader
together in a coordinated workflow. The OT-2 prepares samples,
and the plate reader measures them.

Requirements:
    - OT-2 robot connected and accessible via SSH
    - BMG SPECTROstar Nano plate reader connected
    - 32-bit Python with Nano_Control_Client.py

Usage:
    python example_combined.py
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from project_unity import (
    OT2Instrument,
    PlateReaderInstrument,
    OT2AndPlateReaderExperiment,
    IterativeOptimizationExperiment,
    BaseExperiment,
)


def example_basic_combined():
    """
    Basic example: OT-2 prepares samples, plate reader measures.
    """
    print("=" * 60)
    print("Example: Basic Combined Workflow")
    print("=" * 60)
    
    user_name = input("Enter your name: ").strip() or "User"
    protocol_path = input("Enter path to OT-2 protocol: ").strip()
    wavelength = int(input("Enter measurement wavelength (nm) [600]: ").strip() or "600")
    
    if not os.path.exists(protocol_path):
        print(f"Error: Protocol file not found: {protocol_path}")
        return
    
    print("\nPlease start Nano_Control_Client.py in 32-bit Python.")
    input("Press Enter when ready...")
    
    # Connect to both instruments
    with OT2Instrument() as ot2, PlateReaderInstrument(auto_launch=True) as reader:
        print("\nConnected to both instruments!")
        
        # Show status
        print(f"OT-2 status: {ot2.status()}")
        print(f"Plate reader status: {reader.status()}")
        
        # Create combined experiment
        exp = OT2AndPlateReaderExperiment(
            user_name=user_name,
            protocol_path=protocol_path,
            wavelength=wavelength,
            collect_background=True,
            ot2=ot2,
            plate_reader=reader
        )
        
        print(f"\nExperiment: {exp.metadata.experiment_name}")
        print(f"Output: {exp.metadata.output_directory}")
        
        input("\nPress Enter to start...")
        metadata = exp.run()
        
        print("\n" + "=" * 60)
        print("EXPERIMENT COMPLETE")
        print("=" * 60)
        print(metadata)
        
        if metadata.data_files:
            print(f"\nData files:")
            for f in metadata.data_files:
                print(f"  - {f}")


def example_iterative_optimization():
    """
    Example: Multiple rounds of preparation and measurement.
    """
    print("=" * 60)
    print("Example: Iterative Optimization Workflow")
    print("=" * 60)
    
    user_name = input("Enter your name: ").strip() or "User"
    protocol_path = input("Enter path to OT-2 protocol: ").strip()
    volumes_csv = input("Enter path to volumes CSV: ").strip()
    max_iterations = int(input("Maximum iterations [5]: ").strip() or "5")
    wavelength = int(input("Measurement wavelength (nm) [600]: ").strip() or "600")
    
    print("\nPlease start Nano_Control_Client.py in 32-bit Python.")
    input("Press Enter when ready...")
    
    with OT2Instrument() as ot2, PlateReaderInstrument(auto_launch=False) as reader:
        exp = IterativeOptimizationExperiment(
            user_name=user_name,
            protocol_path=protocol_path,
            volumes_csv_path=volumes_csv,
            wavelength=wavelength,
            max_iterations=max_iterations,
            ot2=ot2,
            plate_reader=reader
        )
        
        print(f"\nWill run up to {max_iterations} optimization iterations")
        
        metadata = exp.run()
        
        print("\n" + "=" * 60)
        print("OPTIMIZATION COMPLETE")
        print("=" * 60)
        print(f"Total iterations: {metadata.results_summary.get('total_iterations')}")


def example_custom_combined():
    """
    Example: Build a custom combined experiment.
    """
    print("=" * 60)
    print("Example: Custom Combined Experiment")
    print("=" * 60)
    
    class DilutionSeriesExperiment(BaseExperiment):
        """
        Custom experiment: OT-2 creates dilution series, plate reader measures.
        """
        
        EXPERIMENT_TYPE = "DilutionSeries"
        REQUIRED_INSTRUMENTS = ["ot2", "plate_reader"]
        
        def __init__(
            self,
            user_name: str,
            protocol_path: str,
            wavelengths: list,
            **instruments
        ):
            super().__init__(user_name=user_name, **instruments)
            self.protocol_path = protocol_path
            self.wavelengths = wavelengths
            
            self.metadata.add_parameter("protocol_path", protocol_path)
            self.metadata.add_parameter("wavelengths", wavelengths)
        
        def setup(self):
            """Collect background and upload protocol."""
            reader = self.instruments["plate_reader"]
            ot2 = self.instruments["ot2"]
            
            # Collect background at each wavelength
            for wl in self.wavelengths:
                print(f"\nCollecting background at {wl}nm")
                print("Insert empty plate...")
                input("Press Enter when ready...")
                
                bg_path = reader.collect_background(
                    wl, 
                    self.metadata.output_directory
                )
                if bg_path:
                    self.metadata.add_data_file(bg_path)
            
            # Upload protocol
            ot2.upload_protocol(self.protocol_path)
        
        def execute(self):
            """Run protocol and measure at each wavelength."""
            ot2 = self.instruments["ot2"]
            reader = self.instruments["plate_reader"]
            
            # Run OT-2 protocol to create dilution series
            protocol_name = os.path.basename(self.protocol_path)
            print(f"\nRunning OT-2 protocol: {protocol_name}")
            ot2.run_protocol(protocol_name)
            
            print("\nOT-2 complete. Insert plate for measurement.")
            input("Press Enter when ready...")
            
            # Measure at each wavelength
            measurements = []
            for wl in self.wavelengths:
                print(f"\nMeasuring at {wl}nm...")
                path = reader.run_measurement(
                    wl,
                    self.metadata.output_directory,
                    filename_prefix=f"dilution_{wl}nm"
                )
                
                if path:
                    self.metadata.add_data_file(path)
                    measurements.append({"wavelength": wl, "path": path})
            
            self.metadata.add_result("measurements", measurements)
    
    # Run the custom experiment
    user_name = input("Enter your name: ").strip() or "User"
    protocol_path = input("Enter path to OT-2 protocol: ").strip()
    wavelengths = [600, 280, 450]  # Multiple wavelengths
    
    print(f"\nWill measure at wavelengths: {wavelengths}")
    print("\nPlease start Nano_Control_Client.py in 32-bit Python.")
    input("Press Enter when ready...")
    
    with OT2Instrument() as ot2, PlateReaderInstrument(auto_launch=False) as reader:
        exp = DilutionSeriesExperiment(
            user_name=user_name,
            protocol_path=protocol_path,
            wavelengths=wavelengths,
            ot2=ot2,
            plate_reader=reader
        )
        
        metadata = exp.run()
        
        print("\n" + "=" * 60)
        print("CUSTOM EXPERIMENT COMPLETE")
        print("=" * 60)
        print(metadata)


def example_sequential_instruments():
    """
    Example: Use instruments sequentially without experiment wrapper.
    """
    print("=" * 60)
    print("Example: Sequential Instrument Control")
    print("=" * 60)
    
    print("\nThis example shows manual control of both instruments.")
    print("\nPlease start Nano_Control_Client.py in 32-bit Python.")
    input("Press Enter when ready...")
    
    # Connect to both instruments
    with OT2Instrument() as ot2, PlateReaderInstrument(auto_launch=False) as reader:
        print("\nBoth instruments connected!")
        
        # OT-2 operations
        print("\n--- OT-2 Operations ---")
        ot2_info = ot2.get_robot_info()
        print(f"OT-2 Python: {ot2_info.get('python_version', 'Unknown')}")
        
        protocols = ot2.list_protocols()
        print(f"Available protocols: {protocols[:5]}..." if len(protocols) > 5 else f"Protocols: {protocols}")
        
        # Plate reader operations
        print("\n--- Plate Reader Operations ---")
        temp1, temp2 = reader.get_temperature()
        print(f"Temperature: {temp1}°C (lower), {temp2}°C (upper)")
        
        # Interactive control
        while True:
            print("\n" + "-" * 40)
            print("Options:")
            print("1. Upload OT-2 protocol")
            print("2. Run OT-2 protocol")
            print("3. Set plate reader temperature")
            print("4. Run plate reader measurement")
            print("5. Exit")
            
            choice = input("Choice: ").strip()
            
            if choice == "1":
                path = input("Protocol path: ").strip()
                if os.path.exists(path):
                    if ot2.upload_protocol(path):
                        print("Upload successful!")
            
            elif choice == "2":
                name = input("Protocol name: ").strip()
                print("Running protocol...")
                success = ot2.run_protocol(name)
                print(f"Result: {'Success' if success else 'May have failed'}")
            
            elif choice == "3":
                temp = float(input("Target temp (°C): "))
                reader.set_temperature(temp)
                print(f"Temperature set to {temp}°C")
            
            elif choice == "4":
                wl = int(input("Wavelength (nm): ") or "600")
                out = input("Output directory: ") or os.getcwd()
                path = reader.run_measurement(wl, out)
                if path:
                    print(f"Saved to: {path}")
            
            elif choice == "5":
                break

def example_temperature_ramp():
    with OT2Instrument() as ot2, PlateReaderInstrument(auto_launch=True) as reader:
        # ot2.upload_protocol("dummy_ot2_protocol.py")
        # ot2.run_protocol("dummy_ot2_protocol.py")
        reader.set_temperature(25.0)
        reader.wait_for_stable_temperature(25.0, 0.2, 30)
        reader.run_measurement(600, r"C:\Users\lachi\OneDrive\Documents\Uni\PhD\Python\ot2\experiment_output")


if __name__ == "__main__":
    print("\nCombined OT-2 + Plate Reader Examples")
    print("=" * 60)
    print("1. Basic combined workflow")
    print("2. Iterative optimization")
    print("3. Custom combined experiment")  
    print("4. Sequential instrument control")
    print("5. Temperature ramp")
    print("=" * 60)
    
    choice = input("Select example (1-5): ").strip()
    
    if choice == "1":
        example_basic_combined()
    elif choice == "2":
        example_iterative_optimization()
    elif choice == "3":
        example_custom_combined()
    elif choice == "4":
        example_sequential_instruments()
    elif choice == "5":
        example_temperature_ramp()
    else:
        print("Invalid choice")
