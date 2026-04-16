"""
Instrument abstraction layer for OT-2, plate reader, and Lumidox control.

Provides unified interfaces for controlling laboratory instruments,
making it easy to build experiments with any combination of hardware.

Available Instruments:
    OT2Instrument: Opentrons OT-2 liquid handling robot
    PlateReaderInstrument: BMG SPECTROstar Nano plate reader
    LumidoxInstrument: Analytical Sales & Services Lumidox II LED controller

Example:
    # OT-2 only
    with OT2Instrument() as ot2:
        ot2.upload_protocol("my_protocol.py")
        ot2.run_protocol("my_protocol.py")
    
    # Plate reader only
    with PlateReaderInstrument() as reader:
        reader.set_temperature(37.0)
        reader.run_measurement(600, "output/")
    
    # Lumidox only
    with LumidoxInstrument() as lumidox:
        lumidox.fire_stage(3)
        time.sleep(60)
        lumidox.turn_off()
    
    # Multiple instruments
    with OT2Instrument() as ot2, LumidoxInstrument() as lumidox:
        # Use both instruments together
        ...
"""

from .base import BaseInstrument, InstrumentStatus
from .ot2 import OT2Instrument
from .plate_reader import PlateReaderInstrument
from .lumidox import LumidoxInstrument

__all__ = [
    "BaseInstrument",
    "InstrumentStatus",
    "OT2Instrument",
    "PlateReaderInstrument",
    "LumidoxInstrument",
]
