"""
Socket communication for plate reader control.

Provides message sending and receiving over socket connections.
"""

import socket
from typing import Tuple, Optional

from ..config import ServerConfig


def send_message(
    conn: socket.socket,
    message_type: str,
    message_data: str = ""
) -> None:
    """
    Send a message to the client, prefixed with a message type.
    
    Message format: "TYPE|DATA"
    
    Args:
        conn: Socket connection object.
        message_type: Type of message (e.g., 'RUN_PROTOCOL', 'GET_TEMP').
        message_data: Optional data payload.
    """
    message = f"{message_type}|{message_data}"
    conn.sendall(message.encode())


def receive_message(
    conn: socket.socket,
    buffer_size: int = 1024
) -> Tuple[str, str]:
    """
    Receive a message from the client.
    
    Args:
        conn: Socket connection object.
        buffer_size: Size of receive buffer.
        
    Returns:
        Tuple of (message_type, message_data).
    """
    data = conn.recv(buffer_size).decode()
    parts = data.split("|", 1)
    
    if len(parts) == 2:
        return parts[0], parts[1]
    else:
        return parts[0], ""


class PlateReaderConnection:
    """
    Context manager for plate reader socket connection.
    
    Provides a cleaner interface for managing the socket lifecycle.
    """
    
    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize connection with configuration.
        
        Args:
            config: Server configuration. Uses defaults if not provided.
        """
        self.config = config or ServerConfig()
        self.socket: Optional[socket.socket] = None
        self.conn: Optional[socket.socket] = None
    
    def __enter__(self) -> socket.socket:
        """Set up server and wait for connection."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.config.host, self.config.port))
        self.socket.listen()
        
        self.conn, _ = self.socket.accept()
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up connections."""
        if self.conn:
            try:
                self.conn.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.conn.close()
        
        if self.socket:
            self.socket.close()
    
    def send(self, message_type: str, message_data: str = "") -> None:
        """Send a message through the connection."""
        if self.conn:
            send_message(self.conn, message_type, message_data)
    
    def receive(self) -> Tuple[str, str]:
        """Receive a message from the connection."""
        if self.conn:
            return receive_message(self.conn, self.config.buffer_size)
        return "", ""
