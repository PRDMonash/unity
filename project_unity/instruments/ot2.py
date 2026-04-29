"""
OT-2 liquid handling robot instrument.

Provides high-level control of the Opentrons OT-2 robot via SSH,
including protocol upload and execution.

When ``use_persistent_execution`` is True (default), ``connect()`` opens a
long-lived interactive shell, starts Python once, and calls
``execute.get_protocol_api()`` so hardware is linked and subsequent
``run_protocol()`` calls only load and ``exec`` the protocol file and call
``run(ctx)`` in that same interpreter (much faster than cold
``opentrons_execute`` each time). Sequential protocols share one
``ProtocolContext``; deck state may carry over between runs.

Ancillary operations (``list_protocols``, ``test_connection``, etc.) use
separate ``exec_command`` channels and do not block the warm Python session.
"""

import os
import subprocess
import time
from typing import Optional, Tuple

import paramiko

from ..config import OT2Config, get_default_ot2_config
from ..utils.logging import log_msg
from .base import BaseInstrument, InstrumentStatus

READY_HW = "READY_HW"
RUN_COMPLETE = "RUN_COMPLETE"
RUN_FAILED = "RUN_FAILED"
SIM_READY = "SIM_READY"
SIM_COMPLETE = "SIM_COMPLETE"
SIM_FAILED = "SIM_FAILED"

_HW_WARMUP_TIMEOUT = 120.0
_SIM_WARMUP_TIMEOUT = 120.0
_PY_PROMPT_TIMEOUT = 60.0


class OT2Instrument(BaseInstrument):
    """
    Opentrons OT-2 liquid handling robot.

    With default config, ``connect()`` warms a persistent Python session and
    hardware API; ``run_protocol()`` reuses that session for fast repeat runs.
    Set ``OT2Config.use_persistent_execution`` to False to use subprocess
    ``opentrons_execute`` / ``opentrons_simulate`` instead (troubleshooting).

    Example:
        with OT2Instrument() as ot2:
            ot2.upload_protocol("my_protocol.py")
            success = ot2.run_protocol("my_protocol.py")

        # Subprocess fallback (cold start each ``run_protocol``).
        cfg = OT2Config(use_persistent_execution=False)
        with OT2Instrument(config=cfg) as ot2:
            ...

        # Optional: ``OT2Config(warm_simulate=True)`` enables warm ``simulate_protocol``
        # in the same interpreter (still validate on-hardware before relying on it).

    Attributes:
        config: OT2Config with connection settings
    """

    name = "OT-2"
    instrument_type = "OT2"

    def __init__(self, config: Optional[OT2Config] = None):
        self.config = config or get_default_ot2_config()
        self._ssh: Optional[paramiko.SSHClient] = None
        self._channel: Optional[paramiko.Channel] = None
        self._connected = False
        self._hardware_ready = False
        self._sim_ready = False

    @staticmethod
    def _safe_protocol_basename(protocol_name: str) -> str:
        base = os.path.basename(protocol_name.strip())
        if not base or base in (".", "..") or ".." in protocol_name:
            raise ValueError(f"Invalid protocol name: {protocol_name!r}")
        if not base.endswith(".py"):
            raise ValueError(f"Protocol must be a .py file name, got: {base!r}")
        return base

    def _open_ssh_client(self) -> None:
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._ssh.connect(
            self.config.hostname,
            username=self.config.username,
            key_filename=self.config.ssh_key_path,
            passphrase=self.config.ssh_passphrase or None,
        )

    def _drain_channel(self, max_bytes: int = 65536) -> str:
        if not self._channel:
            return ""
        out = ""
        for _ in range(500):
            if self._channel.recv_ready():
                out += self._channel.recv(max_bytes).decode("utf-8", errors="replace")
            else:
                break
        return out

    def _read_stream_until_substring(
        self,
        substring: str,
        timeout: float,
        *,
        stream_print: bool = True,
    ) -> str:
        """Accumulate channel output until ``substring`` appears or timeout."""
        if not self._channel:
            raise RuntimeError("No persistent shell channel")
        buf = ""
        start = time.time()
        last_print_len = 0
        while time.time() - start < timeout:
            if self._channel.recv_ready():
                chunk = self._channel.recv(65536).decode("utf-8", errors="replace")
                buf += chunk
                if stream_print and len(buf) > last_print_len:
                    new = buf[last_print_len:]
                    print(new, end="", flush=True)
                    last_print_len = len(buf)
            if substring in buf:
                return buf
            if self._channel.closed:
                break
            time.sleep(0.05)
        raise TimeoutError(
            f"Timed out after {timeout}s waiting for output containing {substring!r}"
        )

    def _read_stream_until_any_marker(
        self,
        markers: Tuple[str, ...],
        timeout: float,
        *,
        stream_print: bool = True,
    ) -> Tuple[str, Optional[str]]:
        """First matching marker wins. Returns (buffer, matched_marker_or_none)."""
        if not self._channel:
            raise RuntimeError("No persistent shell channel")
        buf = ""
        start = time.time()
        last_print_len = 0
        while time.time() - start < timeout:
            if self._channel.recv_ready():
                chunk = self._channel.recv(65536).decode("utf-8", errors="replace")
                buf += chunk
                if stream_print and len(buf) > last_print_len:
                    new = buf[last_print_len:]
                    print(new, end="", flush=True)
                    last_print_len = len(buf)
            for m in markers:
                if m in buf:
                    return buf, m
            if self._channel.closed:
                return buf, None
            time.sleep(0.05)
        return buf, None

    def _start_python_interactive(self) -> None:
        assert self._channel is not None
        self._channel.send("python3\n")
        self._read_stream_until_substring(">>>", _PY_PROMPT_TIMEOUT, stream_print=False)

    def _exec_on_channel(self, python_source: str) -> None:
        """Execute Python source via exec(repr(...)) so one paste works from >>>."""
        assert self._channel is not None
        payload = "exec(" + repr(python_source) + ")\n"
        self._channel.send(payload)

    def _warm_hardware_interpreter(self) -> None:
        """Assume shell channel exists and interactive Python prompt is active."""
        inner = (
            "from opentrons import execute\n"
            f"ctx = execute.get_protocol_api({self.config.api_level!r})\n"
            "print('" + READY_HW + "', flush=True)\n"
        )
        self._exec_on_channel(inner)
        self._read_stream_until_substring(READY_HW, _HW_WARMUP_TIMEOUT)
        log_msg(f"Warm Python session ready ({READY_HW}); hardware API level {self.config.api_level!r}.")
        self._hardware_ready = True

    def _warm_simulate_interpreter(self) -> None:
        inner = (
            "from opentrons import simulate\n"
            f"sim_ctx = simulate.get_protocol_api({self.config.api_level!r})\n"
            "print('" + SIM_READY + "', flush=True)\n"
        )
        self._exec_on_channel(inner)
        self._read_stream_until_substring(SIM_READY, _SIM_WARMUP_TIMEOUT)
        log_msg(f"Warm simulation context ready ({SIM_READY}).")
        self._sim_ready = True

    def _setup_persistent_shell(self) -> None:
        if self._hardware_ready and self._channel and not self._channel.closed:
            return

        log_msg("Starting persistent SSH shell and warming Python (this may take ~15–120s)...")

        self._hardware_ready = False
        self._sim_ready = False

        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None

        assert self._ssh is not None
        self._channel = self._ssh.invoke_shell()
        time.sleep(0.3)
        self._drain_channel()

        self._start_python_interactive()
        self._warm_hardware_interpreter()

    def connect(self) -> bool:
        """
        Establish SSH to the OT-2.

        With ``use_persistent_execution``, also starts ``python3`` over
        ``invoke_shell`` and warms ``execute.get_protocol_api``.
        """
        if self.config.use_persistent_execution:
            if (
                self._connected
                and self._ssh
                and self._channel
                and not self._channel.closed
                and self._hardware_ready
            ):
                return True

            log_msg(f"Connecting to OT-2 at {self.config.hostname}...")
            try:
                if self._ssh is None:
                    self._open_ssh_client()
                self._setup_persistent_shell()
                self._connected = True
                log_msg("Connected to OT-2 (persistent session).")
                return True
            except Exception as e:
                log_msg(f"Failed to connect to OT-2: {e}")
                self._reset_connection_state_after_failure()
                raise
        else:
            if self._connected and self._ssh:
                return True
            log_msg(f"Connecting to OT-2 at {self.config.hostname}...")
            try:
                self._open_ssh_client()
                self._connected = True
                log_msg("Connected to OT-2 successfully.")
                return True
            except Exception as e:
                log_msg(f"Failed to connect to OT-2: {e}")
                self._connected = False
                raise

    def _reset_connection_state_after_failure(self) -> None:
        self._hardware_ready = False
        self._sim_ready = False
        self._connected = False
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
            self._ssh = None

    def disconnect(self) -> None:
        self._hardware_ready = False
        self._sim_ready = False
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
            self._ssh = None
        self._connected = False
        log_msg("Disconnected from OT-2.")

    def status(self) -> InstrumentStatus:
        details = {}
        ready = False

        if self._connected and self._ssh:
            try:
                stdout, stderr = self._execute_command("uname -a")
                details["system_info"] = stdout.strip()
                if self.config.use_persistent_execution:
                    details["persistent_hw_ready"] = self._hardware_ready
                    details["persistent_sim_ready"] = self._sim_ready
                ready = True
            except Exception as e:
                details["error"] = str(e)

        return InstrumentStatus(
            connected=self._connected,
            ready=ready,
            details=details,
        )

    def test_connection(self) -> bool:
        try:
            stdout, stderr = self._execute_command('echo "OT-2 Connection OK"')
            return "Connection OK" in stdout
        except Exception:
            return False

    def _execute_command(self, command: str) -> Tuple[str, str]:
        if not self._ssh or not self._connected:
            raise RuntimeError("Not connected to OT-2")

        stdin, stdout, stderr = self._ssh.exec_command(command)
        return stdout.read().decode(), stderr.read().decode()

    def upload_protocol(self, local_path: str) -> bool:
        if not os.path.exists(local_path):
            log_msg(f"File not found: {local_path}")
            return False

        scp_command = [
            "scp",
            "-i",
            self.config.ssh_key_path,
            "-O",
            local_path,
            f"{self.config.username}@{self.config.hostname}:{self.config.protocol_dest}",
        ]

        try:
            log_msg(f"Uploading {os.path.basename(local_path)} to OT-2...")
            subprocess.run(
                scp_command,
                check=True,
                text=True,
                capture_output=True,
            )
            log_msg("File uploaded successfully.")
            return True

        except subprocess.CalledProcessError as e:
            log_msg(f"Upload failed: {e}")
            log_msg(f"Error output: {e.stderr}")
            return False

    def upload_file(self, local_path: str) -> bool:
        return self.upload_protocol(local_path)

    def _build_run_payload(
        self,
        protocol_basename: str,
        context_var: str,
        *,
        ok_marker: str = RUN_COMPLETE,
        fail_marker: str = RUN_FAILED,
    ) -> str:
        dest = self.config.protocol_dest
        return (
            "import os, traceback\n"
            f"os.chdir({dest!r})\n"
            f"_p = os.path.join({dest!r}, {protocol_basename!r})\n"
            "try:\n"
            "    with open(_p) as _f:\n"
            f"        _code = compile(_f.read(), {protocol_basename!r}, 'exec')\n"
            "    _ns = {'__builtins__': __builtins__}\n"
            "    exec(_code, _ns)\n"
            f"    _ns['run']({context_var})\n"
            f"    print({ok_marker!r}, flush=True)\n"
            "except Exception:\n"
            "    traceback.print_exc()\n"
            f"    print({fail_marker!r}, flush=True)\n"
        )

    def _run_protocol_persistent(self, protocol_basename: str, timeout: float) -> bool:
        if not self._channel or not self._hardware_ready:
            raise RuntimeError("Persistent hardware session not ready; call connect() first.")
        payload = self._build_run_payload(protocol_basename, "ctx")
        self._exec_on_channel(payload)
        buf, marker = self._read_stream_until_any_marker(
            (RUN_COMPLETE, RUN_FAILED),
            timeout,
        )
        if marker == RUN_COMPLETE:
            log_msg("Protocol completed successfully (persistent session).")
            return True
        if marker == RUN_FAILED:
            log_msg("Protocol failed (see traceback above).")
            return False
        log_msg("Protocol end not detected (timeout or channel closed).")
        return False

    def _run_protocol_subprocess(
        self,
        protocol_basename: str,
        timeout: float,
        *,
        simulate: bool,
    ) -> bool:
        if not self._ssh or not self._connected:
            raise RuntimeError("Not connected to OT-2")

        protocol_path = f"'{self.config.protocol_dest}/{protocol_basename}'"
        tool = "opentrons_simulate" if simulate else "opentrons_execute"
        command = f'sh -l -c "{tool} {protocol_path}"'

        log_msg(f"Running {'simulation' if simulate else 'OT-2 protocol'} (subprocess): {protocol_basename}")

        try:
            stdin, stdout, stderr = self._ssh.exec_command(command)
            start_time = time.time()
            while True:
                if time.time() - start_time > timeout:
                    log_msg("Protocol execution timed out")
                    return False
                line = stdout.readline()
                if not line:
                    break
                print(line, end="")
                time.sleep(0.01)

            exit_status = stdout.channel.recv_exit_status()
            err_text = stderr.read().decode()
            success = exit_status == 0
            if success:
                log_msg("Protocol subprocess finished (exit status 0).")
            else:
                if err_text:
                    log_msg(f"stderr: {err_text}")
                log_msg(f"Protocol subprocess failed (exit status {exit_status}).")
            return success

        except Exception as e:
            log_msg(f"Error running protocol subprocess: {e}")
            return False

    def run_protocol(self, protocol_name: str, timeout: float = 3600.0) -> bool:
        if not self._ssh or not self._connected:
            raise RuntimeError("Not connected to OT-2")

        protocol_basename = self._safe_protocol_basename(protocol_name)

        log_msg(f"Running OT-2 protocol: {protocol_basename}")

        if self.config.use_persistent_execution:
            return self._run_protocol_persistent(protocol_basename, timeout)
        return self._run_protocol_subprocess(protocol_basename, timeout, simulate=False)

    def _simulate_protocol_persistent(self, protocol_basename: str, timeout: float) -> bool:
        if not self._channel or not self._hardware_ready:
            raise RuntimeError("Persistent session not ready; call connect() first.")
        if not self._sim_ready:
            log_msg("Warming simulation context (first use)...")
            self._warm_simulate_interpreter()

        payload = self._build_run_payload(
            protocol_basename,
            "sim_ctx",
            ok_marker=SIM_COMPLETE,
            fail_marker=SIM_FAILED,
        )
        self._exec_on_channel(payload)
        buf, marker = self._read_stream_until_any_marker(
            (SIM_COMPLETE, SIM_FAILED),
            timeout,
        )
        if marker == SIM_COMPLETE:
            log_msg("Simulation completed successfully (persistent session).")
            return True
        if marker == SIM_FAILED:
            log_msg("Simulation failed (see traceback above).")
            return False
        log_msg("Simulation end not detected (timeout or channel closed).")
        return False

    def simulate_protocol(
        self,
        protocol_name: str,
        timeout: float = 3600.0,
    ) -> bool:
        if not self._ssh or not self._connected:
            raise RuntimeError("Not connected to OT-2")

        protocol_basename = self._safe_protocol_basename(protocol_name)

        log_msg(f"Simulating OT-2 protocol: {protocol_basename}")

        if self.config.use_persistent_execution and self.config.warm_simulate:
            return self._simulate_protocol_persistent(protocol_basename, timeout)
        return self._run_protocol_subprocess(protocol_basename, timeout, simulate=True)

    def run_protocol_with_upload(
        self,
        protocol_path: str,
        additional_files: Optional[list] = None,
        timeout: float = 3600.0,
    ) -> bool:
        if not self.upload_protocol(protocol_path):
            return False

        if additional_files:
            for file_path in additional_files:
                if not self.upload_file(file_path):
                    log_msg(f"Failed to upload: {file_path}")
                    return False

        protocol_name = os.path.basename(protocol_path)
        return self.run_protocol(protocol_name, timeout)

    def list_protocols(self) -> list:
        try:
            stdout, stderr = self._execute_command(
                f"ls -1 {self.config.protocol_dest}/*.py 2>/dev/null"
            )
            if stdout:
                return [os.path.basename(p) for p in stdout.strip().split("\n")]
            return []
        except Exception as e:
            log_msg(f"Failed to list protocols: {e}")
            return []

    def get_robot_info(self) -> dict:
        info = {}

        try:
            stdout, _ = self._execute_command("uname -a")
            info["system"] = stdout.strip()

            stdout, _ = self._execute_command("python3 --version")
            info["python_version"] = stdout.strip()

            stdout, _ = self._execute_command("opentrons_execute --version 2>&1 || echo 'unknown'")
            info["opentrons_version"] = stdout.strip()

        except Exception as e:
            info["error"] = str(e)

        return info
