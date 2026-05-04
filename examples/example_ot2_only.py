"""
Example: OT-2 Only Experiment

This example demonstrates how to run an OT-2 protocol without
using the plate reader. Useful for sample preparation, liquid
handling, or any OT-2-only workflow.

Requirements:
    - OT-2 reachable on the Robot HTTP API (default port 31950)
    - Set OT2Config.hostname (and optionally http_port) if needed

Usage:
    python example_ot2_only.py
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from project_unity import (
    OT2Instrument,
    OT2ProtocolExperiment,
    OT2Config,
)


def example_basic_protocol():
    """
    Basic example: Run a single OT-2 protocol.
    """
    print("=" * 60)
    print("Example: Basic OT-2 Protocol Execution")
    print("=" * 60)
    
    # Path to your protocol file
    protocol_path = input("Enter path to OT-2 protocol file: ").strip()
    
    if not os.path.exists(protocol_path):
        print(f"Error: Protocol file not found: {protocol_path}")
        return
    
    # Get user name
    user_name = input("Enter your name: ").strip() or "User"
    
    # Create and run experiment
    with OT2Instrument() as ot2:
        # Optionally test connection first
        print("\nTesting OT-2 connection...")
        if not ot2.test_connection():
            print("Warning: Connection test failed. Proceeding anyway...")
        else:
            print("Connection OK!")
        
        # Create experiment
        exp = OT2ProtocolExperiment(
            user_name=user_name,
            protocol_path=protocol_path,
            ot2=ot2
        )
        
        print(f"\nExperiment: {exp.metadata.experiment_name}")
        print(f"Output directory: {exp.metadata.output_directory}")
        
        # Run it
        input("\nPress Enter to start the experiment...")
        metadata = exp.run()
        
        # Print results
        print("\n" + "=" * 60)
        print("EXPERIMENT COMPLETE")
        print("=" * 60)
        print(metadata)
        print(f"\nSuccess: {metadata.results_summary.get('success', 'Unknown')}")


def example_with_additional_files():
    """
    Example: Run protocol with additional files (like CSV data).
    """
    print("=" * 60)
    print("Example: OT-2 Protocol with Additional Files")
    print("=" * 60)
    
    protocol_path = input("Enter path to OT-2 protocol file: ").strip()
    csv_path = input("Enter path to volumes CSV file (or leave empty): ").strip()
    user_name = input("Enter your name: ").strip() or "User"
    
    additional_files = [csv_path] if csv_path and os.path.exists(csv_path) else []
    
    with OT2Instrument() as ot2:
        exp = OT2ProtocolExperiment(
            user_name=user_name,
            protocol_path=protocol_path,
            additional_files=additional_files,
            ot2=ot2
        )
        
        metadata = exp.run()
        print(f"\nExperiment completed with status: {metadata.status}")


def example_custom_config():
    """
    Example: Use custom OT-2 configuration.
    """
    print("=" * 60)
    print("Example: Custom OT-2 Configuration")
    print("=" * 60)
    
    # Create custom config for a different OT-2
    custom_config = OT2Config(
        hostname="192.168.1.100",  # Robot IP or hostname
        http_port=31950,
    )
    
    print(f"Connecting to OT-2 at {custom_config.hostname}")
    
    with OT2Instrument(config=custom_config) as ot2:
        # Check connection
        status = ot2.status()
        print(f"Status: {status}")
        
        # List available protocols
        protocols = ot2.list_protocols()
        print(f"Protocols on OT-2: {protocols}")


def example_direct_instrument_use():
    """
    Example: Use OT2Instrument directly without experiment wrapper.
    
    Useful for quick operations or building custom workflows.
    """
    print("=" * 60)
    print("Example: Direct Instrument Control")
    print("=" * 60)
    
    with OT2Instrument() as ot2:
        # Get robot info
        print("\nGetting OT-2 information...")
        info = ot2.get_robot_info()
        for key, value in info.items():
            print(f"  {key}: {value}")
        
        # List protocols
        print("\nProtocols on OT-2:")
        for protocol in ot2.list_protocols():
            print(f"  - {protocol}")
        
        # Upload and run a protocol manually
        protocol_path = input("\nEnter protocol to run (or press Enter to skip): ").strip()
        
        if protocol_path and os.path.exists(protocol_path):
            print(f"\nUploading {os.path.basename(protocol_path)}...")
            if ot2.upload_protocol(protocol_path):
                print("Upload successful!")
                
                if input("Run protocol? (yes/no): ").lower() == "yes":
                    success = ot2.run_protocol(os.path.basename(protocol_path))
                    print(f"Protocol {'completed' if success else 'may have failed'}")


if __name__ == "__main__":
    print("\nOT-2 Only Examples")
    print("=" * 60)
    print("1. Basic protocol execution")
    print("2. Protocol with additional files")
    print("3. Custom OT-2 configuration")
    print("4. Direct instrument control")
    print("=" * 60)
    
    choice = input("Select example (1-4): ").strip()
    
    if choice == "1":
        example_basic_protocol()
    elif choice == "2":
        example_with_additional_files()
    elif choice == "3":
        example_custom_config()
    elif choice == "4":
        example_direct_instrument_use()
    else:
        print("Invalid choice")
