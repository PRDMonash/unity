"""
OT-2 liquid handling robot instrument.

Provides high-level control of the Opentrons OT-2 via the Robot HTTP API
(default http://<hostname>:31950), including protocol upload and execution.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests

from ..config import OT2Config, get_default_ot2_config
from ..utils.logging import log_msg
from .base import BaseInstrument, InstrumentStatus


_TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "stopped"})
_PENDING_ANALYSIS_STATUSES = frozenset({"pending"})
# Run control actions (see POST /runs/{runId}/actions on robot OpenAPI).
_RUN_ACTION_PLAY = "play"
_RUN_ACTION_STOP = "stop"
_INTERRUPT_STOP_WAIT_S = 180.0
_HOME_REQUEST_TIMEOUT_S = 120.0


class OT2Instrument(BaseInstrument):
    """
    Opentrons OT-2 liquid handling robot.

    Uses the Robot HTTP API (Opentrons-Version header, port 31950 by default)
    to upload protocols, create runs, play them, and poll until completion.

    If you press Ctrl+C in the terminal while a protocol run is polling,
    the client sends a ``stop`` run action, waits (up to about three minutes)
    for a terminal run status, then calls ``POST /robot/home`` with
    ``{"target": "robot"}``, then re-raises ``KeyboardInterrupt``.

    Example:
        with OT2Instrument() as ot2:
            ot2.upload_protocol("my_protocol.py")
            success = ot2.run_protocol("my_protocol.py")

        config = OT2Config(hostname="192.168.1.100")
        with OT2Instrument(config=config) as ot2:
            ...

    Attributes:
        config: OT2Config with connection settings
    """

    name = "OT-2"
    instrument_type = "OT2"

    def __init__(self, config: Optional[OT2Config] = None):
        self.config = config or get_default_ot2_config()
        self._session: Optional[requests.Session] = None
        self._connected = False
        self._protocol_id_by_basename: Dict[str, str] = {}

    def _base_url(self) -> str:
        scheme = "https" if self.config.use_https else "http"
        return f"{scheme}://{self.config.hostname}:{self.config.http_port}"

    def _headers(self) -> Dict[str, str]:
        h = {"Opentrons-Version": self.config.opentrons_api_version}
        if self.config.robot_token:
            h["Authorization"] = f"Bearer {self.config.robot_token}"
        return h

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict] = None,
        files: Optional[list] = None,
        data: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> requests.Response:
        if not path.startswith("/"):
            path = "/" + path
        url = self._base_url() + path
        to = timeout if timeout is not None else self.config.request_timeout_s
        session = self._session or requests
        kwargs: Dict[str, Any] = {
            "headers": self._headers(),
            "timeout": to,
            "verify": self.config.verify_tls,
        }
        if json_body is not None:
            kwargs["json"] = json_body
        if files is not None:
            kwargs["files"] = files
        if data is not None:
            kwargs["data"] = data
        return session.request(method, url, **kwargs)

    def _get_json(self, path: str, **kwargs: Any) -> Any:
        r = self._request("GET", path, **kwargs)
        r.raise_for_status()
        return r.json()

    def connect(self) -> bool:
        """
        Verify reachability of the OT-2 Robot HTTP API (GET /health).

        Returns:
            True if the server responds with 200 OK.

        Raises:
            Exception: On network errors or non-success responses other than 503.
        """
        if self._connected and self._session:
            return True

        log_msg(f"Connecting to OT-2 at {self._base_url()}...")
        self._session = requests.Session()

        try:
            r = self._request("GET", "/health")
            if r.status_code == 200:
                self._connected = True
                log_msg("Connected to OT-2 successfully.")
                return True
            if r.status_code == 503:
                msg = "Robot server reports not ready (503); motors may be unavailable."
                log_msg(msg)
                self._connected = False
                raise ConnectionError(msg)
            r.raise_for_status()
            self._connected = True
            log_msg("Connected to OT-2 successfully.")
            return True
        except Exception as e:
            log_msg(f"Failed to connect to OT-2: {e}")
            self._connected = False
            if self._session:
                self._session.close()
                self._session = None
            raise

    def disconnect(self) -> None:
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None
        self._connected = False
        log_msg("Disconnected from OT-2.")

    def status(self) -> InstrumentStatus:
        details: Dict[str, Any] = {}
        ready = False
        if self._connected and self._session:
            try:
                r = self._request("GET", "/health")
                if r.status_code == 200:
                    payload = r.json()
                    details.update(payload if isinstance(payload, dict) else {})
                    ready = True
                elif r.status_code == 503:
                    details["warning"] = "Server up but robot not ready (503)."
                else:
                    details["error"] = f"HTTP {r.status_code}"
            except Exception as e:
                details["error"] = str(e)
        return InstrumentStatus(
            connected=self._connected,
            ready=ready,
            details=details,
        )

    def test_connection(self) -> bool:
        try:
            r = self._request("GET", "/health")
            return r.status_code == 200
        except Exception:
            return False

    def _require_session(self) -> requests.Session:
        if not self._session or not self._connected:
            raise RuntimeError("Not connected to OT-2")
        return self._session

    @staticmethod
    def _main_file_name(protocol_resource: dict) -> Optional[str]:
        files = protocol_resource.get("files") or []
        for f in files:
            if f.get("role") == "main":
                return f.get("name")
        if files:
            return files[0].get("name")
        return None

    def _upload_multipart(self, local_paths: List[str], key: Optional[str] = None) -> Optional[str]:
        self._require_session()
        handles = []
        try:
            parts = []
            for p in local_paths:
                if not os.path.exists(p):
                    log_msg(f"File not found: {p}")
                    return None
                fh = open(p, "rb")
                handles.append(fh)
                parts.append(
                    (
                        "files",
                        (os.path.basename(p), fh, "application/octet-stream"),
                    )
                )
            form: Dict[str, str] = {"protocol_kind": "standard"}
            if key:
                form["key"] = key[:100]

            log_msg(f"Uploading {len(local_paths)} file(s) to OT-2...")
            r = self._request(
                "POST",
                "/protocols",
                files=parts,
                data=form,
                timeout=max(self.config.request_timeout_s, 120.0),
            )
            if not r.ok:
                log_msg(f"Upload failed: HTTP {r.status_code} {r.text[:500]}")
                return None
            body = r.json()
            data = body.get("data") if isinstance(body, dict) else None
            if not isinstance(data, dict):
                log_msg("Upload response missing data.")
                return None
            pid = data.get("id")
            if not pid:
                log_msg("Upload response missing protocol id.")
                return None
            main_name = self._main_file_name(data)
            if main_name:
                self._protocol_id_by_basename[main_name] = pid
            log_msg("Upload successful.")
            return str(pid)
        finally:
            for h in handles:
                try:
                    h.close()
                except Exception:
                    pass

    def upload_protocol(self, local_path: str) -> bool:
        """
        Upload a protocol file to the OT-2 via POST /protocols.

        Optional supporting labware JSON files should be included in the same
        upload via run_protocol_with_upload.
        """
        key = os.path.basename(local_path)
        pid = self._upload_multipart([local_path], key=key)
        return pid is not None

    def upload_file(self, local_path: str) -> bool:
        """Alias for upload_protocol for clarity."""
        return self.upload_protocol(local_path)

    def _list_protocol_resources(self) -> List[dict]:
        body = self._get_json("/protocols")
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, list):
            return []
        return [x for x in data if isinstance(x, dict)]

    def _resolve_protocol_id(self, protocol_name: str) -> Optional[str]:
        if protocol_name in self._protocol_id_by_basename:
            return self._protocol_id_by_basename[protocol_name]

        candidates: List[tuple[str, str]] = []
        for res in self._list_protocol_resources():
            pid = res.get("id")
            main = self._main_file_name(res)
            if pid and main == protocol_name:
                created = res.get("createdAt") or ""
                candidates.append((created, str(pid)))

        if not candidates:
            log_msg(f"No uploaded protocol found with main file name {protocol_name!r}.")
            return None
        candidates.sort(key=lambda x: x[0])
        chosen = candidates[-1][1]
        self._protocol_id_by_basename[protocol_name] = chosen
        return chosen

    def _post_json_expect_data(self, path: str, payload: dict) -> Optional[dict]:
        r = self._request("POST", path, json_body=payload)
        if not r.ok:
            log_msg(f"{path} failed: HTTP {r.status_code} {r.text[:500]}")
            return None
        if not r.content:
            return {}
        try:
            body = r.json()
        except ValueError:
            return {}
        data = body.get("data") if isinstance(body, dict) else None
        return data if isinstance(data, dict) else None

    def _issue_run_action(self, run_id: str, action_type: str) -> bool:
        r = self._request(
            "POST",
            f"/runs/{run_id}/actions",
            json_body={"data": {"actionType": action_type}},
        )
        if not r.ok:
            log_msg(
                f"Run action {action_type!r} failed: HTTP {r.status_code} "
                f"{r.text[:300]}"
            )
            return False
        return True

    def _wait_run_terminal(
        self, run_id: str, deadline: float, *, log_prefix: str = ""
    ) -> bool:
        """Poll GET /runs/{run_id} until status is terminal or deadline passes."""
        last_status = ""
        prefix = f"{log_prefix}: " if log_prefix else ""
        while time.time() < deadline:
            try:
                body = self._get_json(f"/runs/{run_id}")
                run = body.get("data") if isinstance(body, dict) else None
                if not isinstance(run, dict):
                    time.sleep(0.5)
                    continue
                st = run.get("status") or ""
                if st != last_status:
                    log_msg(f"{prefix}Run {run_id} status: {st}")
                    last_status = str(st)
                if st in _TERMINAL_RUN_STATUSES:
                    return True
            except requests.RequestException as e:
                log_msg(f"{prefix}Polling run failed: {e}")
            time.sleep(0.5)
        return False

    def _home_robot(self) -> bool:
        r = self._request(
            "POST",
            "/robot/home",
            json_body={"target": "robot"},
            timeout=max(self.config.request_timeout_s, _HOME_REQUEST_TIMEOUT_S),
        )
        if not r.ok:
            log_msg(f"Homing failed: HTTP {r.status_code} {r.text[:300]}")
            return False
        return True

    def _cleanup_run_after_keyboard_interrupt(self, run_id: str) -> None:
        log_msg(
            "Keyboard interrupt — sending stop to current run; "
            "then homing when the run finishes stopping."
        )
        try:
            self._issue_run_action(run_id, _RUN_ACTION_STOP)
        except Exception as e:
            log_msg(f"Failed to send stop action: {e}")
        wait_deadline = time.time() + _INTERRUPT_STOP_WAIT_S
        reached = self._wait_run_terminal(
            run_id, wait_deadline, log_prefix="Interrupt cleanup"
        )
        if not reached:
            log_msg(
                "Run did not reach a terminal status within "
                f"{_INTERRUPT_STOP_WAIT_S}s after stop; homing anyway."
            )
        try:
            log_msg("Homing robot after interrupt...")
            if not self._home_robot():
                log_msg("Homing request was not accepted successfully.")
        except Exception as e:
            log_msg(f"Homing after interrupt failed: {e}")

    def _run_by_protocol_id(self, protocol_id: str, timeout: float) -> bool:
        self._require_session()
        log_msg(f"Starting run for protocol id {protocol_id}")
        run_data = self._post_json_expect_data(
            "/runs",
            {"data": {"protocolId": protocol_id}},
        )
        if not run_data:
            return False
        run_id = run_data.get("id")
        if not run_id:
            log_msg("Run creation response missing id.")
            return False

        try:
            play_resp = self._request(
                "POST",
                f"/runs/{run_id}/actions",
                json_body={"data": {"actionType": _RUN_ACTION_PLAY}},
            )
            if not play_resp.ok:
                log_msg(
                    f"Play failed: HTTP {play_resp.status_code} {play_resp.text[:500]}"
                )
                return False

            deadline = time.time() + timeout
            last_status = ""
            while time.time() < deadline:
                try:
                    body = self._get_json(f"/runs/{run_id}")
                    run = body.get("data") if isinstance(body, dict) else None
                    if not isinstance(run, dict):
                        time.sleep(0.5)
                        continue
                    st = run.get("status") or ""
                    if st != last_status:
                        log_msg(f"Run {run_id} status: {st}")
                        last_status = str(st)
                    if st in _TERMINAL_RUN_STATUSES:
                        ok = st == "succeeded"
                        errs = run.get("errors") or []
                        if isinstance(errs, list) and errs:
                            log_msg(
                                f"Run finished with {len(errs)} error record(s)."
                            )
                        return ok
                except requests.RequestException as e:
                    log_msg(f"Polling run failed: {e}")
                time.sleep(0.5)

            log_msg("Protocol execution timed out")
            return False
        except KeyboardInterrupt:
            self._cleanup_run_after_keyboard_interrupt(str(run_id))
            raise

    def run_protocol(self, protocol_name: str, timeout: float = 3600.0) -> bool:
        """
        Execute a protocol on the OT-2 via POST /runs and play action.

        The protocol must already be uploaded (main file basename must match
        protocol_name), unless it was uploaded in this session and cached.

        Ctrl+C during the run stops the protocol on the robot, waits for a
        terminal run status, homes the gantry, then re-raises KeyboardInterrupt.
        """
        self._require_session()
        protocol_id = self._resolve_protocol_id(protocol_name)
        if not protocol_id:
            return False
        return self._run_by_protocol_id(protocol_id, timeout)

    def simulate_protocol(self, protocol_name: str, timeout: float = 3600.0) -> bool:
        """
        Wait for robot-side static analysis of an uploaded protocol (HTTP API),
        not a full opentrons_simulate CLI session.

        Polls GET /protocols/{id}/analyses/{analysisId} until the analysis leaves
        pending state. Returns True when analysis completes without errors.
        """
        self._require_session()
        protocol_id = self._resolve_protocol_id(protocol_name)
        if not protocol_id:
            return False

        log_msg(f"Waiting for protocol analysis: {protocol_name}")

        deadline = time.time() + timeout
        analysis_id: Optional[str] = None

        try:
            body = self._get_json(f"/protocols/{protocol_id}/analyses")
            analyses = body.get("data") if isinstance(body, dict) else None
            if isinstance(analyses, list) and analyses:
                last = analyses[-1]
                if isinstance(last, dict) and last.get("id"):
                    analysis_id = str(last["id"])
        except requests.RequestException as e:
            log_msg(f"Listing analyses failed: {e}")

        if not analysis_id:
            created = self._post_json_expect_data(
                f"/protocols/{protocol_id}/analyses",
                {"data": {}},
            )
            if created and created.get("id"):
                analysis_id = str(created["id"])

        if not analysis_id:
            log_msg("Could not obtain a protocol analysis id.")
            return False

        while time.time() < deadline:
            try:
                body = self._get_json(
                    f"/protocols/{protocol_id}/analyses/{analysis_id}"
                )
                analysis = body.get("data") if isinstance(body, dict) else None
                if not isinstance(analysis, dict):
                    time.sleep(0.5)
                    continue
                st = analysis.get("status") or ""
                if st in _PENDING_ANALYSIS_STATUSES:
                    time.sleep(0.5)
                    continue
                errs = analysis.get("errors")
                if errs:
                    log_msg(f"Analysis completed with errors: {errs}")
                    return False
                if str(st).lower() == "failed":
                    return False
                log_msg(f"Analysis finished with status {st!r}.")
                return True
            except requests.RequestException as e:
                log_msg(f"Polling analysis failed: {e}")
                time.sleep(0.5)

        log_msg("Protocol analysis timed out")
        return False

    def run_protocol_with_upload(
        self,
        protocol_path: str,
        additional_files: Optional[list] = None,
        timeout: float = 3600.0,
    ) -> bool:
        paths = [protocol_path]
        if additional_files:
            paths.extend(additional_files)
        key = os.path.basename(protocol_path)
        protocol_id = self._upload_multipart(paths, key=key)
        if not protocol_id:
            return False
        return self._run_by_protocol_id(protocol_id, timeout)

    def list_protocols(self) -> list:
        try:
            self._require_session()
            names = []
            for res in self._list_protocol_resources():
                main = self._main_file_name(res)
                if main and main.endswith(".py"):
                    names.append(main)
            return names
        except Exception as e:
            log_msg(f"Failed to list protocols: {e}")
            return []

    def get_robot_info(self) -> dict:
        info: Dict[str, Any] = {}
        try:
            self._require_session()
            r = self._request("GET", "/health")
            if r.status_code != 200:
                info["error"] = f"HTTP {r.status_code}"
                return info
            payload = r.json()
            if isinstance(payload, dict):
                info.update(payload)
        except Exception as e:
            info["error"] = str(e)
        return info
