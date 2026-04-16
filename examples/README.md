# Project Unity Examples

This directory contains example scripts demonstrating how to use the `project_unity` package for various experiment configurations.

## Quick Start

### OT-2 Only

```python
from project_unity import OT2Instrument, OT2ProtocolExperiment

with OT2Instrument() as ot2:
    exp = OT2ProtocolExperiment(
        user_name="Your Name",
        protocol_path="path/to/protocol.py",
        ot2=ot2
    )
    metadata = exp.run()
```

### Plate Reader Only

```python
from project_unity import PlateReaderInstrument, PlateReaderMeasurementExperiment

# Start Nano_Control_Client.py in 32-bit Python first!
with PlateReaderInstrument() as reader:
    exp = PlateReaderMeasurementExperiment(
        user_name="Your Name",
        wavelength=600,
        plate_reader=reader
    )
    metadata = exp.run()
```

### Lumidox Only

```python
from project_unity import LumidoxInstrument, LumidoxExposureExperiment

with LumidoxInstrument() as lumidox:
    exp = LumidoxExposureExperiment(
        user_name="Your Name",
        duration_seconds=120,
        stage=3,
        lumidox=lumidox,
    )
    metadata = exp.run()
```

### Combined Instruments

```python
from project_unity import (
    OT2Instrument,
    PlateReaderInstrument,
    OT2AndPlateReaderExperiment,
)

with OT2Instrument() as ot2, PlateReaderInstrument() as reader:
    exp = OT2AndPlateReaderExperiment(
        user_name="Your Name",
        protocol_path="path/to/protocol.py",
        wavelength=600,
        ot2=ot2,
        plate_reader=reader
    )
    metadata = exp.run()
```

## Example Files

| File | Description |
|------|-------------|
| `example_ot2_only.py` | OT-2 liquid handler examples |
| `example_plate_reader_only.py` | Plate reader measurement examples |
| `example_lumidox.py` | Lumidox II LED controller examples |
| `example_combined.py` | Combined OT-2 + plate reader workflows |
| `example_custom_experiment.py` | Creating your own experiment classes |

## Available Experiment Templates

### OT-2 Only
- `OT2ProtocolExperiment` - Run a single protocol
- `OT2MultiProtocolExperiment` - Run multiple protocols in sequence

### Plate Reader Only
- `PlateReaderMeasurementExperiment` - Single measurement
- `PlateReaderTimeCourseExperiment` - Measurements over time
- `PlateReaderTemperatureRampExperiment` - Measurements at different temperatures

### Lumidox Only
- `LumidoxExposureExperiment` - Timed LED illumination at one power level
- `LumidoxMultiStageExperiment` - Cycle through preset stages
- `LumidoxCustomSequenceExperiment` - Arbitrary current/duration sequence

### Combined
- `OT2AndPlateReaderExperiment` - OT-2 preparation + plate reader measurement
- `IterativeOptimizationExperiment` - Multiple rounds of optimization

## Building Custom Experiments

Subclass `BaseExperiment` to create your own experiment types:

```python
from project_unity import BaseExperiment

class MyExperiment(BaseExperiment):
    EXPERIMENT_TYPE = "MyExperiment"
    REQUIRED_INSTRUMENTS = ["ot2", "plate_reader"]
    
    def setup(self) -> None:
        # Preparation (upload protocols, collect backgrounds, etc.)
        pass
    
    def execute(self) -> None:
        # Main experiment logic
        ot2 = self.instruments["ot2"]
        reader = self.instruments["plate_reader"]
        
        # Do experiment...
        self.metadata.add_result("success", True)
    
    def finalize(self) -> None:
        # Optional cleanup
        pass
```

## Metadata

All experiments automatically record standardized metadata:

```python
metadata = exp.run()

print(metadata.experiment_id)      # Unique ID
print(metadata.experiment_type)    # e.g., "OT2Protocol"
print(metadata.status)             # "completed", "failed", etc.
print(metadata.parameters)         # Experiment parameters
print(metadata.results_summary)    # Results
print(metadata.data_files)         # List of data file paths
print(metadata.event_log)          # Timestamped event log

# Save to JSON
metadata.save("experiment_results.json")

# Load from JSON
metadata = ExperimentMetadata.load("experiment_results.json")
```

## Plate Reader Note

The plate reader uses ActiveX COM which requires 32-bit Python. You have two options:

1. **Manual launch**: Start `Nano_Control_Client.py` in 32-bit Python before running your script
2. **Auto-launch**: Configure the 32-bit Python path and use `auto_launch=True`:

```python
with PlateReaderInstrument(
    auto_launch=True,
    python_32_path=r"C:\Python311-32\python.exe"
) as reader:
    # ...
```

## Troubleshooting

### OT-2 Connection Issues
- Verify the OT-2 IP address in `OT2Config`
- Ensure the SSH key is correct
- Check network connectivity

### Plate Reader Connection Issues
- Ensure `Nano_Control_Client.py` is running in 32-bit Python
- Check that the plate reader is powered on and connected
- Verify the COM port in the BMG software

### Experiment Failures
- Check the metadata event log for error details
- Review the experiment output directory for partial results
- Metadata is saved even if experiment fails
