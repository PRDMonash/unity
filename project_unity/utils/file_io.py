"""
File I/O utilities for OT-2 and plate reader control.

Provides file selection dialogs and data loading functions.
"""

import os
from tkinter import Tk, filedialog
from typing import Optional

import pandas as pd

from .logging import log_msg


def get_output_path() -> str:
    """
    Prompt the user to select an output folder using a dialog.
    
    Returns:
        Full path of the selected folder.
    """
    root = Tk()
    root.withdraw()  # Hide the main Tkinter window
    
    while True:
        output_path = filedialog.askdirectory(title="Select Output Folder")
        
        if not output_path:
            log_msg("No folder selected, please select a folder.")
        else:
            break
    
    root.quit()
    return output_path


def get_file_path(title: str = "Select a File") -> str:
    """
    Prompt the user to select a file using a dialog.
    
    Args:
        title: The title for the file selection dialog.
        
    Returns:
        Full path of the selected file.
    """
    root = Tk()
    root.withdraw()  # Hide the main Tkinter window
    
    while True:
        file_name = filedialog.askopenfilename(title=title)
        
        if not file_name:
            log_msg("No file selected, please select a file.")
        else:
            break
    
    root.quit()
    return file_name


def load_data_new(
    path: str,
    start_wavelength: int = 220,
    end_wavelength: int = 1000
) -> pd.DataFrame:
    """
    Load a CSV file without headers and rename columns for wavelength data.
    
    Assumes the first column contains identifiers and remaining columns
    contain wavelength-indexed measurements.
    
    Args:
        path: The file path of the CSV to load.
        start_wavelength: The starting wavelength for column renaming.
        end_wavelength: The ending wavelength for column renaming.
        
    Returns:
        DataFrame with 'Row/Col' as first column and wavelengths as remaining columns.
        Returns empty DataFrame on error.
    """
    try:
        df = pd.read_csv(path, header=None)
        df.columns = ['Row/Col'] + list(range(start_wavelength, end_wavelength + 1))
        return df
    except FileNotFoundError as e:
        log_msg(f"Error: File not found - {e}")
    except pd.errors.EmptyDataError as e:
        log_msg(f"Error: Empty file - {e}")
    except Exception as e:
        log_msg(f"Error loading file: {e}")
    
    return pd.DataFrame()


def ensure_directory(path: str) -> str:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: The directory path to ensure exists.
        
    Returns:
        The path that was created/verified.
    """
    os.makedirs(path, exist_ok=True)
    return path


def move_file(source: str, dest_dir: str) -> str:
    """
    Move a file to a destination directory.
    
    Args:
        source: Source file path.
        dest_dir: Destination directory path.
        
    Returns:
        New file path after moving.
    """
    import shutil
    
    new_path = os.path.join(dest_dir, os.path.basename(source))
    shutil.move(source, new_path)
    return new_path
