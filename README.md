# Project Unity

A modular Python package for orchestrating laboratory instruments — the **Opentrons OT-2** liquid handling robot, **BMG SPECTROstar Nano** plate reader, and **Lumidox II** LED controller — in automated, reproducible experiments.

```
pip install paramiko pyserial pandas numpy
```

---

## Table of Contents

- [Design Principles](#design-principles)
- [Package Structure](#package-structure)
- [Prerequisites](#prerequisites)
- [Core Concepts](#core-concepts)
  - [Instruments](#instruments)
  - [Experiments](#experiments)
  - [Metadata](#metadata)
  - [Configuration](#configuration)
- [Quick Start](#quick-start)
  - [OT-2 Only](#ot-2-only)
  - [Plate Reader Only](#plate-reader-only)
  - [Lumidox Only](#lumidox-only)
  - [Combined Instruments](#combined-instruments)
- [Instrument Reference](#instrument-reference)
  - [OT2Instrument](#ot2instrument)
  - [PlateReaderInstrument](#platereaderinstrument)
  - [LumidoxInstrument](#lumidoxinstrument)
- [Experiment Templates](#experiment-templates)
- [Building Custom Experiments](#building-custom-experiments)
  - [Minimal Example](#minimal-example)
  - [Parameterized Experiment](#parameterized-experiment)
  - [Multi-Instrument Experiment](#multi-instrument-experiment)
  - [Finalization and Cleanup](#finalization-and-cleanup)
- [Configuration Reference](#configuration-reference)
- [Utilities](#utilities)
- [The 32-Bit Plate Reader Client](#the-32-bit-plate-reader-client)
- [Troubleshooting](#troubleshooting)

---

## Design Principles

Project Unity is built around four ideas:

1. **Instrument abstraction** — Every piece of hardware implements the same `BaseInstrument` interface (`connect`, `disconnect`, `status`, `test_connection`) and works as a Python context manager. You never manage raw sockets or serial ports directly; the instrument class handles the lifecycle.

2. **Experiment as a first-class object** — All experimental workflows inherit from `BaseExperiment`, which enforces a three-phase lifecycle (`setup → execute → finalize`) and automatically records structured metadata. This keeps ad-hoc scripts from turning into unmaintainable one-offs.

3. **Composability** — Instruments are injected into experiments as keyword arguments. Any combination of hardware can be used together simply by passing the relevant instruments. There is no tight coupling between experiment logic and a specific instrument set.

4. **Reproducibility by default** — Every experiment run produces a JSON metadata file containing a unique ID, timestamped event log, all parameters, data file paths, instrument configurations, and a results summary. This happens automatically; you do not need to add logging code yourself.

---

## Package Structure

```
ot2_platereader_control/
├── project_unity/                  # The package
│   ├── __init__.py                 # Public API — everything importable from here
│   ├── instruments/
│   │   ├── base.py                 # BaseInstrument, InstrumentStatus
│   │   ├── ot2.py                  # OT2Instrument
│   │   ├── plate_reader.py         # PlateReaderInstrument
│   │   └── lumidox.py              # LumidoxInstrument
│   ├── experiments/
│   │   ├── base.py                 # BaseExperiment (abstract)
│   │   ├── metadata.py             # ExperimentMetadata, ExperimentStatus
│   │   ├── ot2_protocol.py         # OT2ProtocolExperiment, OT2MultiProtocolExperiment
│   │   ├── plate_reader_measurement.py
│   │   │                           # PlateReaderMeasurementExperiment
│   │   │                           # PlateReaderTimeCourseExperiment
│   │   │                           # PlateReaderTemperatureRampExperiment
│   │   ├── lumidox_illumination.py # LumidoxExposureExperiment
│   │   │                           # LumidoxMultiStageExperiment
│   │   │                           # LumidoxCustomSequenceExperiment
│   │   └── combined.py             # OT2AndPlateReaderExperiment
│   │                               # IterativeOptimizationExperiment
│   ├── config/
│   │   └── settings.py             # All configuration dataclasses
│   ├── communication/
│   │   ├── socket_client.py        # Plate reader socket protocol
│   │   └── ot2_ssh.py              # OT-2 SSH/SCP helpers
│   └── utils/
│       ├── logging.py              # log_msg(), timeit()
│       ├── file_io.py              # File dialogs, CSV loading, directory helpers
│       ├── data_processing.py      # Background subtraction, blank correction
│       └── user_input.py           # Typed input prompts with validation
├── Nano_Control_Client.py          # 32-bit ActiveX COM bridge (runs in 32-bit Python)
├── examples/                       # Runnable example scripts
├── requirements_64.txt             # Dependencies for the main package (64-bit)
└── requirements_32.txt             # Dependencies for the 32-bit client (pywin32)
```

---

## Prerequisites

| Requirement | Purpose |
|---|---|
| **Python 3.10+** (64-bit) | Runs the main package, OT-2 SSH, Lumidox serial, and experiment framework |
| **Python 3.11 (32-bit)** | Required *only* for `Nano_Control_Client.py` — the BMG ActiveX COM interface is 32-bit only |
| `paramiko` | SSH/SCP communication with the OT-2 |
| `pyserial` | Serial communication with the Lumidox II |
| `pandas`, `numpy` | Data loading and processing |
| `pywin32` *(32-bit env)* | ActiveX COM automation for the plate reader client |

Install 64-bit dependencies:

```bash
pip install -r requirements_64.txt
```

Install 32-bit dependencies (in the 32-bit Python environment):

```bash
<path-to-32bit-python>\python.exe -m pip install -r requirements_32.txt
```

---

## Core Concepts

### Instruments

An **instrument** is a Python object that wraps a physical device. All instruments share the same interface:

```python
class BaseInstrument(ABC):
    name: str                        # Human-readable name
    instrument_type: str             # Category ("OT2", "PlateReader", "Lumidox")

    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def status(self) -> InstrumentStatus: ...
    def test_connection(self) -> bool: ...
```

Every instrument is a context manager. The recommended pattern is:

```python
with OT2Instrument() as ot2:
    # ot2.connect() was called automatically
    ot2.upload_protocol("my_protocol.py")
    ot2.run_protocol("my_protocol.py")
# ot2.disconnect() was called automatically
```

You can combine instruments in a single `with` statement:

```python
with OT2Instrument() as ot2, PlateReaderInstrument() as reader, LumidoxInstrument() as lumidox:
    ...
```

### Experiments

An **experiment** is a subclass of `BaseExperiment` that defines a reproducible workflow. Every experiment follows the same lifecycle:

```
__init__  →  run()
               ├── connect instruments
               ├── setup()       ← you implement this
               ├── execute()     ← you implement this
               ├── finalize()    ← optional override
               ├── disconnect instruments
               └── save metadata (always, even on failure)
```

Instruments are passed as keyword arguments and accessed via `self.instruments["key"]`:

```python
class MyExperiment(BaseExperiment):
    EXPERIMENT_TYPE = "MyExperiment"
    REQUIRED_INSTRUMENTS = ["ot2"]

    def setup(self):
        self.instruments["ot2"].upload_protocol("protocol.py")

    def execute(self):
        self.instruments["ot2"].run_protocol("protocol.py")
```

Calling `exp.run()` returns an `ExperimentMetadata` object containing everything that happened.

### Metadata

`ExperimentMetadata` is a structured record created automatically by every experiment. It captures:

| Field | Description |
|---|---|
| `experiment_id` | Unique 8-character identifier |
| `experiment_type` | Class name / category |
| `experiment_name` | Human-readable label |
| `user_name` | Who ran it |
| `start_time` / `end_time` | ISO timestamps |
| `status` | `"pending"`, `"running"`, `"completed"`, `"failed"`, `"cancelled"` |
| `instruments` | Map of instruments used, their configs and operations |
| `parameters` | Experiment-specific parameters |
| `results_summary` | Key results |
| `data_files` | Paths to all output files |
| `event_log` | Timestamped list of events |
| `package_version` | Version of `project_unity` for reproducibility |

Metadata is saved as JSON to the experiment output directory at the end of every run:

```python
metadata = exp.run()

# Access results
print(metadata.status)              # "completed"
print(metadata.results_summary)     # {"success": True, ...}
print(metadata.data_files)          # ["path/to/measurement.csv", ...]

# Persist and reload
metadata.save("results.json")
loaded = ExperimentMetadata.load("results.json")
```

### Configuration

All hardware settings live in typed dataclasses in `project_unity.config`. Default values match the standard lab setup, but everything is overridable:

```python
from project_unity import OT2Config, OT2Instrument

config = OT2Config(
    hostname="192.168.1.100",
    ssh_key_path=r"C:\keys\my_ot2_key",
)
with OT2Instrument(config=config) as ot2:
    ...
```

---

## Quick Start

### OT-2 Only

Upload and run a protocol on the OT-2 robot:

```python
from project_unity import OT2Instrument, OT2ProtocolExperiment

with OT2Instrument() as ot2:
    exp = OT2ProtocolExperiment(
        user_name="Lachlan",
        protocol_path="my_protocol.py",
        ot2=ot2,
    )
    metadata = exp.run()
    print(metadata.results_summary)
```

### Plate Reader Only

Take a single absorbance measurement (start `Nano_Control_Client.py` in 32-bit Python first):

```python
from project_unity import PlateReaderInstrument, PlateReaderMeasurementExperiment

with PlateReaderInstrument() as reader:
    exp = PlateReaderMeasurementExperiment(
        user_name="Lachlan",
        wavelength=600,
        plate_reader=reader,
    )
    metadata = exp.run()
    print(metadata.data_files)
```

### Lumidox Only

Illuminate a plate at preset stage 3 for 2 minutes:

```python
from project_unity import LumidoxInstrument, LumidoxExposureExperiment

with LumidoxInstrument() as lumidox:
    exp = LumidoxExposureExperiment(
        user_name="Lachlan",
        duration_seconds=120,
        stage=3,
        lumidox=lumidox,
    )
    metadata = exp.run()
```

### Combined Instruments

Run an OT-2 protocol to prepare samples, then measure with the plate reader:

```python
from project_unity import (
    OT2Instrument,
    PlateReaderInstrument,
    OT2AndPlateReaderExperiment,
)

with OT2Instrument() as ot2, PlateReaderInstrument() as reader:
    exp = OT2AndPlateReaderExperiment(
        user_name="Lachlan",
        protocol_path="prepare_samples.py",
        wavelength=600,
        ot2=ot2,
        plate_reader=reader,
    )
    metadata = exp.run()
```

---

## Instrument Reference

### OT2Instrument

Controls the Opentrons OT-2 via SSH. Key methods:

| Method | Description |
|---|---|
| `connect()` / `disconnect()` | Manage SSH session |
| `upload_protocol(local_path)` | SCP a `.py` file to the robot |
| `upload_file(local_path)` | Alias — upload any file (e.g. CSV) |
| `run_protocol(name, timeout)` | Execute a protocol already on the robot |
| `run_protocol_with_upload(path, additional_files, timeout)` | Upload + run in one step |
| `list_protocols()` | List `.py` files in the robot's protocol directory |
| `get_robot_info()` | System info, Python version, Opentrons version |
| `test_connection()` | Quick echo test over SSH |

### PlateReaderInstrument

Controls the BMG SPECTROstar Nano via a socket bridge to a 32-bit client. Key methods:

| Method | Description |
|---|---|
| `connect()` / `disconnect()` | Start socket server, wait for 32-bit client |
| `get_temperature()` → `(float, float)` | Read lower and upper plate temperatures |
| `set_temperature(temp)` | Set target incubator temperature |
| `wait_for_stable_temperature(target, tolerance, stable_time)` | Block until temperature is stable |
| `set_and_stabilize(temp)` | Set + wait in one call |
| `run_measurement(wavelength, output_dir)` → `str` | Run absorbance scan, return path to CSV |
| `collect_background(wavelength, output_dir)` → `str` | Measure empty plate for background correction |
| `run_measurement_with_background(wavelength, output_dir)` | Collect background + measurement together |

### LumidoxInstrument

Controls the Lumidox II LED array over USB serial. Key methods:

| Method | Description |
|---|---|
| `connect()` / `disconnect()` | Open serial port, enter remote mode |
| `fire_stage(stage)` | Turn on LEDs at a preset power stage (1–5) |
| `fire_custom(current_ma)` | Turn on LEDs at a specific drive current |
| `turn_off()` | Return to standby |
| `timed_exposure(duration, stage=, current_ma=)` | Fire → sleep → off in one call |
| `get_device_info()` | Firmware, model, serial, wavelength, max current |
| `get_stage_info(stage)` / `get_all_stages()` | Read calibrated power for preset stages |

The `LumidoxConfig` supports `auto_detect=True` (default) to scan for USB Serial / FTDI ports automatically, or you can specify a port explicitly:

```python
from project_unity import LumidoxConfig, LumidoxInstrument

config = LumidoxConfig(port="COM5", auto_detect=False)
with LumidoxInstrument(config=config) as lumidox:
    lumidox.fire_stage(3)
```

---

## Experiment Templates

Project Unity ships with ready-to-use experiment classes:

### OT-2

| Class | Description |
|---|---|
| `OT2ProtocolExperiment` | Upload and run a single protocol, with optional additional files |
| `OT2MultiProtocolExperiment` | Run a list of protocols in sequence, with optional pauses between them |

### Plate Reader

| Class | Description |
|---|---|
| `PlateReaderMeasurementExperiment` | Single absorbance measurement with optional background collection |
| `PlateReaderTimeCourseExperiment` | Repeated measurements at fixed intervals |
| `PlateReaderTemperatureRampExperiment` | Measurements at a series of temperatures, with optional bidirectional ramp |

### Lumidox

| Class | Description |
|---|---|
| `LumidoxExposureExperiment` | Timed illumination at one power level (preset stage or custom current) |
| `LumidoxMultiStageExperiment` | Cycle through multiple preset stages with configurable durations |
| `LumidoxCustomSequenceExperiment` | Arbitrary list of `{current_ma, duration_seconds}` steps |

### Combined

| Class | Description |
|---|---|
| `OT2AndPlateReaderExperiment` | OT-2 sample preparation → plate reader measurement |
| `IterativeOptimizationExperiment` | Multiple rounds of OT-2 prep + measurement, with user-driven stopping |

---

## Building Custom Experiments

### Minimal Example

The smallest possible custom experiment:

```python
from project_unity import BaseExperiment, OT2Instrument

class MyExperiment(BaseExperiment):
    EXPERIMENT_TYPE = "MyExperiment"
    REQUIRED_INSTRUMENTS = ["ot2"]

    def setup(self):
        pass  # nothing to prepare

    def execute(self):
        ot2 = self.instruments["ot2"]
        info = ot2.get_robot_info()
        self.metadata.add_result("robot_info", info)

with OT2Instrument() as ot2:
    exp = MyExperiment(user_name="Lachlan", ot2=ot2)
    metadata = exp.run()
```

### Parameterized Experiment

Accept configuration through `__init__` and record it in metadata:

```python
from typing import List
from project_unity import BaseExperiment

class MultiWavelengthScan(BaseExperiment):
    EXPERIMENT_TYPE = "MultiWavelengthScan"
    REQUIRED_INSTRUMENTS = ["plate_reader"]

    def __init__(self, user_name: str, wavelengths: List[int], **instruments):
        super().__init__(user_name=user_name, **instruments)
        self.wavelengths = wavelengths
        self.metadata.add_parameter("wavelengths", wavelengths)

    def setup(self):
        reader = self.instruments["plate_reader"]
        bg = reader.collect_background(self.wavelengths[0], self.metadata.output_directory)
        self.metadata.add_data_file(bg)

    def execute(self):
        reader = self.instruments["plate_reader"]
        for wl in self.wavelengths:
            path = reader.run_measurement(wl, self.metadata.output_directory)
            if path:
                self.metadata.add_data_file(path)
```

### Multi-Instrument Experiment

Declare multiple required instruments and use them together:

```python
from project_unity import BaseExperiment

class PrepareAndIlluminate(BaseExperiment):
    EXPERIMENT_TYPE = "PrepareAndIlluminate"
    REQUIRED_INSTRUMENTS = ["ot2", "lumidox"]

    def __init__(self, user_name, protocol_path, stage, duration, **instruments):
        super().__init__(user_name=user_name, **instruments)
        self.protocol_path = protocol_path
        self.stage = stage
        self.duration = duration

    def setup(self):
        self.instruments["ot2"].upload_protocol(self.protocol_path)

    def execute(self):
        ot2 = self.instruments["ot2"]
        lumidox = self.instruments["lumidox"]

        ot2.run_protocol("prepare_plate.py")
        input("Move plate to Lumidox and press Enter...")
        lumidox.timed_exposure(self.duration, stage=self.stage)
```

Use it:

```python
from project_unity import OT2Instrument, LumidoxInstrument

with OT2Instrument() as ot2, LumidoxInstrument() as lumidox:
    exp = PrepareAndIlluminate(
        user_name="Lachlan",
        protocol_path="prepare_plate.py",
        stage=3,
        duration=120,
        ot2=ot2,
        lumidox=lumidox,
    )
    exp.run()
```

### Finalization and Cleanup

Override `finalize()` for post-experiment actions. It runs even if `execute()` raises an exception (within the experiment's error handling):

```python
class ExperimentWithCleanup(BaseExperiment):
    EXPERIMENT_TYPE = "WithCleanup"
    REQUIRED_INSTRUMENTS = ["plate_reader"]

    def setup(self):
        pass

    def execute(self):
        reader = self.instruments["plate_reader"]
        path = reader.run_measurement(600, self.metadata.output_directory)
        self.metadata.add_data_file(path)

    def finalize(self):
        reader = self.instruments["plate_reader"]
        reader.set_temperature(25.0)  # cool back to room temp
        self.metadata.add_result("cleanup_completed", True)
```

---

## Configuration Reference

All configuration dataclasses live in `project_unity.config` and can be imported directly from `project_unity`.

### OT2Config

| Field | Default | Description |
|---|---|---|
| `hostname` | `"169.254.80.171"` | OT-2 IP address |
| `username` | `"root"` | SSH username |
| `ssh_key_path` | `r"C:\Users\lachi\...\ot2_ssh_key"` | Path to SSH private key |
| `protocol_dest` | `"/data/user_storage/prd_protocols"` | Remote directory for protocols |
| `ssh_passphrase` | `""` | SSH key passphrase (empty if none) |

### PlateReaderConfig

| Field | Default | Description |
|---|---|---|
| `server` | `ServerConfig()` | Socket server settings |
| `python_32_path` | `r"C:\...\Python311-32\python.exe"` | Path to 32-bit Python |
| `client_script_path` | `""` (auto-detected) | Path to `Nano_Control_Client.py` |
| `auto_launch` | `False` | Auto-start the 32-bit client |
| `connection_timeout` | `60.0` | Seconds to wait for client connection |
| `default_wavelength` | `600` | Default measurement wavelength (nm) |
| `measurement_timeout` | `400.0` | Measurement timeout (seconds) |

### ServerConfig

| Field | Default | Description |
|---|---|---|
| `host` | `"localhost"` | Socket bind address |
| `port` | `65432` | Socket port |
| `buffer_size` | `1024` | Receive buffer size |

### LumidoxConfig

| Field | Default | Description |
|---|---|---|
| `port` | `""` | COM port (e.g. `"COM3"`); empty = use auto-detect |
| `baud_rate` | `19200` | Serial baud rate |
| `timeout` | `1.0` | Serial read timeout (seconds) |
| `auto_detect` | `True` | Scan for USB Serial / FTDI ports |

### PlateConfig

| Field | Default | Description |
|---|---|---|
| `rows` | `"ABCDEFGH"` | Row labels |
| `cols` | `12` | Number of columns |
| `blank_wells` | `("A1", "A2", "A3", "A4")` | Default blank well positions |
| `default_volume_ul` | `300.0` | Default well volume (µL) |

### TemperatureConfig

| Field | Default | Description |
|---|---|---|
| `start_temp` | `25.0` | Starting temperature (°C) |
| `target_temp` | `45.0` | Target temperature (°C) |
| `step_size` | `0.5` | Temperature step (°C) |
| `pause_time_seconds` | `300` | Pause at each step (seconds) |
| `stabilization_time` | `45.0` | Required stable time (seconds) |
| `check_interval` | `5.0` | Temperature polling interval (seconds) |
| `range_tolerance` | `0.2` | Acceptable deviation (°C) |

---

## Utilities

Importable directly from `project_unity`:

### Logging

- **`log_msg(message)`** — Print with `[YYYY-MM-DD HH:MM:SS]` prefix.
- **`@timeit`** — Decorator that logs a function's execution time.

### File I/O

- **`get_output_path()`** — Open a folder picker dialog, return selected path.
- **`get_file_path(title)`** — Open a file picker dialog, return selected path.
- **`load_data_new(path, start_wavelength, end_wavelength)`** — Load a plate reader CSV into a `pandas.DataFrame` with wavelength column headers.
- **`ensure_directory(path)`** — `os.makedirs(path, exist_ok=True)`, returns the path.
- **`move_file(source, dest_dir)`** — Move a file into a directory.

### Data Processing

- **`subtract_plate_background(df_measurement, df_background, wavelength)`** — Well-by-well background subtraction.
- **`calculate_blank_average(df_corrected, blank_wells, wavelength)`** — Average absorbance of blank wells.
- **`apply_corrections(df_corrected, blank_average, wavelength)`** — Subtract blank average from all wells.

### User Input

`UserInputHandler` provides validated input prompts:

```python
from project_unity.utils import UserInputHandler

temp = UserInputHandler.get_float("Enter temperature (°C)", default=25.0)
confirmed = UserInputHandler.wait_for_confirmation("Proceed?")
UserInputHandler.wait_for_ready("Press Enter when plate is loaded")
```

---

## The 32-Bit Plate Reader Client

The BMG SPECTROstar Nano exposes its API through ActiveX COM, which only works in 32-bit Python. Project Unity bridges this gap with a client/server architecture:

```
┌──────────────────────┐      socket      ┌──────────────────────────┐
│  Your script         │ ◄──────────────► │  Nano_Control_Client.py  │
│  (64-bit Python)     │   localhost:65432 │  (32-bit Python)         │
│  PlateReaderInstrument                   │  ActiveX COM → BMG       │
└──────────────────────┘                   └──────────────────────────┘
```

**Option A — Manual launch** (default):

1. Open a terminal and run:
   ```
   C:\...\Python311-32\python.exe Nano_Control_Client.py
   ```
2. In your script, use `PlateReaderInstrument(auto_launch=False)` (the default).

**Option B — Auto-launch**:

```python
with PlateReaderInstrument(
    auto_launch=True,
    python_32_path=r"C:\...\Python311-32\python.exe",
) as reader:
    reader.run_measurement(600, "output/")
```

The client script location is auto-detected relative to the package, but can be overridden with `client_script_path`.

---

## Troubleshooting

### OT-2 Connection

| Symptom | Fix |
|---|---|
| `Connection refused` | Verify the OT-2 IP address in `OT2Config.hostname`. The robot must be on the same network. |
| `Authentication failed` | Check `ssh_key_path` points to the correct private key. Ensure the key is not passphrase-protected, or set `ssh_passphrase`. |
| `Protocol not found` on robot | Ensure `protocol_dest` matches the directory you uploaded to. Default is `/data/user_storage/prd_protocols`. |
| `Protocol Finished` not detected | The protocol output may have been buffered. Check the `full_output` in the return value or increase `timeout`. |

### Plate Reader

| Symptom | Fix |
|---|---|
| `No client connection within 60s` | Ensure `Nano_Control_Client.py` is running in **32-bit** Python. Check that the port (default 65432) is not blocked. |
| `pywin32` import error in client | Install `pywin32` in the 32-bit Python: `python -m pip install pywin32`. |
| Measurement timeout | The plate reader may be busy. Increase `measurement_timeout` in `PlateReaderConfig` or the `timeout` parameter on `run_measurement()`. |

### Lumidox

| Symptom | Fix |
|---|---|
| `No serial ports found` | Ensure the Lumidox II USB cable is connected. Install FTDI drivers if needed. |
| `No recommended port found` | The auto-detect looks for "USB Serial Port" or "FTDI" in the port description. Specify the port manually via `LumidoxConfig(port="COM3", auto_detect=False)`. |
| Commands hang | Check `baud_rate` (should be 19200) and `timeout` in `LumidoxConfig`. |

### General

- **Metadata is always saved**, even when an experiment fails. Check the output directory for the JSON file.
- **Event logs** inside the metadata contain timestamped entries for every significant action, making post-mortem debugging straightforward.
- **Context managers** guarantee cleanup. If a script crashes between `connect()` and `disconnect()`, instruments are left in an unknown state — always use `with` blocks.

---

## Examples

The `examples/` directory contains runnable scripts for every use case:

| File | Description |
|---|---|
| `example_ot2_only.py` | OT-2 protocol execution, custom configs, direct control |
| `example_plate_reader_only.py` | Single measurement, time course, temperature ramp, auto-launch |
| `example_lumidox.py` | Direct control, timed exposure, multi-stage sweep, custom sequences |
| `example_combined.py` | OT-2 + plate reader workflows, iterative optimization |
| `example_custom_experiment.py` | Building your own experiment classes from `BaseExperiment` |

See the [examples README](examples/README.md) for quick-start snippets and template listings.
