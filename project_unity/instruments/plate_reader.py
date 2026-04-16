"""
BMG SPECTROstar Nano plate reader instrument.

Provides high-level control of the plate reader via socket communication
with a 32-bit client process.

Note:
    Due to the BMG ActiveX COM interface being 32-bit only, this instrument
    communicates with a separate 32-bit Python process (Nano_Control_Client.py)
    via socket. The PlateReaderInstrument can optionally auto-launch this
    client process.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, List
from datetime import datetime

from ..config import ServerConfig, PlateReaderConfig, get_default_server_config
from ..utils.logging import log_msg
from .base import BaseInstrument, InstrumentStatus


class PlateReaderInstrument(BaseInstrument):
    """
    BMG SPECTROstar Nano plate reader.
    
    Communicates with the plate reader via a socket connection to a
    32-bit client process. Can optionally auto-launch the client.
    
    Example:
        # Auto-launch client (if 32-bit Python path is configured)
        with PlateReaderInstrument(auto_launch=True) as reader:
            reader.set_temperature(37.0)
            temp1, temp2 = reader.get_temperature()
            path = reader.run_measurement(600, "output/")
        
        # Manual client launch
        # First, start Nano_Control_Client.py in 32-bit Python
        with PlateReaderInstrument(auto_launch=False) as reader:
            # Client should connect automatically
            reader.run_measurement(600, "output/")
        
        # Custom configuration
        config = ServerConfig(port=65433)
        with PlateReaderInstrument(config=config) as reader:
            ...
    
    Attributes:
        config: ServerConfig with socket settings
        auto_launch: Whether to auto-launch the 32-bit client
        python_32_path: Path to 32-bit Python executable
    """
    
    name = "SPECTROstar Nano"
    instrument_type = "PlateReader"
    
    # Default paths - can be overridden
    DEFAULT_CLIENT_SCRIPT = Path(__file__).parent.parent.parent / "Nano_Control_Client.py"
    DEFAULT_PYTHON_32 = PlateReaderConfig.python_32_path

    def __init__(
        self,
        config: Optional[ServerConfig] = None,
        auto_launch: bool = False,
        python_32_path: Optional[str] = None,
        client_script_path: Optional[str] = None,
        connection_timeout: float = 60.0
    ):
        """
        Initialize plate reader instrument.
        
        Args:
            config: Server configuration for socket communication.
            auto_launch: If True, automatically launch the 32-bit client process.
            python_32_path: Path to 32-bit Python executable.
            client_script_path: Path to Nano_Control_Client.py.
            connection_timeout: Seconds to wait for client connection.
        """
        self.config = config or get_default_server_config()
        self.auto_launch = auto_launch
        self.python_32_path = python_32_path or self.DEFAULT_PYTHON_32
        self.client_script_path = Path(client_script_path) if client_script_path else self.DEFAULT_CLIENT_SCRIPT
        self.connection_timeout = connection_timeout
        
        self._server: Optional[socket.socket] = None
        self._conn: Optional[socket.socket] = None
        self._client_process: Optional[subprocess.Popen] = None
        self._connected = False
    
    def connect(self) -> bool:
        """
        Start the socket server and wait for the 32-bit client to connect.
        
        If auto_launch is True, will attempt to start the client process.
        Otherwise, prompts user to start it manually.
        
        Returns:
            True if connection was successful.
        """
        try:
            # Create and bind socket
            self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.bind((self.config.host, self.config.port))
            self._server.listen(1)
            
            log_msg(f"Plate reader server listening on {self.config.host}:{self.config.port}")
            
            # Auto-launch client if requested
            if self.auto_launch:
                if not self._launch_client():
                    log_msg("Warning: Failed to auto-launch client. Please start manually.")
                    self._prompt_manual_launch()
            else:
                self._prompt_manual_launch()
            
            # Wait for connection with timeout
            self._server.settimeout(self.connection_timeout)
            
            try:
                log_msg("Waiting for client connection...")
                self._conn, addr = self._server.accept()
                self._conn.settimeout(300.0)  # 5 minute timeout for operations
                
                log_msg(f"Client connected from {addr}")
                self._connected = True
                return True
                
            except socket.timeout:
                log_msg(f"Connection timeout after {self.connection_timeout}s")
                raise TimeoutError(
                    f"No client connection within {self.connection_timeout}s. "
                    "Ensure Nano_Control_Client.py is running in 32-bit Python."
                )
            
        except Exception as e:
            log_msg(f"Failed to establish connection: {e}")
            self.disconnect()
            raise
    
    def _launch_client(self) -> bool:
        """
        Launch the 32-bit client process.
        
        Returns:
            True if launch was successful.
        """
        # Verify paths exist
        if not os.path.exists(self.python_32_path):
            log_msg(f"32-bit Python not found at: {self.python_32_path}")
            return False
        
        if not self.client_script_path.exists():
            log_msg(f"Client script not found at: {self.client_script_path}")
            return False
        
        try:
            log_msg(f"Launching 32-bit client: {self.client_script_path}")
            
            # Launch in a new console window (Windows)
            if sys.platform == 'win32':
                self._client_process = subprocess.Popen(
                    [self.python_32_path, str(self.client_script_path)],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # For other platforms, just run in background
                self._client_process = subprocess.Popen(
                    [self.python_32_path, str(self.client_script_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            log_msg(f"Client process started (PID: {self._client_process.pid})")
            
            # Give it a moment to start
            time.sleep(2)
            
            return True
            
        except Exception as e:
            log_msg(f"Failed to launch client: {e}")
            return False
    
    def _prompt_manual_launch(self) -> None:
        """Display instructions for manually launching the client."""
        log_msg("=" * 60)
        log_msg("MANUAL CLIENT LAUNCH REQUIRED")
        log_msg("=" * 60)
        log_msg(f"Please run in 32-bit Python ({self.python_32_path}):")
        log_msg(f"  python {self.client_script_path}")
        log_msg("=" * 60)
    
    def disconnect(self) -> None:
        """
        Disconnect from the plate reader and clean up.
        
        Sends shutdown signal to client and closes all sockets.
        """
        # Send shutdown to client
        if self._conn and self._connected:
            try:
                self._send_message("SHUTDOWN")
            except Exception:
                pass
        
        # Close connection
        if self._conn:
            try:
                self._conn.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        
        # Close server socket
        if self._server:
            try:
                self._server.close()
            except Exception:
                pass
            self._server = None
        
        # Wait for client process to exit
        if self._client_process:
            try:
                self._client_process.wait(timeout=10)
            except Exception:
                pass
            self._client_process = None
        
        self._connected = False
        log_msg("Disconnected from plate reader.")
    
    def status(self) -> InstrumentStatus:
        """
        Get current plate reader status.
        
        Returns:
            InstrumentStatus with connection and ready state.
        """
        details = {}
        ready = False
        
        if self._connected and self._conn:
            try:
                temp1, temp2 = self.get_temperature()
                details["temp1"] = temp1
                details["temp2"] = temp2
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
        Test that the connection is working.
        
        Returns:
            True if we can read temperature.
        """
        try:
            self.get_temperature()
            return True
        except Exception:
            return False
    
    def _send_message(self, message_type: str, message_data: str = "") -> None:
        """
        Send a message to the client.
        
        Args:
            message_type: Type of message (e.g., 'GET_TEMP', 'RUN_PROTOCOL')
            message_data: Optional data payload
        """
        if not self._conn:
            raise RuntimeError("Not connected to plate reader")
        
        message = f"{message_type}|{message_data}"
        self._conn.sendall(message.encode())
    
    def _receive_message(self) -> Tuple[str, str]:
        """
        Receive a message from the client.
        
        Returns:
            Tuple of (message_type, message_data)
        """
        if not self._conn:
            raise RuntimeError("Not connected to plate reader")
        
        data = self._conn.recv(self.config.buffer_size).decode()
        parts = data.split("|", 1)
        
        if len(parts) == 2:
            return parts[0], parts[1]
        else:
            return parts[0], ""
    
    def get_temperature(self) -> Tuple[float, float]:
        """
        Get current temperature readings.
        
        Returns:
            Tuple of (temp1, temp2) in Celsius.
            temp1 is lower plate, temp2 is upper plate.
        """
        self._send_message("GET_TEMP")
        msg_type, msg_data = self._receive_message()
        
        if msg_type == "TEMPS":
            temp1 = int(msg_data.split(",")[0].strip()) / 10
            temp2 = int(msg_data.split(",")[1].strip()) / 10
            return temp1, temp2
        
        raise RuntimeError(f"Unexpected response: {msg_type}")
    
    def set_temperature(self, temp: float) -> None:
        """
        Set the target incubator temperature.
        
        Note: This starts heating but does not wait for the temperature
        to stabilize. Use wait_for_stable_temperature() to wait.
        
        Args:
            temp: Target temperature in Celsius
        """
        log_msg(f"Setting plate reader temperature to {temp}°C")
        self._send_message("SET_TEMP", str(temp))
        
        # Wait for acknowledgment
        msg_type, _ = self._receive_message()
        if msg_type != "OK":
            log_msg(f"Warning: Unexpected response to SET_TEMP: {msg_type}")
    
    def wait_for_stable_temperature(
        self,
        target_temp: float,
        tolerance: float = 0.2,
        stable_time: float = 60.0,
        check_interval: float = 5.0,
        max_wait: float = 1800.0
    ) -> bool:
        """
        Wait for temperature to stabilize at target.
        
        Args:
            target_temp: Target temperature in Celsius
            tolerance: Acceptable deviation from target
            stable_time: How long temperature must remain stable (seconds)
            check_interval: How often to check temperature (seconds)
            max_wait: Maximum time to wait (seconds)
            
        Returns:
            True if temperature stabilized, False if timeout
        """
        log_msg(f"Waiting for temperature to stabilize at {target_temp}°C...")
        
        start_time = time.time()
        stable_duration = 0.0
        
        while stable_duration < stable_time:
            if time.time() - start_time > max_wait:
                log_msg("Temperature stabilization timeout")
                return False
            
            temp1, temp2 = self.get_temperature()
            
            # Check if within tolerance
            if abs(temp1 - target_temp) <= tolerance:
                stable_duration += check_interval
                log_msg(f"Temperature {temp1}°C (stable for {stable_duration:.0f}s)")
            else:
                stable_duration = 0.0
                log_msg(f"Temperature {temp1}°C (target: {target_temp}°C)")
            
            time.sleep(check_interval)
        
        log_msg(f"Temperature stabilized at {target_temp}°C")
        return True
    
    def set_and_stabilize(
        self,
        temp: float,
        tolerance: float = 0.2,
        stable_time: float = 60.0
    ) -> bool:
        """
        Set temperature and wait for it to stabilize.
        
        Convenience method combining set_temperature and wait_for_stable_temperature.
        
        Args:
            temp: Target temperature in Celsius
            tolerance: Acceptable deviation
            stable_time: How long temperature must remain stable
            
        Returns:
            True if stabilized successfully
        """
        self.set_temperature(temp)
        return self.wait_for_stable_temperature(temp, tolerance, stable_time)
    
    def plate_out(self) -> None:
        """
        Eject the plate holder from the reader.

        Raises:
            RuntimeError: If the command is not acknowledged.
        """
        log_msg("Ejecting plate from reader...")
        self._send_message("PLATE_OUT")
        msg_type, _ = self._receive_message()
        if msg_type != "OK":
            raise RuntimeError(f"Unexpected response to PLATE_OUT: {msg_type}")
        log_msg("Plate ejected.")

    def plate_in(self) -> None:
        """
        Insert the plate holder into the reader.

        Raises:
            RuntimeError: If the command is not acknowledged.
        """
        log_msg("Inserting plate into reader...")
        self._send_message("PLATE_IN")
        msg_type, _ = self._receive_message()
        if msg_type != "OK":
            raise RuntimeError(f"Unexpected response to PLATE_IN: {msg_type}")
        log_msg("Plate inserted.")

    def run_measurement(
        self,
        wavelength: int,
        output_dir: str,
        filename_prefix: str = "measurement",
        timeout: float = 400.0
    ) -> Optional[str]:
        """
        Run an absorbance measurement.
        
        Args:
            wavelength: Measurement wavelength in nm (e.g., 600)
            output_dir: Directory to save the measurement file
            filename_prefix: Prefix for the output filename
            timeout: Maximum time to wait for measurement
            
        Returns:
            Path to saved measurement file, or None if failed
        """
        log_msg(f"Running absorbance measurement at {wavelength}nm...")
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        self._send_message("RUN_PROTOCOL", f"{wavelength}nm")
        
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout:
                msg_type, msg_data = self._receive_message()
                
                if msg_type == "CSV_FILE":
                    log_msg("Measurement data received.")
                    
                    # Move file to output directory
                    original_name = os.path.basename(msg_data)
                    new_filename = f"{filename_prefix}_{original_name}"
                    new_path = os.path.join(output_dir, new_filename)
                    
                    shutil.move(msg_data, new_path)
                    log_msg(f"Measurement saved to {new_path}")
                    return new_path
                else:
                    log_msg(f"Waiting for measurement data... (received: {msg_type})")
                    time.sleep(2)
            
            log_msg("Measurement timeout")
            return None
            
        except Exception as e:
            log_msg(f"Measurement error: {e}")
            return None
    
    def collect_background(
        self,
        wavelength: int,
        output_dir: str,
        timeout: float = 300.0
    ) -> Optional[str]:
        """
        Collect plate background measurement from empty plate.
        
        Args:
            wavelength: Measurement wavelength in nm
            output_dir: Directory to save background file
            timeout: Maximum time to wait
            
        Returns:
            Path to saved background file, or None if failed
        """
        log_msg("Collecting plate background...")
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        self._send_message("PLATE_BACKGROUND", f"{wavelength}nm")
        
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout:
                msg_type, msg_data = self._receive_message()
                
                if msg_type == "PLATE_BACKGROUND":
                    log_msg("Plate background data received.")
                    
                    new_path = os.path.join(output_dir, os.path.basename(msg_data))
                    shutil.move(msg_data, new_path)
                    
                    log_msg(f"Background saved to {new_path}")
                    return new_path
                else:
                    log_msg(f"Waiting for background data... (received: {msg_type})")
                    time.sleep(2)
            
            log_msg("Background collection timeout")
            return None
            
        except Exception as e:
            log_msg(f"Background collection error: {e}")
            return None
    
    def run_measurement_with_background(
        self,
        wavelength: int,
        output_dir: str,
        collect_background: bool = True,
        filename_prefix: str = "measurement"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Run a measurement with optional background collection.
        
        Convenience method that collects background first (if requested),
        then runs the measurement.
        
        Args:
            wavelength: Measurement wavelength in nm
            output_dir: Directory to save files
            collect_background: Whether to collect background first
            filename_prefix: Prefix for measurement filename
            
        Returns:
            Tuple of (measurement_path, background_path)
            Either may be None if not collected or failed
        """
        background_path = None
        
        if collect_background:
            background_path = self.collect_background(wavelength, output_dir)
            if not background_path:
                log_msg("Warning: Background collection failed")
        
        measurement_path = self.run_measurement(
            wavelength, output_dir, filename_prefix
        )
        
        return measurement_path, background_path
