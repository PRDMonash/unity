"""
OT-2 protocol execution experiment.

Simple experiment template for running OT-2 protocols without
plate reader involvement.
"""

import os
from typing import Optional, List

from ..utils.logging import log_msg
from .base import BaseExperiment


class OT2ProtocolExperiment(BaseExperiment):
    """
    Simple OT-2-only experiment for running protocols.
    
    This experiment uploads and runs a single protocol on the OT-2,
    optionally with additional supporting files (like CSV data files).
    
    Example:
        from ot2_controller.instruments import OT2Instrument
        from ot2_controller.experiments import OT2ProtocolExperiment
        
        with OT2Instrument() as ot2:
            exp = OT2ProtocolExperiment(
                user_name="Lachlan",
                protocol_path="my_protocol.py",
                ot2=ot2
            )
            metadata = exp.run()
            
            if metadata.results_summary.get("success"):
                print("Protocol completed successfully!")
    
    Attributes:
        protocol_path: Path to the protocol file
        additional_files: Optional list of additional files to upload
    """
    
    EXPERIMENT_TYPE = "OT2Protocol"
    REQUIRED_INSTRUMENTS = ["ot2"]
    
    def __init__(
        self,
        user_name: str,
        protocol_path: str,
        additional_files: Optional[List[str]] = None,
        protocol_timeout: float = 3600.0,
        experiment_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        **instruments
    ):
        """
        Initialize OT-2 protocol experiment.
        
        Args:
            user_name: Name of the user running the experiment
            protocol_path: Path to the OT-2 protocol file
            additional_files: Optional list of additional files to upload
                             (e.g., CSV files with parameters)
            protocol_timeout: Maximum time to wait for protocol (seconds)
            experiment_name: Human-readable name for this run
            output_dir: Directory for output files
            **instruments: Must include ot2=OT2Instrument()
        """
        super().__init__(
            user_name=user_name,
            experiment_name=experiment_name or f"OT-2: {os.path.basename(protocol_path)}",
            output_dir=output_dir,
            **instruments
        )
        
        self.protocol_path = protocol_path
        self.additional_files = additional_files or []
        self.protocol_timeout = protocol_timeout
        
        # Record parameters
        self.metadata.add_parameter("protocol_path", protocol_path)
        self.metadata.add_parameter("protocol_name", os.path.basename(protocol_path))
        self.metadata.add_parameter("additional_files", self.additional_files)
        self.metadata.add_parameter("protocol_timeout", protocol_timeout)
    
    def setup(self) -> None:
        """Upload protocol and additional files to OT-2."""
        ot2 = self.instruments["ot2"]
        
        # Verify protocol exists
        if not os.path.exists(self.protocol_path):
            raise FileNotFoundError(f"Protocol not found: {self.protocol_path}")
        
        # Upload protocol
        log_msg(f"Uploading protocol: {os.path.basename(self.protocol_path)}")
        if not ot2.upload_protocol(self.protocol_path):
            raise RuntimeError("Failed to upload protocol")
        
        self.log_event("upload", "Protocol uploaded", {
            "file": self.protocol_path
        })
        self.metadata.log_instrument_operation("ot2", f"uploaded {self.protocol_path}")
        
        # Upload additional files
        for file_path in self.additional_files:
            if not os.path.exists(file_path):
                log_msg(f"Warning: Additional file not found: {file_path}")
                continue
            
            log_msg(f"Uploading: {os.path.basename(file_path)}")
            if ot2.upload_file(file_path):
                self.log_event("upload", "Additional file uploaded", {
                    "file": file_path
                })
                self.metadata.log_instrument_operation("ot2", f"uploaded {file_path}")
            else:
                log_msg(f"Warning: Failed to upload {file_path}")
    
    def execute(self) -> None:
        """Run the protocol on the OT-2."""
        ot2 = self.instruments["ot2"]
        protocol_name = os.path.basename(self.protocol_path)
        
        log_msg(f"Running protocol: {protocol_name}")
        self.log_event("execution", "Starting protocol execution")
        self.metadata.log_instrument_operation("ot2", f"running {protocol_name}")
        
        success = ot2.run_protocol(protocol_name, self.protocol_timeout)
        
        self.metadata.add_result("success", success)
        self.metadata.add_result("protocol_name", protocol_name)
        
        if success:
            self.log_event("execution", "Protocol completed successfully")
            self.metadata.log_instrument_operation("ot2", "protocol completed")
        else:
            self.log_event("execution", "Protocol may not have completed successfully")
            self.metadata.log_instrument_operation("ot2", "protocol status uncertain")


class OT2MultiProtocolExperiment(BaseExperiment):
    """
    OT-2 experiment for running multiple protocols in sequence.
    
    Example:
        with OT2Instrument() as ot2:
            exp = OT2MultiProtocolExperiment(
                user_name="Lachlan",
                protocols=[
                    "step1_distribute.py",
                    "step2_mix.py",
                    "step3_transfer.py"
                ],
                ot2=ot2
            )
            exp.run()
    """
    
    EXPERIMENT_TYPE = "OT2MultiProtocol"
    REQUIRED_INSTRUMENTS = ["ot2"]
    
    def __init__(
        self,
        user_name: str,
        protocols: List[str],
        pause_between: bool = True,
        experiment_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        **instruments
    ):
        """
        Initialize multi-protocol experiment.
        
        Args:
            user_name: Name of the user
            protocols: List of protocol file paths to run in order
            pause_between: Whether to pause for user confirmation between protocols
            experiment_name: Human-readable name
            output_dir: Output directory
            **instruments: Must include ot2=OT2Instrument()
        """
        super().__init__(
            user_name=user_name,
            experiment_name=experiment_name or "OT-2 Multi-Protocol",
            output_dir=output_dir,
            **instruments
        )
        
        self.protocols = protocols
        self.pause_between = pause_between
        
        self.metadata.add_parameter("protocols", protocols)
        self.metadata.add_parameter("pause_between", pause_between)
    
    def setup(self) -> None:
        """Upload all protocols."""
        ot2 = self.instruments["ot2"]
        
        for protocol_path in self.protocols:
            if not os.path.exists(protocol_path):
                raise FileNotFoundError(f"Protocol not found: {protocol_path}")
            
            log_msg(f"Uploading: {os.path.basename(protocol_path)}")
            if not ot2.upload_protocol(protocol_path):
                raise RuntimeError(f"Failed to upload: {protocol_path}")
    
    def execute(self) -> None:
        """Run all protocols in sequence."""
        ot2 = self.instruments["ot2"]
        results = []
        
        for i, protocol_path in enumerate(self.protocols):
            protocol_name = os.path.basename(protocol_path)
            log_msg(f"\nRunning protocol {i+1}/{len(self.protocols)}: {protocol_name}")
            
            if self.pause_between and i > 0:
                input(f"Press Enter to run {protocol_name}...")
            
            success = ot2.run_protocol(protocol_name)
            results.append({
                "protocol": protocol_name,
                "success": success,
                "order": i + 1
            })
            
            if not success:
                log_msg(f"Warning: Protocol {protocol_name} may not have completed")
        
        self.metadata.add_result("protocol_results", results)
        self.metadata.add_result("all_successful", all(r["success"] for r in results))
