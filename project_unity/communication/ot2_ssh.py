"""
OT-2 robot communication via SSH and SCP.

Provides file transfer and protocol execution on the OT-2.
"""

import subprocess
import time
from typing import Optional

import paramiko

from ..config import OT2Config, get_default_ot2_config
from ..utils.logging import log_msg


def run_subprocess(
    file_path: str,
    config: Optional[OT2Config] = None
) -> bool:
    """
    Transfer a file to the OT-2 using SCP.
    
    Args:
        file_path: Local path of the file to transfer.
        config: OT-2 configuration. Uses defaults if not provided.
        
    Returns:
        True if transfer successful, False otherwise.
    """
    config = config or get_default_ot2_config()
    
    scp_command = [
        "scp",
        "-i", config.ssh_key_path,
        "-O",  # Force legacy SCP protocol
        file_path,
        f"{config.username}@{config.hostname}:{config.protocol_dest}"
    ]
    
    try:
        result = subprocess.run(
            scp_command,
            check=True,
            text=True,
            capture_output=True
        )
        log_msg("File transferred successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        log_msg(f"An error occurred: {e}")
        log_msg(f"Error output: {e.stderr}")
        return False


def run_ssh_command(
    protocol_name: str,
    config: Optional[OT2Config] = None
) -> bool:
    """
    Execute a protocol on the OT-2 via SSH.
    
    Establishes an SSH connection, runs opentrons_execute with the given
    protocol, and monitors output for completion.
    
    Args:
        protocol_name: Name of the protocol file to execute.
        config: OT-2 configuration. Uses defaults if not provided.
        
    Returns:
        True if protocol finished successfully, False otherwise.
    """
    config = config or get_default_ot2_config()
    complete = False
    ssh = None
    stdin = None
    
    try:
        protocol_path = f"'{config.protocol_dest}/{protocol_name}'"
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            config.hostname,
            username=config.username,
            key_filename=config.ssh_key_path
        )
        
        stdin, stdout, stderr = ssh.exec_command(
            f'sh -l -c "opentrons_execute {protocol_path}"'
        )
        
        full_output = []
        
        while True:
            line = stdout.readline()
            if not line:
                break
            
            print(line, end='')
            full_output.append(line)
            
            if "Protocol Finished" in line:
                log_msg("Protocol end detected")
                complete = True
                break
            
            time.sleep(0.1)
        
        # Check remaining output
        if ' Protocol Finished\n' in full_output:
            log_msg("Protocol end detected")
            complete = True
        elif not complete:
            log_msg("Protocol end not detected")
            
    except Exception as e:
        log_msg(f"An error occurred: {e}")
        
    finally:
        if stdin:
            stdin.close()
        if ssh:
            ssh.close()
    
    return complete


class OT2Connection:
    """
    Context manager for OT-2 SSH connection.
    
    .. deprecated::
        Use :class:`ot2_controller.instruments.OT2Instrument` instead.
        OT2Instrument provides the same functionality with better
        integration into the experiment framework.
        
        Example:
            # Old way (deprecated)
            with OT2Connection() as conn:
                conn.upload_file("protocol.py")
                conn.execute_protocol("protocol.py")
            
            # New way (recommended)
            from ot2_controller import OT2Instrument
            with OT2Instrument() as ot2:
                ot2.upload_protocol("protocol.py")
                ot2.run_protocol("protocol.py")
    
    Provides a cleaner interface for managing SSH connections and
    executing multiple commands.
    """
    
    def __init__(self, config: Optional[OT2Config] = None):
        """
        Initialize connection with configuration.
        
        Args:
            config: OT-2 configuration. Uses defaults if not provided.
        """
        self.config = config or get_default_ot2_config()
        self.ssh: Optional[paramiko.SSHClient] = None
    
    def __enter__(self) -> "OT2Connection":
        """Establish SSH connection."""
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(
            self.config.hostname,
            username=self.config.username,
            key_filename=self.config.ssh_key_path
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close SSH connection."""
        if self.ssh:
            self.ssh.close()
    
    def execute_command(self, command: str) -> tuple:
        """
        Execute a command on the OT-2.
        
        Args:
            command: Shell command to execute.
            
        Returns:
            Tuple of (stdout, stderr) as strings.
        """
        if not self.ssh:
            raise RuntimeError("Not connected to OT-2")
        
        stdin, stdout, stderr = self.ssh.exec_command(command)
        return stdout.read().decode(), stderr.read().decode()
    
    def execute_protocol(self, protocol_name: str) -> bool:
        """
        Execute a protocol and wait for completion.
        
        Args:
            protocol_name: Name of the protocol file.
            
        Returns:
            True if protocol completed successfully.
        """
        return run_ssh_command(protocol_name, self.config)
    
    def upload_file(self, local_path: str) -> bool:
        """
        Upload a file to the OT-2.
        
        Args:
            local_path: Local path of the file to upload.
            
        Returns:
            True if upload successful.
        """
        return run_subprocess(local_path, self.config)
    
    def test_connection(self) -> bool:
        """
        Test the SSH connection with a simple command.
        
        Returns:
            True if connection is working.
        """
        try:
            stdout, stderr = self.execute_command('echo "Connection OK"')
            return "Connection OK" in stdout
        except Exception:
            return False
