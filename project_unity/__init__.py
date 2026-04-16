"""
OT-2, Plate Reader, and Lumidox Controller Package.

A modular package for controlling OT-2 liquid handling robots, UV-Vis plate
readers, Lumidox II LED controllers, and other instruments for automated
experiments.

Modules:
    instruments: High-level instrument control (OT2Instrument,
                 PlateReaderInstrument, LumidoxInstrument)
    experiments: Experiment templates and base classes
    config: Configuration dataclasses and settings
    utils: Logging, file I/O, and data processing utilities
    communication: Low-level socket and SSH communication

Quick Start - OT-2 Only:
    from project_unity import OT2Instrument, OT2ProtocolExperiment
    
    with OT2Instrument() as ot2:
        exp = OT2ProtocolExperiment(
            user_name="Lachlan",
            protocol_path="my_protocol.py",
            ot2=ot2
        )
        exp.run()

Quick Start - Plate Reader Only:
    from project_unity import PlateReaderInstrument, PlateReaderMeasurementExperiment
    
    with PlateReaderInstrument() as reader:
        exp = PlateReaderMeasurementExperiment(
            user_name="Lachlan",
            wavelength=600,
            plate_reader=reader
        )
        exp.run()

Quick Start - Lumidox Only:
    from project_unity import LumidoxInstrument, LumidoxExposureExperiment
    
    with LumidoxInstrument() as lumidox:
        exp = LumidoxExposureExperiment(
            user_name="Lachlan",
            duration_seconds=120,
            stage=3,
            lumidox=lumidox,
        )
        exp.run()

Quick Start - Combined Instruments:
    from project_unity import OT2Instrument, PlateReaderInstrument, LumidoxInstrument
    
    with OT2Instrument() as ot2, LumidoxInstrument() as lumidox:
        # Prepare samples on OT-2 then illuminate with Lumidox
        ...
"""

__version__ = "3.0.0"
__author__ = "Lachlan"

# =============================================================================
# Instruments
# =============================================================================
from .instruments import (
    BaseInstrument,
    InstrumentStatus,
    OT2Instrument,
    PlateReaderInstrument,
    LumidoxInstrument,
)

# =============================================================================
# Experiments
# =============================================================================
from .experiments import (
    # Metadata and base
    ExperimentMetadata,
    ExperimentStatus,
    BaseExperiment,
    
    # OT-2 only experiments
    OT2ProtocolExperiment,
    OT2MultiProtocolExperiment,
    
    # Plate reader only experiments
    PlateReaderMeasurementExperiment,
    PlateReaderTimeCourseExperiment,
    PlateReaderTemperatureRampExperiment,
    
    # Lumidox only experiments
    LumidoxExposureExperiment,
    LumidoxMultiStageExperiment,
    LumidoxCustomSequenceExperiment,
    
    # Combined experiments
    OT2AndPlateReaderExperiment,
    IterativeOptimizationExperiment,
)

# =============================================================================
# Configuration
# =============================================================================
from .config import (
    OT2Config,
    PlateConfig,
    PlateReaderConfig,
    BayesianConfig,
    ServerConfig,
    LumidoxConfig,
    TemperatureConfig,
)

# =============================================================================
# Utilities
# =============================================================================
from .utils import (
    log_msg,
    timeit,
    get_output_path,
    get_file_path,
    load_data_new,
)

# =============================================================================
# Low-level Communication (for advanced use)
# =============================================================================
from .communication import (
    send_message,
    receive_message,
    run_subprocess,
    run_ssh_command,
    OT2Connection,
)

__all__ = [
    # Version
    "__version__",
    
    # Instruments
    "BaseInstrument",
    "InstrumentStatus",
    "OT2Instrument",
    "PlateReaderInstrument",
    "LumidoxInstrument",
    
    # Experiments - Metadata and Base
    "ExperimentMetadata",
    "ExperimentStatus",
    "BaseExperiment",
    
    # Experiments - OT-2 Only
    "OT2ProtocolExperiment",
    "OT2MultiProtocolExperiment",
    
    # Experiments - Plate Reader Only
    "PlateReaderMeasurementExperiment",
    "PlateReaderTimeCourseExperiment",
    "PlateReaderTemperatureRampExperiment",
    
    # Experiments - Lumidox Only
    "LumidoxExposureExperiment",
    "LumidoxMultiStageExperiment",
    "LumidoxCustomSequenceExperiment",
    
    # Experiments - Combined
    "OT2AndPlateReaderExperiment",
    "IterativeOptimizationExperiment",
    
    # Config
    "OT2Config",
    "PlateConfig",
    "PlateReaderConfig",
    "BayesianConfig",
    "ServerConfig",
    "LumidoxConfig",
    "TemperatureConfig",
    
    # Utils
    "log_msg",
    "timeit",
    "get_output_path",
    "get_file_path",
    "load_data_new",
    
    # Low-level Communication
    "send_message",
    "receive_message",
    "run_subprocess",
    "run_ssh_command",
    "OT2Connection",
]
