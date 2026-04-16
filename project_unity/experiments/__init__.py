"""
Experiment modules for OT-2, plate reader, and Lumidox control.

Provides:
- Base classes for building custom experiments
- Standardized metadata for all experiments
- Ready-to-use experiment templates for common workflows

Experiment Templates:
    OT-2 Only:
        - OT2ProtocolExperiment: Run a single OT-2 protocol
        - OT2MultiProtocolExperiment: Run multiple protocols in sequence
    
    Plate Reader Only:
        - PlateReaderMeasurementExperiment: Single measurement
        - PlateReaderTimeCourseExperiment: Measurements over time
        - PlateReaderTemperatureRampExperiment: Measurements at different temps
    
    Lumidox Only:
        - LumidoxExposureExperiment: Timed LED illumination at one power level
        - LumidoxMultiStageExperiment: Cycle through preset stages
        - LumidoxCustomSequenceExperiment: Arbitrary current/duration sequence
    
    Combined:
        - OT2AndPlateReaderExperiment: OT-2 prep + plate reader measurement
        - IterativeOptimizationExperiment: Multiple rounds of prep + measurement

Building Custom Experiments:
    Subclass BaseExperiment and implement setup() and execute():
    
    class MyExperiment(BaseExperiment):
        EXPERIMENT_TYPE = "MyExperiment"
        REQUIRED_INSTRUMENTS = ["ot2"]
        
        def setup(self):
            # Preparation code
            pass
        
        def execute(self):
            # Main experiment logic
            pass
"""

# Metadata and base classes
from .metadata import ExperimentMetadata, ExperimentStatus, InstrumentRecord
from .base import BaseExperiment

# OT-2 only experiments
from .ot2_protocol import OT2ProtocolExperiment, OT2MultiProtocolExperiment

# Plate reader only experiments
from .plate_reader_measurement import (
    PlateReaderMeasurementExperiment,
    PlateReaderTimeCourseExperiment,
    PlateReaderTemperatureRampExperiment,
)

# Lumidox only experiments
from .lumidox_illumination import (
    LumidoxExposureExperiment,
    LumidoxMultiStageExperiment,
    LumidoxCustomSequenceExperiment,
)

# Combined experiments
from .combined import OT2AndPlateReaderExperiment, IterativeOptimizationExperiment

__all__ = [
    # Metadata
    "ExperimentMetadata",
    "ExperimentStatus",
    "InstrumentRecord",
    
    # Base class
    "BaseExperiment",
    
    # OT-2 only experiments
    "OT2ProtocolExperiment",
    "OT2MultiProtocolExperiment",
    
    # Plate reader only experiments
    "PlateReaderMeasurementExperiment",
    "PlateReaderTimeCourseExperiment",
    "PlateReaderTemperatureRampExperiment",
    
    # Lumidox only experiments
    "LumidoxExposureExperiment",
    "LumidoxMultiStageExperiment",
    "LumidoxCustomSequenceExperiment",
    
    # Combined experiments
    "OT2AndPlateReaderExperiment",
    "IterativeOptimizationExperiment",
]
