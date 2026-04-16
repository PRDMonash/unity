"""
Configuration module for OT-2, plate reader, and Lumidox control.

Provides dataclasses for hardware configuration, plate settings,
and experiment parameters.
"""

from .settings import (
    OT2Config,
    PlateConfig,
    PlateReaderConfig,
    BayesianConfig,
    ServerConfig,
    LumidoxConfig,
    TemperatureConfig,
    get_default_ot2_config,
    get_default_plate_config,
    get_default_plate_reader_config,
    get_default_bayesian_config,
    get_default_server_config,
    get_default_lumidox_config,
    get_default_temperature_config,
)

__all__ = [
    "OT2Config",
    "PlateConfig",
    "PlateReaderConfig",
    "BayesianConfig",
    "ServerConfig",
    "LumidoxConfig",
    "TemperatureConfig",
    "get_default_ot2_config",
    "get_default_plate_config",
    "get_default_plate_reader_config",
    "get_default_bayesian_config",
    "get_default_server_config",
    "get_default_lumidox_config",
    "get_default_temperature_config",
]
