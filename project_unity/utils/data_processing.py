"""
Data processing utilities for plate reader measurements.

Provides functions for background subtraction, blank correction,
and absorbance data processing.
"""

from typing import List, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from .logging import log_msg


def subtract_plate_background(
    df_measurement: pd.DataFrame,
    df_background: pd.DataFrame,
    wavelength: int
) -> pd.DataFrame:
    """
    Subtract plate background from measurement data.
    
    This corrects for well-to-well variations in plate thickness.
    
    Args:
        df_measurement: DataFrame with measurement data.
        df_background: DataFrame with background (empty plate) data.
        wavelength: The wavelength column to process.
        
    Returns:
        Corrected DataFrame with background subtracted.
    """
    df_corrected = df_measurement.copy()
    
    for idx, row in df_corrected.iterrows():
        well_id = row['Row/Col']
        
        # Find corresponding background value
        bg_row = df_background[df_background['Row/Col'] == well_id]
        if bg_row.empty:
            bg_row = df_background[df_background['Row/Col'].str.strip() == well_id.strip()]
        
        if not bg_row.empty:
            bg_value = float(bg_row[wavelength].values[0])
            df_corrected.at[idx, wavelength] = row[wavelength] - bg_value
        else:
            log_msg(f"WARNING: No background found for well {well_id}, skipping background correction")
    
    return df_corrected


def calculate_blank_average(
    df_corrected: pd.DataFrame,
    blank_wells: List[str],
    wavelength: int
) -> Tuple[float, List[float]]:
    """
    Calculate the average absorbance of blank wells.
    
    Args:
        df_corrected: Background-corrected DataFrame.
        blank_wells: List of blank well identifiers.
        wavelength: The wavelength column to process.
        
    Returns:
        Tuple of (blank_average, list of individual blank values).
    """
    blank_values = []
    
    for blank_well in blank_wells:
        blank_row = df_corrected[df_corrected['Row/Col'] == blank_well]
        if blank_row.empty:
            blank_row = df_corrected[df_corrected['Row/Col'].str.strip() == blank_well]
        
        if not blank_row.empty:
            blank_values.append(float(blank_row[wavelength].values[0]))
        else:
            log_msg(f"WARNING: Blank well {blank_well} not found in data")
    
    if blank_values:
        blank_average = float(np.mean(blank_values))
    else:
        log_msg("WARNING: No blank wells found, using 0.0 for blank average")
        blank_average = 0.0
    
    return blank_average, blank_values


def apply_corrections(
    df_corrected: pd.DataFrame,
    blank_average: float,
    wavelength: int
) -> pd.DataFrame:
    """
    Apply blank subtraction to all wells.
    
    Args:
        df_corrected: Background-corrected DataFrame.
        blank_average: Average blank value to subtract.
        wavelength: The wavelength column to process.
        
    Returns:
        Fully corrected DataFrame.
    """
    df_corrected[wavelength] = df_corrected[wavelength] - blank_average
    return df_corrected


def extract_well_absorbance(
    df: pd.DataFrame,
    well_id: str,
    wavelength: int
) -> Optional[float]:
    """
    Extract absorbance value for a specific well.
    
    Args:
        df: DataFrame with absorbance data.
        well_id: Well identifier (e.g., 'A5').
        wavelength: The wavelength column to read.
        
    Returns:
        Absorbance value or None if well not found.
    """
    well_data = df[df['Row/Col'] == well_id]
    
    if well_data.empty:
        well_data = df[df['Row/Col'].str.strip() == well_id]
    
    if not well_data.empty:
        return float(well_data[wavelength].values[0])
    
    return None


def process_measurement_data(
    measurement_path: str,
    background_path: str,
    blank_wells: List[str],
    measurement_wells: List[str],
    wavelength: int
) -> Tuple[List[float], float]:
    """
    Complete processing pipeline for measurement data.
    
    Performs:
    1. Load measurement and background data
    2. Subtract plate background
    3. Calculate blank average
    4. Subtract blank average
    5. Extract absorbance values for measurement wells
    
    Args:
        measurement_path: Path to measurement CSV.
        background_path: Path to background CSV.
        blank_wells: List of blank well identifiers.
        measurement_wells: List of measurement well identifiers.
        wavelength: The wavelength to process.
        
    Returns:
        Tuple of (list of absorbance values, blank average).
    """
    from .file_io import load_data_new
    
    # Load data
    df_measurement = load_data_new(measurement_path, 
                                    start_wavelength=wavelength,
                                    end_wavelength=wavelength)
    df_background = load_data_new(background_path,
                                   start_wavelength=wavelength,
                                   end_wavelength=wavelength)
    
    # Apply corrections
    log_msg("Subtracting plate background from measurement...")
    df_corrected = subtract_plate_background(df_measurement, df_background, wavelength)
    
    log_msg("Calculating blank average and subtracting from all wells...")
    blank_average, _ = calculate_blank_average(df_corrected, blank_wells, wavelength)
    log_msg(f"Blank average (background-corrected): {blank_average:.4f}")
    
    df_corrected = apply_corrections(df_corrected, blank_average, wavelength)
    log_msg("Background and blank corrections applied.")
    
    # Extract values for measurement wells
    absorbances = []
    for well_id in measurement_wells:
        abs_val = extract_well_absorbance(df_corrected, well_id, wavelength)
        if abs_val is not None:
            absorbances.append(abs_val)
        else:
            log_msg(f"WARNING: Well {well_id} not found in measurement data.")
            absorbances.append(0.0)
    
    return absorbances, blank_average
