import win32com.client.gencache
import time
import os
import glob
import socket
import sys
import json
import argparse
from datetime import datetime

# =============================================================================
# Configuration
# =============================================================================
#
# This 32-bit client is intentionally standalone - it does NOT import the
# `project_unity` package because the package's dependencies are installed in
# the 64-bit Python environment. All settings are loaded from a JSON config
# file with the following resolution order (later sources override earlier):
#
#   1. Hard-coded DEFAULT_CONFIG below (sane defaults for a stock BMG install).
#   2. JSON file at <script-dir>/nano_client_config.json, if it exists.
#   3. JSON file pointed to by the NANO_CLIENT_CONFIG environment variable.
#   4. JSON file pointed to by the --config command-line argument.
#   5. Individual --host / --port / --control-name / etc. command-line flags.
#
# Copy `nano_client_config.example.json` to `nano_client_config.json` and edit
# it to match your machine. The user-local file is git-ignored.
# =============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_FILENAME = "nano_client_config.json"
DEFAULT_CONFIG_PATH = os.path.join(SCRIPT_DIR, DEFAULT_CONFIG_FILENAME)

DEFAULT_CONFIG = {
    "server": {
        # Must match ServerConfig in project_unity/config/settings.py
        "host": "localhost",
        "port": 65432,
    },
    "connection": {
        "max_retries": 30,
        "retry_delay_seconds": 1,
    },
    "bmg": {
        # Name shown in BMG MARS control software for the connected instrument
        "control_name": "SPECTROstar Nano",
        # Where pre-defined BMG protocols (.mtp/.lbp definitions) live on disk.
        # Stock installer uses C:\Users\Public\BMG\...; older installs use
        # C:\Program Files (x86)\BMG\...
        "test_runs_path": r"C:\Users\Public\BMG\SPECTROstar Nano\User\Definit",
        # Where the BMG software writes raw run files
        "data_output_path": r"C:\Users\Public\BMG\SPECTROstar Nano\User\Data",
        # Where exported CSV result files are dropped (this script picks the
        # most recent CSV from this folder after each run)
        "csv_output_dir": r"C:\Users\Public\UV_VIS_DATA",
    },
    "logging": {
        # Empty string => write logs next to this script
        "log_dir": "",
    },
}


def _deep_merge(base: dict, overrides: dict) -> dict:
    """Recursively merge `overrides` into `base`, returning a new dict."""
    result = dict(base)
    for key, value in overrides.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_json_config(path: str) -> dict:
    """Load a JSON config file, raising a clear error on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file '{path}': {e}")
    except OSError as e:
        raise OSError(f"Failed to read config file '{path}': {e}")


def load_config(cli_args: argparse.Namespace) -> dict:
    """
    Build the active configuration by layering JSON files and CLI overrides
    on top of DEFAULT_CONFIG.

    :param cli_args: Parsed command-line arguments (see build_arg_parser).
    :return: A fully resolved config dictionary.
    """
    config = dict(DEFAULT_CONFIG)
    config["server"] = dict(DEFAULT_CONFIG["server"])
    config["connection"] = dict(DEFAULT_CONFIG["connection"])
    config["bmg"] = dict(DEFAULT_CONFIG["bmg"])
    config["logging"] = dict(DEFAULT_CONFIG["logging"])

    sources_loaded = []

    if os.path.exists(DEFAULT_CONFIG_PATH):
        config = _deep_merge(config, _load_json_config(DEFAULT_CONFIG_PATH))
        sources_loaded.append(DEFAULT_CONFIG_PATH)

    env_path = os.environ.get("NANO_CLIENT_CONFIG")
    if env_path:
        config = _deep_merge(config, _load_json_config(env_path))
        sources_loaded.append(f"$NANO_CLIENT_CONFIG={env_path}")

    if cli_args.config:
        config = _deep_merge(config, _load_json_config(cli_args.config))
        sources_loaded.append(cli_args.config)

    if cli_args.host is not None:
        config["server"]["host"] = cli_args.host
    if cli_args.port is not None:
        config["server"]["port"] = cli_args.port
    if cli_args.control_name is not None:
        config["bmg"]["control_name"] = cli_args.control_name

    config["_sources"] = sources_loaded
    return config


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "BMG SPECTROstar Nano 32-bit ActiveX bridge client. "
            "Connects to a 64-bit PlateReaderInstrument server over a TCP "
            "socket and forwards commands to the BMG via COM."
        )
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to a JSON config file (overrides settings from "
             "nano_client_config.json next to this script).",
    )
    parser.add_argument(
        "--host",
        help="Server host to connect to (overrides config).",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Server port to connect to (overrides config).",
    )
    parser.add_argument(
        "--control-name",
        dest="control_name",
        help="BMG instrument control name (overrides config).",
    )
    return parser


# Active configuration (populated by client_main); also referenced by helpers
CONFIG: dict = {}

# =============================================================================
# Logging Configuration
# =============================================================================

LOG_FILE = None


def init_logging():
    """Initialize the log file for this session."""
    global LOG_FILE
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"client_log_{timestamp}.txt"
    log_dir = (CONFIG.get("logging", {}).get("log_dir") or "").strip()
    if not log_dir:
        log_dir = SCRIPT_DIR
    os.makedirs(log_dir, exist_ok=True)
    LOG_FILE = os.path.join(log_dir, log_filename)
    
    # Write header to log file
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write(f"BMG SPECTROstar Nano Client Log\n")
        f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Python: {sys.version}\n")
        f.write(f"Platform: {sys.platform}\n")
        f.write("=" * 70 + "\n\n")
    
    print(f"[Log file: {LOG_FILE}]")


def log_msg(message: str):
    """
    Log a message with a timestamp to both console and file.

    :param message: String, the message to be logged.
    :return: None
    """
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    formatted_msg = f"[{current_time}] {message}"
    
    # Print to console
    print(formatted_msg)
    
    # Write to log file if initialized
    if LOG_FILE:
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(formatted_msg + "\n")
        except Exception:
            pass  # Silently fail if we can't write to log


class BmgCom:
    """
    A class to handle communication with the BMG SPECTROstar Nano plate reader using ActiveX.

    This class provides methods to control the plate reader, such as opening connections, running protocols,
    setting temperature, and inserting/ejecting plates.

    :param control_name: Optional name of the device to connect to. If provided, an attempt to open
                         a connection is made during initialization.
    """

    def __init__(self, control_name: str = None):
        """
        Initialize the BmgCom class and create the ActiveX COM object.

        :param control_name: Optional string specifying the control name for the reader. If provided,
                             an automatic connection is attempted.
        :raises: Exception if the ActiveX COM object instantiation or connection fails.
        """
        try:
            # Initialize ActiveX COM object
            self.com = win32com.client.Dispatch("BMG_ActiveX.BMGRemoteControl")
            log_msg("COM object created successfully.")

        except Exception as e:
            log_msg(f"Instantiation failed: {e}")
            raise

        if control_name:
            self.open(control_name)

    def open(self, control_name: str):
        """
        Open a connection to the BMG reader.

        :param control_name: String specifying the name of the reader to connect to.
        :raises: Exception if the connection fails or returns an error status.
        """
        try:
            result_status = self.com.OpenConnectionV(control_name)
            if result_status:
                raise Exception(f"OpenConnection failed: {result_status}")
            log_msg(f"Connected to {control_name} successfully.")
        except Exception as e:
            log_msg(f"Failed to open connection: {e}")
            raise

    def version(self):
        """
        Retrieve the software version of the BMG ActiveX Interface.

        :return: String representing the software version.
        :raises: Exception if the version retrieval fails.
        """
        try:
            version = self.com.GetVersion()
            log_msg(f"Software version: {version}")
            return version
        except Exception as e:
            log_msg(f"Failed to get version: {e}")
            raise

    def status(self):
        """
        Get the current status of the plate reader e.g., 'Ready', 'Busy'.

        :return: String representing the current status of the reader.
        :raises: Exception if the status retrieval fails.
        """
        try:
            status = self.com.GetInfoV("Status")
            return status.strip() if isinstance(status, str) else 'unknown'
        except Exception as e:
            log_msg(f"Failed to get status: {e}")
            raise

    def temp1(self):
        """
        Get the current temperature of the incubator at the bottom heating plate.

        :return: String representing the current temperature of the bottom heating plate.
        :raises: Exception if the temp1 retrieval fails.
        """
        try:
            temp1 = self.com.GetInfoV("Temp1")
            return temp1.strip() if isinstance(temp1, str) else 'unknown'
        except Exception as e:
            log_msg(f"Failed to get Temp1: {e}")
            raise

    def temp2(self):
        """
        Get the current temperature of the incubator at the top heating plate.

        :return: String representing the current temperature of the top heating plate.
        :raises: Exception if the temp2 retrieval fails.
        """
        try:
            temp2 = self.com.GetInfoV("Temp2")
            return temp2.strip() if isinstance(temp2, str) else 'unknown'
        except Exception as e:
            log_msg(f"Failed to get Temp2: {e}")
            raise

    def plate_in(self):
        """
        Insert the plate holder into the reader.

        :return: None
        :raises: Exception if the plate insertion command fails.
        """
        try:
            self.exec(['PlateIn'])
            log_msg("Plate inserted into the reader.")
        except Exception as e:
            log_msg(f"Failed to insert plate: {e}")
            raise

    def plate_out(self):
        """
        Eject the plate holder from the reader.

        :return: None
        :raises: Exception if the plate ejection command fails.
        """
        try:
            self.exec(['PlateOut'])
            log_msg("Plate ejected from the reader.")
        except Exception as e:
            log_msg(f"Failed to eject plate: {e}")
            raise

    def set_temp(self, temp: str):
        """
        Activate the plate reader's incubator and set it to a target temperature.
        Note that this command does not wait for the heating plates to reach the target temperature before proceeding.

        :return: None
        :raises: Exception if the set temp command fails.
        """
        try:
            self.exec(['Temp', temp])
            log_msg(f"Temperature set to {temp}.")
        except Exception as e:
            log_msg(f"Failed to set temperature: {e}")
            raise

    def run_protocol(self,
                     name: str,
                     test_path: str = None,
                     data_path: str = None
                     ):
        """
        Run a test protocol from pre-defined protocols stored on the plate reader.

        :param name: Protocol name as registered in the BMG MARS software.
        :param test_path: Directory containing protocol definitions. Defaults to
                          ``CONFIG["bmg"]["test_runs_path"]`` when omitted.
        :param data_path: Directory where the BMG software writes raw run files.
                          Defaults to ``CONFIG["bmg"]["data_output_path"]`` when omitted.
        :return: None
        :raises: Exception if the run protocol command fails.
        """
        if test_path is None:
            test_path = CONFIG["bmg"]["test_runs_path"]
        if data_path is None:
            data_path = CONFIG["bmg"]["data_output_path"]
        try:
            # self.exec(['Run', name, test_path, data_path])
            self.com.ExecuteAndWait(['Run', name, test_path, data_path])
            log_msg(f"Protocol '{name}' completed successfully.")
        except Exception as e:
            log_msg(f"Failed to run protocol '{name}': {e}")
            raise

    def exec(self, cmd: list):
        """
        Eject the plate holder from the reader.

        :return: None
        :raises: Exception if the execute command fails.
        """
        try:
            res = self.com.ExecuteAndWait(cmd)
            if res:
                raise Exception(f"Command {cmd} failed: {res}")
        except Exception as e:
            log_msg(f"Command execution failed: {e}")
            raise


def get_most_recent_csv(directory: str):
    """
    Find the most recently modified CSV file in the specified directory.

    This function searches for all CSV files in the provided directory and returns the one with the latest modification time.

    :param directory: The directory path to search for CSV files.
    :raises FileNotFoundError: If no CSV files are found in the directory.
    :return: The file path of the most recently modified CSV file.
    """
    # Search for all CSV files in the given directory
    csv_files = glob.glob(os.path.join(directory, '*.csv'))

    if not csv_files:
        raise FileNotFoundError("No CSV files found in the directory.")

    # Sort files by their last modified time in descending order
    latest_file = max(csv_files, key=os.path.getmtime)

    return latest_file


def get_csv():
    """
    Retrieve the most recent CSV file from the configured CSV output directory.

    This function identifies and returns the most recently modified CSV file
    from the directory specified by ``CONFIG["bmg"]["csv_output_dir"]``.

    :return: The file path of the most recent CSV file.
    """
    data_directory = CONFIG["bmg"]["csv_output_dir"]
    recent_csv = get_most_recent_csv(data_directory)
    return recent_csv


def measurements(bmg, protocol_name: str = 'Empty Plate Reading'):
    """
    Run a measurement protocol on the BMG SPECTROstar Nano reader.

    This function manages the process of ejecting the plate, inserting it, and executing the provided measurement protocol
    using the plate reader. It logs instrument statuses before and after each action.

    :param bmg: An instance of the BmgCom class controlling the plate reader.
    :param protocol_name: The name of the protocol to be run (default is 'Empty Plate Reading').
    :return: None
    """
    # Check instrument status
    log_msg(f"Instrument Status: {bmg.status()}")

    # Eject the plate
    # bmg.plate_out()

    # Insert the plate
    bmg.plate_in()
    log_msg(f"Instrument Status: {bmg.status()}")

    # # Set the target temperature
    # target_temp = '25.0'
    # bmg.set_temp(target_temp)

    bmg.run_protocol(
        protocol_name,
        CONFIG["bmg"]["test_runs_path"],
        CONFIG["bmg"]["data_output_path"],
    )

    # bmg.plate_out()


def send_message(sock, message_type: str, message_data: str = ""):
    """
    Send a message to the server with a specified message type.

    The message is encoded as a string that combines the message type and optional message data, separated by a pipe ('|') character.
    The message is then sent to the server through the provided socket.

    :param sock: The socket object used to communicate with the server.
    :param message_type: The type of the message being sent (e.g., 'REQUEST', 'UPDATE').
    :param message_data: Optional additional data to include with the message (default is an empty string).
    :return: None
    """
    message = f"{message_type}|{message_data}"
    sock.sendall(message.encode())


def receive_message(sock):
    """
    Receive a message from the server.

    This function waits to receive a message from the server via the provided socket. The received message is split into
    its type and data components, using the pipe ('|') character as a delimiter.

    :param sock: The socket object used to receive the message.
    :return: A tuple containing the message type and message data.
    """
    data = sock.recv(1024).decode()
    return data.split("|", 1)


def handle_server(bmg, s):
    """
    Handle communication with a server (64-bit script).

    This function manages the interaction between the BMG SPECTROstar Nano reader and the server. It listens for
    messages from the server and executes the appropriate actions, such as performing background readings,
    running protocols, and collecting sample data. Depending on the message type, it performs the necessary operations
    on the plate reader and sends back CSV data or other responses to the server.

    :param bmg: An instance of the BmgCom class controlling the SPECTROstar Nano reader.
    :param s: A socket object used to communicate with the server.
    :raises Exception: If there is a failure in communication or plate reading operations.
    :return: None
    """
    try:
        bmg.plate_out()
        while True:
            # Wait for a message from the server
            log_msg("Awaiting message from server")
            msg_type, msg_data = receive_message(s)

            if msg_type == "PLATE_BACKGROUND":
                log_msg("Plate background requested")
                bmg.plate_out()
                measurements(bmg, msg_data)
                bmg.plate_out()
                plate_bg = get_csv()
                send_message(s, "PLATE_BACKGROUND", plate_bg)

            if msg_type == "RUN_PROTOCOL":
                measurements(bmg, msg_data)
                csv_file = get_csv()
                send_message(s, "CSV_FILE", csv_file)

            if msg_type == "GET_TEMP":
                temp_string = f"{bmg.temp1()}, {bmg.temp2()}"
                send_message(s, "TEMPS", temp_string)

            if msg_type == "SET_TEMP":
                bmg.set_temp(msg_data)
                send_message(s, "OK")

            if msg_type == "PLATE_IN":
                log_msg("Plate-in requested")
                bmg.plate_in()
                send_message(s, "OK")

            if msg_type == "PLATE_OUT":
                log_msg("Plate-out requested")
                bmg.plate_out()
                send_message(s, "OK")

            if msg_type == "NEXT_READING":
                log_msg("Next sample requested.")
                log_msg("Ejecting reader & awaiting sample loading.")
                measurements(bmg)

            if msg_type == "SHUTDOWN":
                log_msg("Received signal from the server to shut down client.")
                break

            else:
                pass

        log_msg("Finished communication with 64-bit script.")

    except Exception as e:
        log_msg(f"Failed to communicate with 64-bit script: {e}")


def client_main(argv=None):
    """
    Main function to establish communication between the BMG SPECTROstar Nano reader and the 64-bit server.

    This function initializes the connection to the server and handles the communication protocol by dispatching
    the ActiveX object for the plate reader and sending/receiving messages to/from the server. It handles the full
    lifecycle of the client-server interaction and ensures proper connection termination.

    :param argv: Optional list of command-line arguments (defaults to ``sys.argv[1:]``).
    :raises Exception: If an error occurs during communication or setup.
    :return: None
    """
    import traceback

    global CONFIG

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        CONFIG = load_config(args)
    except (OSError, ValueError) as e:
        print(f"[Config error] {e}")
        print("Falling back to built-in defaults.")
        CONFIG = dict(DEFAULT_CONFIG)

    init_logging()
    log_msg("=" * 60)
    log_msg("BMG SPECTROstar Nano Client Starting")
    log_msg("=" * 60)

    sources = CONFIG.get("_sources") or []
    if sources:
        log_msg(f"Loaded config from: {', '.join(sources)}")
    else:
        log_msg(f"No config file found - using built-in defaults. "
                f"Create '{DEFAULT_CONFIG_PATH}' to customise.")

    server_host = CONFIG["server"]["host"]
    server_port = int(CONFIG["server"]["port"])
    control_name = CONFIG["bmg"]["control_name"]
    max_retries = int(CONFIG["connection"]["max_retries"])
    retry_delay = float(CONFIG["connection"]["retry_delay_seconds"])

    log_msg(f"Server target: {server_host}:{server_port}")
    log_msg(f"BMG control name: {control_name}")
    log_msg(f"Protocol path: {CONFIG['bmg']['test_runs_path']}")
    log_msg(f"Data path: {CONFIG['bmg']['data_output_path']}")
    log_msg(f"CSV pickup: {CONFIG['bmg']['csv_output_dir']}")

    try:
        log_msg("Initializing BMG COM object...")
        bmg = BmgCom(control_name)

        bmg.version()

        connected = False
        log_msg(f"Attempting to connect to server (max {max_retries} attempts)...")

        for attempt in range(1, max_retries + 1):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((server_host, server_port))
                log_msg(f"Connected to server on attempt {attempt}.")
                connected = True
                break
            except ConnectionRefusedError:
                log_msg(f"Connection attempt {attempt}/{max_retries} failed - server not ready. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            except Exception as e:
                log_msg(f"Connection attempt {attempt}/{max_retries} failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)

        if not connected:
            log_msg("ERROR: Failed to connect to server after all retries.")
            log_msg(f"Make sure the 64-bit server is running on {server_host}:{server_port}.")
            log_msg(f"Log file saved to: {LOG_FILE}")
            input("Press Enter to exit...")
            return
        
        try:
            handle_server(bmg, s)
            log_msg("Disconnecting...")
        finally:
            s.close()
            log_msg("Disconnected.")

    except Exception as e:
        log_msg(f"An error occurred: {e}")
        log_msg("Full traceback:")
        # Log the full traceback
        tb_str = traceback.format_exc()
        for line in tb_str.split('\n'):
            log_msg(f"  {line}")
        log_msg("Check that the plate reader is connected and powered on.")
        log_msg(f"Log file saved to: {LOG_FILE}")
        input("Press Enter to exit...")
    
    finally:
        log_msg("=" * 60)
        log_msg("Client session ended")
        log_msg("=" * 60)
        if LOG_FILE:
            log_msg(f"Full log saved to: {LOG_FILE}")


if __name__ == '__main__':
    client_main()