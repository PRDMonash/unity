"""
Example: Plate Reader Only Experiments

This example demonstrates how to run plate reader measurements
without using the OT-2. Useful for manual sample preparation
or standalone absorbance measurements.

Requirements:
    - BMG SPECTROstar Nano plate reader connected
    - 32-bit Python installed (for ActiveX COM)
    - Nano_Control_Client.py ready to run

Note on 32-bit Client:
    The plate reader uses ActiveX COM which requires 32-bit Python.
    You have two options:
    1. Set auto_launch=True and configure python_32_path
    2. Manually start Nano_Control_Client.py before running this script

Usage:
    python example_plate_reader_only.py
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from project_unity import (
    PlateReaderInstrument,
    PlateReaderMeasurementExperiment,
    PlateReaderTimeCourseExperiment,
    PlateReaderTemperatureRampExperiment,
    ServerConfig,
)


def example_single_measurement():
    """
    Basic example: Take a single absorbance measurement.
    """
    print("=" * 60)
    print("Example: Single Plate Reader Measurement")
    print("=" * 60)
    
    user_name = input("Enter your name: ").strip() or "User"
    wavelength = int(input("Enter wavelength (nm) [600]: ").strip() or "600")
    
    print("\nPlease start Nano_Control_Client.py in 32-bit Python if not auto-launching.")
    
    # Connect to plate reader
    # Set auto_launch=True if you have 32-bit Python configured
    with PlateReaderInstrument(auto_launch=False) as reader:
        print("\nConnected to plate reader!")
        
        # Show current temperature
        temp1, temp2 = reader.get_temperature()
        print(f"Current temperature: {temp1}°C (lower), {temp2}°C (upper)")
        
        # Create and run experiment
        exp = PlateReaderMeasurementExperiment(
            user_name=user_name,
            wavelength=wavelength,
            collect_background=True,
            plate_reader=reader
        )
        
        print(f"\nExperiment: {exp.metadata.experiment_name}")
        print(f"Output: {exp.metadata.output_directory}")
        
        metadata = exp.run()
        
        print("\n" + "=" * 60)
        print("EXPERIMENT COMPLETE")
        print("=" * 60)
        print(metadata)
        
        if metadata.data_files:
            print(f"\nData files saved:")
            for f in metadata.data_files:
                print(f"  - {f}")


def example_time_course():
    """
    Example: Take measurements over time.
    """
    print("=" * 60)
    print("Example: Time Course Measurement")
    print("=" * 60)
    
    user_name = input("Enter your name: ").strip() or "User"
    wavelength = int(input("Enter wavelength (nm) [600]: ").strip() or "600")
    num_measurements = int(input("Number of measurements [5]: ").strip() or "5")
    interval = float(input("Interval between measurements (seconds) [60]: ").strip() or "60")
    
    print("\nPlease start Nano_Control_Client.py in 32-bit Python.")
    
    with PlateReaderInstrument(auto_launch=False) as reader:
        exp = PlateReaderTimeCourseExperiment(
            user_name=user_name,
            wavelength=wavelength,
            num_measurements=num_measurements,
            interval_seconds=interval,
            plate_reader=reader
        )
        
        print(f"\nWill take {num_measurements} measurements every {interval}s")
        print(f"Total time: ~{num_measurements * interval / 60:.1f} minutes")
        
        metadata = exp.run()
        
        print("\n" + "=" * 60)
        print("TIME COURSE COMPLETE")
        print("=" * 60)
        print(f"Successful measurements: {metadata.results_summary.get('successful_measurements')}")


def example_temperature_ramp():
    """
    Example: Measurements at different temperatures.
    """
    print("=" * 60)
    print("Example: Temperature Ramp Measurement")
    print("=" * 60)
    
    user_name = input("Enter your name: ").strip() or "User"
    wavelength = int(input("Enter wavelength (nm) [600]: ").strip() or "600")
    start_temp = float(input("Start temperature (°C) [25]: ").strip() or "25")
    end_temp = float(input("End temperature (°C) [45]: ").strip() or "45")
    step_size = float(input("Temperature step (°C) [2]: ").strip() or "2")
    bidirectional = input("Ramp back down? (yes/no) [no]: ").strip().lower() == "yes"
    
    print("\nPlease start Nano_Control_Client.py in 32-bit Python.")
    
    with PlateReaderInstrument(auto_launch=False) as reader:
        exp = PlateReaderTemperatureRampExperiment(
            user_name=user_name,
            wavelength=wavelength,
            start_temp=start_temp,
            end_temp=end_temp,
            step_size=step_size,
            bidirectional=bidirectional,
            stabilization_time=60.0,  # Wait 60s for temp to stabilize
            plate_reader=reader
        )
        
        num_steps = int(abs(end_temp - start_temp) / step_size) + 1
        if bidirectional:
            num_steps = num_steps * 2 - 1
        
        print(f"\nWill measure at {num_steps} temperature points")
        print(f"Temperature range: {start_temp}°C to {end_temp}°C")
        
        metadata = exp.run()
        
        print("\n" + "=" * 60)
        print("TEMPERATURE RAMP COMPLETE")
        print("=" * 60)
        print(f"Temperatures measured: {metadata.results_summary.get('temperatures_measured')}")


def example_direct_instrument_use():
    """
    Example: Use PlateReaderInstrument directly.
    """
    print("=" * 60)
    print("Example: Direct Plate Reader Control")
    print("=" * 60)
    
    print("\nPlease start Nano_Control_Client.py in 32-bit Python.")
    
    with PlateReaderInstrument(auto_launch=False) as reader:
        print("\nConnected!")
        
        while True:
            print("\nOptions:")
            print("1. Get temperature")
            print("2. Set temperature")
            print("3. Wait for stable temperature")
            print("4. Run measurement")
            print("5. Collect background")
            print("6. Exit")
            
            choice = input("\nChoice: ").strip()
            
            if choice == "1":
                temp1, temp2 = reader.get_temperature()
                print(f"Temperature: {temp1}°C (lower), {temp2}°C (upper)")
            
            elif choice == "2":
                temp = float(input("Target temperature (°C): "))
                reader.set_temperature(temp)
                print(f"Temperature set to {temp}°C")
            
            elif choice == "3":
                temp = float(input("Target temperature (°C): "))
                stable_time = float(input("Stabilization time (seconds) [60]: ") or "60")
                print(f"Waiting for {temp}°C to stabilize...")
                if reader.wait_for_stable_temperature(temp, stable_time=stable_time):
                    print("Temperature stabilized!")
                else:
                    print("Stabilization timeout")
            
            elif choice == "4":
                wavelength = int(input("Wavelength (nm) [600]: ") or "600")
                output_dir = input("Output directory: ").strip() or os.getcwd()
                path = reader.run_measurement(wavelength, output_dir)
                if path:
                    print(f"Measurement saved to: {path}")
                else:
                    print("Measurement failed")
            
            elif choice == "5":
                wavelength = int(input("Wavelength (nm) [600]: ") or "600")
                output_dir = input("Output directory: ").strip() or os.getcwd()
                path = reader.collect_background(wavelength, output_dir)
                if path:
                    print(f"Background saved to: {path}")
                else:
                    print("Background collection failed")
            
            elif choice == "6":
                break


def example_auto_launch():
    """
    Example: Auto-launch the 32-bit client.
    """
    print("=" * 60)
    print("Example: Auto-Launch 32-bit Client")
    print("=" * 60)
    
    print("\nThis example auto-launches the 32-bit client.")
    print("Configure the path to 32-bit Python below.")
    
    # Configure paths
    python_32_path = r"C:\Users\lachi\AppData\Local\Programs\Python\Python311-32\python.exe"
    client_script = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "Nano_Control_Client.py"
    )
    
    print(f"\n32-bit Python: {python_32_path}")
    print(f"Client script: {client_script}")
    
    if not os.path.exists(python_32_path):
        print(f"\nError: 32-bit Python not found at {python_32_path}")
        print("Please install 32-bit Python or update the path.")
        return
    
    # Use auto_launch=True
    with PlateReaderInstrument(
        auto_launch=True,
        python_32_path=python_32_path,
        client_script_path=client_script,
        connection_timeout=60.0
    ) as reader:
        print("\nConnected with auto-launched client!")
        
        temp1, temp2 = reader.get_temperature()
        print(f"Current temperature: {temp1}°C, {temp2}°C")
        
        # Run a quick measurement
        print("\nRunning test measurement...")
        output_dir = os.path.join(os.getcwd(), "test_output")
        path = reader.run_measurement(600, output_dir)
        
        if path:
            print(f"Measurement saved: {path}")
        else:
            print("Measurement failed")


if __name__ == "__main__":
    print("\nPlate Reader Only Examples")
    print("=" * 60)
    print("1. Single measurement")
    print("2. Time course")
    print("3. Temperature ramp")
    print("4. Direct instrument control")
    print("5. Auto-launch 32-bit client")
    print("=" * 60)
    
    choice = input("Select example (1-5): ").strip()
    
    if choice == "1":
        example_single_measurement()
    elif choice == "2":
        example_time_course()
    elif choice == "3":
        example_temperature_ramp()
    elif choice == "4":
        example_direct_instrument_use()
    elif choice == "5":
        example_auto_launch()
    else:
        print("Invalid choice")
