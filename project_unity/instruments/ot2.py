"""
OT-2 liquid handling robot instrument.

Provides high-level control of the Opentrons OT-2 robot via SSH,
including protocol upload and execution.
"""

import os
import subprocess
import time
from typing import Optional, Tuple

import paramiko

from ..config import OT2Config, get_default_ot2_config
from ..utils.logging import log_msg
from .base import BaseInstrument, InstrumentStatus


class OT2Instrument(BaseInstrument):
    """
    Opentrons OT-2 liquid handling robot.
    
    Provides methods for uploading protocols, executing them, and
    monitoring the robot via SSH connection.
    
    Example:
        # Using context manager (recommended)
        with OT2Instrument() as ot2:
            ot2.upload_protocol("my_protocol.py")
            success = ot2.run_protocol("my_protocol.py")
            print(f"Protocol {'completed' if success else 'failed'}")
        
        # Manual connection management
        ot2 = OT2Instrument()
        try:
            ot2.connect()
            ot2.upload_protocol("my_protocol.py")
            ot2.run_protocol("my_protocol.py")
        finally:
            ot2.disconnect()
        
        # Custom configuration
        config = OT2Config(hostname="192.168.1.100")
        with OT2Instrument(config=config) as ot2:
            ...
    
    Attributes:
        config: OT2Config with connection settings
    """
    
    name = "OT-2"
    instrument_type = "OT2"
    
    def __init__(self, config: Optional[OT2Config] = None):
        """
        Initialize OT-2 instrument.
        
        Args:
            config: OT-2 configuration. Uses defaults if not provided.
        """
        self.config = config or get_default_ot2_config()
        self._ssh: Optional[paramiko.SSHClient] = None
        self._connected = False
    
    def connect(self) -> bool:
        """
        Establish SSH connection to the OT-2.
        
        Returns:
            True if connection was successful.
            
        Raises:
            Exception: If connection fails after retries.
        """
        if self._connected and self._ssh:
            return True
        
        try:
            log_msg(f"Connecting to OT-2 at {self.config.hostname}...")
            
            self._ssh = paramiko.SSHClient()
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._ssh.connect(
                self.config.hostname,
                username=self.config.username,
                key_filename=self.config.ssh_key_path,
                passphrase=self.config.ssh_passphrase or None
            )
            
            self._connected = True
            log_msg("Connected to OT-2 successfully.")
            return True
            
        except Exception as e:
            log_msg(f"Failed to connect to OT-2: {e}")
            self._connected = False
            raise
    
    def disconnect(self) -> None:
        """Close the SSH connection."""
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
            self._ssh = None
        self._connected = False
        log_msg("Disconnected from OT-2.")
    
    def status(self) -> InstrumentStatus:
        """
        Get current OT-2 status.
        
        Returns:
            InstrumentStatus with connection and ready state.
        """
        details = {}
        ready = False
        
        if self._connected and self._ssh:
            try:
                # Try to get system info
                stdout, stderr = self._execute_command("uname -a")
                details["system_info"] = stdout.strip()
                ready = True
            except Exception as e:
                details["error"] = str(e)
        
        return InstrumentStatus(
            connected=self._connected,
            ready=ready,
            details=details
        )
    
    def test_connection(self) -> bool:
        """
        Test the SSH connection with a simple command.
        
        Returns:
            True if connection is working.
        """
        try:
            stdout, stderr = self._execute_command('echo "OT-2 Connection OK"')
            return "Connection OK" in stdout
        except Exception:
            return False
    
    def _execute_command(self, command: str) -> Tuple[str, str]:
        """
        Execute a command on the OT-2.
        
        Args:
            command: Shell command to execute.
            
        Returns:
            Tuple of (stdout, stderr) as strings.
            
        Raises:
            RuntimeError: If not connected.
        """
        if not self._ssh or not self._connected:
            raise RuntimeError("Not connected to OT-2")
        
        stdin, stdout, stderr = self._ssh.exec_command(command)
        return stdout.read().decode(), stderr.read().decode()
    
    def upload_protocol(self, local_path: str) -> bool:
        """
        Upload a protocol file to the OT-2 via SCP.
        
        Args:
            local_path: Local path of the file to upload.
            
        Returns:
            True if upload was successful.
        """
        if not os.path.exists(local_path):
            log_msg(f"File not found: {local_path}")
            return False
        
        scp_command = [
            "scp",
            "-i", self.config.ssh_key_path,
            "-O",  # Force legacy SCP protocol
            local_path,
            f"{self.config.username}@{self.config.hostname}:{self.config.protocol_dest}"
        ]
        
        try:
            log_msg(f"Uploading {os.path.basename(local_path)} to OT-2...")
            result = subprocess.run(
                scp_command,
                check=True,
                text=True,
                capture_output=True
            )
            log_msg("File uploaded successfully.")
            return True
            
        except subprocess.CalledProcessError as e:
            log_msg(f"Upload failed: {e}")
            log_msg(f"Error output: {e.stderr}")
            return False
    
    def upload_file(self, local_path: str) -> bool:
        """Alias for upload_protocol for clarity."""
        return self.upload_protocol(local_path)
    
    def run_protocol(
        self,
        protocol_name: str,
        timeout: float = 3600.0
    ) -> bool:
        """
        Execute a protocol on the OT-2.
        
        The protocol must already be uploaded to the OT-2.
        
        Args:
            protocol_name: Name of the protocol file to execute.
            timeout: Maximum time to wait for protocol completion (seconds).
            
        Returns:
            True if protocol completed successfully.
        """
        if not self._ssh or not self._connected:
            raise RuntimeError("Not connected to OT-2")
        
        protocol_path = f"'{self.config.protocol_dest}/{protocol_name}'"
        command = f'sh -l -c "opentrons_execute {protocol_path}"'
        
        log_msg(f"Running OT-2 protocol: {protocol_name}")
        
        try:
            stdin, stdout, stderr = self._ssh.exec_command(command)
            
            complete = False
            start_time = time.time()
            full_output = []
            
            while True:
                # Check timeout
                if time.time() - start_time > timeout:
                    log_msg("Protocol execution timed out")
                    return False
                
                line = stdout.readline()
                if not line:
                    break
                
                print(line, end='')
                full_output.append(line)
                
                if "Protocol Finished" in line:
                    log_msg("Protocol completed successfully.")
                    complete = True
                    break
                
                time.sleep(0.1)
            
            # Check if we missed the completion message
            if not complete and ' Protocol Finished\n' in full_output:
                complete = True
            
            if not complete:
                log_msg("Protocol end not detected in output.")
            
            return complete
            
        except Exception as e:
            log_msg(f"Error running protocol: {e}")
            return False

    def simulate_protocol(
            self,
            protocol_name: str,
            timeout: float = 3600.0
    ) -> bool:
        """
        Simulate a protocol on the OT-2.

        The protocol must already be uploaded to the OT-2.

        Args:
            protocol_name: Name of the protocol file to simulate.
            timeout: Maximum time to wait for protocol completion (seconds).

        Returns:
            True if protocol completed successfully.
        """
        if not self._ssh or not self._connected:
            raise RuntimeError("Not connected to OT-2")

        protocol_path = f"'{self.config.protocol_dest}/{protocol_name}'"
        command = f'sh -l -c "opentrons_simulate {protocol_path}"'

        log_msg(f"Simulating OT-2 protocol: {protocol_name}")

        try:
            stdin, stdout, stderr = self._ssh.exec_command(command)

            complete = False
            start_time = time.time()
            full_output = []

            while True:
                # Check timeout
                if time.time() - start_time > timeout:
                    log_msg("Protocol simulation timed out")
                    return False

                line = stdout.readline()
                if not line:
                    break

                print(line, end='')
                full_output.append(line)

                if "Protocol Finished" in line:
                    log_msg("Protocol completed successfully.")
                    complete = True
                    break

                time.sleep(0.1)

            # Check if we missed the completion message
            if not complete and ' Protocol Finished\n' in full_output:
                complete = True

            if not complete:
                log_msg("Protocol end not detected in output.")

            return complete

        except Exception as e:
            log_msg(f"Error running protocol: {e}")
            return False
    
    def run_protocol_with_upload(
        self,
        protocol_path: str,
        additional_files: Optional[list] = None,
        timeout: float = 3600.0
    ) -> bool:
        """
        Upload and run a protocol in one step.
        
        Convenience method that uploads the protocol (and any additional files),
        then executes it.
        
        Args:
            protocol_path: Local path to the protocol file.
            additional_files: Optional list of additional files to upload
                             (e.g., CSV files with parameters).
            timeout: Maximum time to wait for protocol completion.
            
        Returns:
            True if protocol completed successfully.
        """
        # Upload protocol
        if not self.upload_protocol(protocol_path):
            return False
        
        # Upload additional files
        if additional_files:
            for file_path in additional_files:
                if not self.upload_file(file_path):
                    log_msg(f"Failed to upload: {file_path}")
                    return False
        
        # Run protocol
        protocol_name = os.path.basename(protocol_path)
        return self.run_protocol(protocol_name, timeout)
    
    def list_protocols(self) -> list:
        """
        List protocols currently on the OT-2.
        
        Returns:
            List of protocol filenames.
        """
        try:
            stdout, stderr = self._execute_command(
                f"ls -1 {self.config.protocol_dest}/*.py 2>/dev/null"
            )
            if stdout:
                return [os.path.basename(p) for p in stdout.strip().split('\n')]
            return []
        except Exception as e:
            log_msg(f"Failed to list protocols: {e}")
            return []
    
    def get_robot_info(self) -> dict:
        """
        Get information about the OT-2 robot.
        
        Returns:
            Dictionary with robot information.
        """
        info = {}
        
        try:
            stdout, _ = self._execute_command("uname -a")
            info["system"] = stdout.strip()
            
            stdout, _ = self._execute_command("python3 --version")
            info["python_version"] = stdout.strip()
            
            stdout, _ = self._execute_command("opentrons_execute --version 2>&1 || echo 'unknown'")
            info["opentrons_version"] = stdout.strip()
            
        except Exception as e:
            info["error"] = str(e)
        
        return info
