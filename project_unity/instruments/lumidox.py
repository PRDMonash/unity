"""
Lumidox II LED light controller instrument.

Provides high-level control of the Analytical Sales & Services Lumidox II
LED controller via serial (USB/FTDI) communication.

The Lumidox II supports up to 5 preset power stages and custom current
output for illuminating multi-well plates with specific wavelengths.
"""

import time
import threading
from typing import Optional, Dict, Any, List

import serial
import serial.tools.list_ports

from ..config import LumidoxConfig, get_default_lumidox_config
from ..utils.logging import log_msg
from .base import BaseInstrument, InstrumentStatus


# Stage register mappings for reading preset power levels
STAGE_REGISTERS = {
    1: {"current": b"78", "total_power": b"7b", "per_power": b"7c",
        "total_units": b"7d", "per_units": b"7e"},
    2: {"current": b"80", "total_power": b"83", "per_power": b"84",
        "total_units": b"85", "per_units": b"86"},
    3: {"current": b"88", "total_power": b"88", "per_power": b"8c",
        "total_units": b"8d", "per_units": b"8e"},
    4: {"current": b"90", "total_power": b"90", "per_power": b"94",
        "total_units": b"95", "per_units": b"96"},
    5: {"current": b"98", "total_power": b"9b", "per_power": b"9c",
        "total_units": b"9d", "per_units": b"9e"},
}

# Register addresses for device info
MODEL_REGISTERS = [b"6c", b"6d", b"6e", b"6f", b"70", b"71", b"72", b"73"]
SERIAL_REGISTERS = [
    b"60", b"61", b"62", b"63", b"64", b"65",
    b"66", b"67", b"68", b"69", b"6a", b"6b",
]
WAVELENGTH_REGISTERS = [b"76", b"81", b"82", b"89", b"8a"]


def _checksum(s: bytes) -> bytearray:
    """Calculate checksum for a Lumidox serial command."""
    value = sum(s[1:]) % 256
    return bytearray(str(hex(value)[2:]).rjust(2, '0'), 'utf8')


def _hex_to_dec(bufp: bytes) -> int:
    """Convert hexadecimal response bytes to a signed decimal value."""
    newval = 0
    divvy = 4096
    for pn in range(1, 5):
        vally = bufp[pn]
        subby = 48 if vally < 97 else 87
        newval += (bufp[pn] - subby) * divvy
        divvy /= 16
    if newval > 32767:
        newval = newval - 65536
    return int(newval)


def _decode_total_units(index: int) -> str:
    """Decode total power units from register index."""
    units_map = {
        0: "W TOTAL RADIANT POWER",
        1: "mW TOTAL RADIANT POWER",
        2: "W/cm² TOTAL IRRADIANCE",
        3: "mW/cm² TOTAL IRRADIANCE",
        4: "",
        5: "A TOTAL CURRENT",
        6: "mA TOTAL CURRENT",
    }
    return units_map.get(index, "UNKNOWN UNITS")


def _decode_per_units(index: int) -> str:
    """Decode per-well power units from register index."""
    units_map = {
        0: "W PER WELL",
        1: "mW PER WELL",
        2: "W TOTAL RADIANT POWER",
        3: "mW TOTAL RADIANT POWER",
        4: "mW/cm² PER WELL",
        5: "mW/cm²",
        6: "J/s",
        7: "",
        8: "A PER WELL",
        9: "mA PER WELL",
    }
    return units_map.get(index, "UNKNOWN UNITS")


def find_lumidox_ports() -> List[Dict[str, Any]]:
    """
    Scan for serial ports that may be a Lumidox II controller.

    Returns:
        List of dicts with keys ``port``, ``description``, ``recommended``.
        Ports containing "USB Serial Port" or "FTDI" are marked recommended.
    """
    ports = list(serial.tools.list_ports.comports())
    results = []
    for p in ports:
        desc = str(p)
        is_candidate = "USB Serial Port" in desc or "FTDI" in desc.upper()
        results.append({
            "port": p.device,
            "description": desc,
            "recommended": is_candidate,
        })
    return results


class LumidoxInstrument(BaseInstrument):
    """
    Analytical Sales & Services Lumidox II LED controller.

    Communicates with the controller over a serial (USB/FTDI) connection.
    Supports firing preset power stages (1-5), custom current output,
    and querying device information.

    Example:
        # Using context manager (recommended)
        with LumidoxInstrument() as lumidox:
            print(lumidox.get_device_info())
            lumidox.fire_stage(3)
            time.sleep(60)          # illuminate for 60 s
            lumidox.turn_off()

        # Custom configuration
        from project_unity.config import LumidoxConfig
        config = LumidoxConfig(port="COM5")
        with LumidoxInstrument(config=config) as lumidox:
            lumidox.fire_custom(current_ma=200)
            time.sleep(30)
            lumidox.turn_off()

        # Auto-detect COM port
        config = LumidoxConfig(auto_detect=True)
        with LumidoxInstrument(config=config) as lumidox:
            ...

    Attributes:
        config: LumidoxConfig with serial connection settings
    """

    name = "Lumidox II"
    instrument_type = "Lumidox"

    def __init__(self, config: Optional[LumidoxConfig] = None):
        """
        Initialize Lumidox II instrument.

        Args:
            config: Lumidox configuration. Uses defaults if not provided.
        """
        self.config = config or get_default_lumidox_config()
        self._ser: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self._connected = False

    # ------------------------------------------------------------------
    # Low-level serial helpers
    # ------------------------------------------------------------------

    def _get_com_val(self, command_hex: bytes, value: int = 0) -> int:
        """
        Send a command to the controller and return the response value.

        Args:
            command_hex: Two-byte hex command (e.g. ``b"15"``).
            value: Integer payload (0 for read commands).

        Returns:
            Decoded integer response from the controller.

        Raises:
            RuntimeError: If not connected.
        """
        if self._ser is None or not self._ser.is_open:
            raise RuntimeError("Not connected to Lumidox II")

        with self._lock:
            value = int(value)
            command = b'*' + command_hex
            if value == 0:
                command += b"0000"
            else:
                command += bytearray(
                    str(hex(value)[2:]).rjust(4, '0'), 'utf8'
                )
            command += _checksum(command)
            command += b'\r'

            self._ser.write(command)
            response = self._ser.read_until(b'^')
            return _hex_to_dec(response)

    # ------------------------------------------------------------------
    # BaseInstrument interface
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """
        Open the serial connection and put the device in remote mode.

        If ``config.auto_detect`` is True and ``config.port`` is empty,
        the first recommended (USB Serial / FTDI) port is used.

        Returns:
            True if connection was successful.

        Raises:
            ConnectionError: If no suitable port is found.
            serial.SerialException: If the port cannot be opened.
        """
        if self._connected and self._ser and self._ser.is_open:
            return True

        port = self.config.port

        # Auto-detect port if requested
        if self.config.auto_detect and not port:
            candidates = find_lumidox_ports()
            recommended = [p for p in candidates if p["recommended"]]
            if recommended:
                port = recommended[0]["port"]
                log_msg(f"Auto-detected Lumidox port: {port}")
            elif candidates:
                port = candidates[0]["port"]
                log_msg(f"No recommended port found; trying {port}")
            else:
                raise ConnectionError(
                    "No serial ports found. Is the Lumidox II connected?"
                )

        if not port:
            raise ConnectionError(
                "No COM port specified. Set config.port or enable auto_detect."
            )

        try:
            log_msg(f"Connecting to Lumidox II on {port}...")
            self._ser = serial.Serial(
                port,
                baudrate=self.config.baud_rate,
                timeout=self.config.timeout,
            )
            self._ser.reset_input_buffer()
            time.sleep(0.1)

            # Put device in remote mode (standby)
            self._get_com_val(b"15", 1)
            time.sleep(0.1)

            self._connected = True
            log_msg("Connected to Lumidox II successfully.")
            return True

        except Exception as e:
            log_msg(f"Failed to connect to Lumidox II: {e}")
            self._connected = False
            if self._ser:
                try:
                    self._ser.close()
                except Exception:
                    pass
                self._ser = None
            raise

    def disconnect(self) -> None:
        """
        Turn off LEDs, return device to local mode, and close the serial port.

        Safe to call multiple times.
        """
        if self._ser and self._ser.is_open:
            try:
                # Standby (LEDs off)
                self._get_com_val(b"15", 1)
                time.sleep(0.1)
                # Return to local mode
                self._get_com_val(b"15", 0)
                time.sleep(0.1)
            except Exception:
                pass
            try:
                self._ser.close()
            except Exception:
                pass

        self._ser = None
        self._connected = False
        log_msg("Disconnected from Lumidox II.")

    def status(self) -> InstrumentStatus:
        """
        Get current Lumidox II status.

        Returns:
            InstrumentStatus with connection state and device details.
        """
        details: Dict[str, Any] = {}
        ready = False

        if self._connected and self._ser and self._ser.is_open:
            try:
                fw = str(int(self._get_com_val(b"02", 0)))
                details["firmware"] = f"1.{fw}"
                ready = True
            except Exception as e:
                details["error"] = str(e)

        return InstrumentStatus(
            connected=self._connected,
            ready=ready,
            details=details,
        )

    def test_connection(self) -> bool:
        """
        Verify the connection by reading the firmware version.

        Returns:
            True if the device responds correctly.
        """
        try:
            self._get_com_val(b"02", 0)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Device information
    # ------------------------------------------------------------------

    def get_device_info(self) -> Dict[str, Any]:
        """
        Read comprehensive device information from the controller.

        Returns:
            Dictionary with keys:
            ``firmware``, ``model``, ``serial``, ``wavelength``,
            ``max_current_ma``.
        """
        firmware = str(int(self._get_com_val(b"02", 0)))
        model = ''.join(
            chr(int(self._get_com_val(reg, 0))) for reg in MODEL_REGISTERS
        )
        serial_num = ''.join(
            chr(int(self._get_com_val(reg, 0))) for reg in SERIAL_REGISTERS
        )
        wavelength = ''.join(
            chr(int(self._get_com_val(reg, 0))) for reg in WAVELENGTH_REGISTERS
        )
        max_current = int(self._get_com_val(b"98", 0))

        return {
            "firmware": f"1.{firmware}",
            "model": model.strip(),
            "serial": serial_num.strip(),
            "wavelength": wavelength.strip(),
            "max_current_ma": max_current,
        }

    def get_firmware_version(self) -> str:
        """Return the firmware version string (e.g. ``'1.5'``)."""
        fw = str(int(self._get_com_val(b"02", 0)))
        return f"1.{fw}"

    def get_wavelength(self) -> str:
        """Return the LED wavelength label (e.g. ``'405nm'``)."""
        return ''.join(
            chr(int(self._get_com_val(reg, 0))) for reg in WAVELENGTH_REGISTERS
        ).strip()

    def get_max_current(self) -> int:
        """Return the maximum allowed drive current in mA."""
        return int(self._get_com_val(b"98", 0))

    # ------------------------------------------------------------------
    # Stage information
    # ------------------------------------------------------------------

    def get_stage_info(self, stage: int) -> Dict[str, Any]:
        """
        Read the calibrated power/current information for one preset stage.

        Args:
            stage: Stage number (1-5).

        Returns:
            Dictionary with ``stage``, ``current_ma``, ``total_power``,
            ``total_units``, ``per_power``, ``per_units``.

        Raises:
            ValueError: If stage is not 1-5.
        """
        if stage < 1 or stage > 5:
            raise ValueError(f"Stage must be 1-5, got {stage}")

        regs = STAGE_REGISTERS[stage]
        return {
            "stage": stage,
            "current_ma": int(self._get_com_val(regs["current"], 0)),
            "total_power": int(self._get_com_val(regs["total_power"], 0)) / 10,
            "total_units": _decode_total_units(
                int(self._get_com_val(regs["total_units"], 0))
            ),
            "per_power": int(self._get_com_val(regs["per_power"], 0)) / 10,
            "per_units": _decode_per_units(
                int(self._get_com_val(regs["per_units"], 0))
            ),
        }

    def get_all_stages(self) -> List[Dict[str, Any]]:
        """
        Read information for all 5 preset stages.

        Returns:
            List of stage info dictionaries (see :meth:`get_stage_info`).
        """
        return [self.get_stage_info(s) for s in range(1, 6)]

    # ------------------------------------------------------------------
    # LED control
    # ------------------------------------------------------------------

    def fire_stage(self, stage: int) -> int:
        """
        Fire (turn on) LEDs using a preset power stage.

        The controller enters output mode and drives at the current
        calibrated for the given stage.

        Args:
            stage: Stage number (1-5).

        Returns:
            The current in mA that was set.

        Raises:
            ValueError: If stage is not 1-5.
        """
        if stage < 1 or stage > 5:
            raise ValueError(f"Stage must be 1-5, got {stage}")

        regs = STAGE_REGISTERS[stage]

        # Enter output mode
        self._get_com_val(b"15", 3)
        time.sleep(0.1)

        # Read stage current and set it
        current_ma = int(self._get_com_val(regs["current"], 0))
        self._get_com_val(b"41", current_ma)

        log_msg(f"Lumidox II firing stage {stage} at {current_ma} mA")
        return current_ma

    def fire_custom(self, current_ma: int) -> None:
        """
        Fire LEDs at a specific current.

        Args:
            current_ma: Drive current in milliamps.

        Raises:
            ValueError: If current exceeds the device maximum.
        """
        max_current = self.get_max_current()
        if current_ma > max_current:
            raise ValueError(
                f"Requested {current_ma} mA exceeds device maximum "
                f"of {max_current} mA"
            )

        # Enter output mode
        self._get_com_val(b"15", 3)
        time.sleep(0.1)

        # Set custom current
        self._get_com_val(b"41", current_ma)
        log_msg(f"Lumidox II firing at {current_ma} mA (custom)")

    def turn_off(self) -> None:
        """Turn off LED output (return to standby/remote mode)."""
        self._get_com_val(b"15", 1)
        time.sleep(0.1)
        log_msg("Lumidox II LEDs turned off.")

    def timed_exposure(
        self,
        duration_seconds: float,
        stage: Optional[int] = None,
        current_ma: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Run a timed illumination: fire, wait, then turn off.

        Exactly one of ``stage`` or ``current_ma`` must be provided.

        Args:
            duration_seconds: How long to illuminate in seconds.
            stage: Preset stage number (1-5).
            current_ma: Custom drive current in mA.

        Returns:
            Dictionary with ``duration_seconds``, ``current_ma``, and
            ``stage`` (if applicable).

        Raises:
            ValueError: If neither or both of stage/current_ma are given.
        """
        if (stage is None) == (current_ma is None):
            raise ValueError("Provide exactly one of 'stage' or 'current_ma'")

        if stage is not None:
            actual_current = self.fire_stage(stage)
        else:
            self.fire_custom(current_ma)
            actual_current = current_ma

        log_msg(f"Illuminating for {duration_seconds}s...")

        try:
            time.sleep(duration_seconds)
        finally:
            self.turn_off()

        result = {
            "duration_seconds": duration_seconds,
            "current_ma": actual_current,
        }
        if stage is not None:
            result["stage"] = stage
        return result
