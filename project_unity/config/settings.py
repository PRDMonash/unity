"""
Configuration settings for OT-2 and plate reader control.

Contains dataclasses for hardware configuration, plate settings,
and experiment parameters. These replace hardcoded values scattered
throughout the codebase.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class OT2Config:
    """Configuration for OT-2 robot connection.

    OT2Instrument uses the Robot HTTP API on ``hostname`` / ``http_port`` for
    health checks, protocol upload (``.py`` main file), runs, and execution.

    ``username``, ``ssh_key_path``, ``protocol_dest``, and ``scp_force_legacy``
    are used for SCP transfers of auxiliary files (see ``upload_file`` and
    ``run_protocol_with_upload(..., additional_files=...)``). The SSH host is
    ``hostname`` (same as the HTTP robot address). ``ssh_passphrase`` is not
    passed to ``scp``; use an unencrypted key or ssh-agent if needed.
    """

    hostname: str = "169.254.21.69"
    username: str = "root"
    ssh_key_path: str = r"C:\Users\PRD-OT2\ot2_ssh_key"
    protocol_dest: str = "/data/user_storage/prd_protocols"
    ssh_passphrase: str = ""  # Not used by SCP subprocess; use ssh-agent if needed
    scp_force_legacy: bool = True  # Pass ``-O`` to scp (helps on some Windows OpenSSH builds)

    http_port: int = 31950
    use_https: bool = False
    opentrons_api_version: str = "*"
    verify_tls: bool = True
    request_timeout_s: float = 30.0
    robot_token: Optional[str] = None


@dataclass
class PlateConfig:
    """Configuration for 96-well plate layout."""
    
    rows: str = "ABCDEFGH"
    cols: int = 12
    blank_wells: Tuple[str, ...] = ("A1", "A2", "A3", "A4")
    default_volume_ul: float = 300.0
    
    def get_all_wells(self) -> List[str]:
        """Generate list of all wells in order (A1, A2, ..., H12)."""
        return [f"{row}{col}" for row in self.rows for col in range(1, self.cols + 1)]
    
    def get_total_wells(self) -> int:
        """Return total number of wells on plate."""
        return len(self.rows) * self.cols


@dataclass
class BayesianConfig:
    """Configuration for Bayesian optimization experiments."""
    
    # Concentration bounds
    min_concentration: float = 0.01
    max_concentration: float = 0.99
    
    # Pipette transfer limits
    min_transfer_ul: float = 20.0
    max_transfer_ul: float = 1000.0
    
    # Default optimization parameters
    default_target_absorbance: float = 1.0
    default_tolerance: float = 0.05
    default_wavelength: int = 600
    default_batch_size: int = 4
    default_max_iterations: int = 10
    default_total_volume_ul: float = 300.0


@dataclass
class ServerConfig:
    """Configuration for socket server."""
    
    host: str = "localhost"
    port: int = 65432
    buffer_size: int = 1024


@dataclass
class PlateReaderConfig:
    """Configuration for plate reader instrument."""
    
    # Server settings
    server: ServerConfig = None
    
    # 32-bit client settings
    python_32_path: str = r"C:\Users\Public\Python-32\python.exe"
    client_script_path: str = ""  # Auto-detected if empty
    auto_launch: bool = False
    connection_timeout: float = 60.0
    
    # Measurement defaults
    default_wavelength: int = 600
    measurement_timeout: float = 400.0
    background_timeout: float = 300.0
    
    def __post_init__(self):
        if self.server is None:
            self.server = ServerConfig()


@dataclass
class LumidoxConfig:
    """Configuration for Lumidox II LED controller connection."""
    
    port: str = ""  # COM port (e.g. "COM3"); empty = use auto_detect
    baud_rate: int = 19200
    timeout: float = 1.0
    auto_detect: bool = True  # Scan for USB Serial / FTDI ports


@dataclass
class TemperatureConfig:
    """Configuration for temperature control experiments."""
    
    start_temp: float = 25.0
    target_temp: float = 45.0
    step_size: float = 0.5
    pause_time_seconds: int = 300  # 5 minutes
    stabilization_time: float = 45.0
    check_interval: float = 5.0
    range_tolerance: float = 0.2


# Factory functions for getting default configurations
def get_default_ot2_config() -> OT2Config:
    """Return default OT-2 configuration."""
    return OT2Config()


def get_default_plate_config() -> PlateConfig:
    """Return default plate configuration."""
    return PlateConfig()


def get_default_bayesian_config() -> BayesianConfig:
    """Return default Bayesian optimization configuration."""
    return BayesianConfig()


def get_default_server_config() -> ServerConfig:
    """Return default server configuration."""
    return ServerConfig()


def get_default_temperature_config() -> TemperatureConfig:
    """Return default temperature configuration."""
    return TemperatureConfig()


def get_default_lumidox_config() -> LumidoxConfig:
    """Return default Lumidox II configuration."""
    return LumidoxConfig()


def get_default_plate_reader_config() -> PlateReaderConfig:
    """Return default plate reader configuration."""
    return PlateReaderConfig()
