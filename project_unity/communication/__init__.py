"""
Communication modules for OT-2 and plate reader control.

Provides socket communication with the plate reader and
SSH/SCP communication with the OT-2 robot.
"""

from .socket_client import send_message, receive_message
from .ot2_ssh import run_subprocess, run_ssh_command, OT2Connection

__all__ = [
    "send_message",
    "receive_message",
    "run_subprocess",
    "run_ssh_command",
    "OT2Connection",
]
