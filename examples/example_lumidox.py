"""
Example: Lumidox II LED Controller Experiments

This example demonstrates how to use the LumidoxInstrument for
programmatic LED illumination of multi-well plates, including:

1. Direct instrument control (fire / turn off)
2. Timed exposure experiment (single stage)
3. Multi-stage sweep experiment
4. Custom current sequence experiment
5. Using Lumidox alongside OT-2 and plate reader

Usage:
    python example_lumidox.py
"""

import os
import sys
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from project_unity import (
    LumidoxInstrument,
    LumidoxExposureExperiment,
    LumidoxMultiStageExperiment,
    LumidoxCustomSequenceExperiment,
    LumidoxConfig,
)


# =============================================================================
# Example 1: Direct Instrument Control
# =============================================================================

def example_direct_control():
    """
    Use the LumidoxInstrument directly without the experiment framework.

    Good for quick tests or when integrating into your own scripts.
    """
    print("\n" + "=" * 60)
    print("Example 1: Direct Instrument Control")
    print("=" * 60)

    # Auto-detect COM port (default behaviour)
    with LumidoxInstrument() as lumidox:
        # Print device info
        info = lumidox.get_device_info()
        print(f"  Model:       {info['model']}")
        print(f"  Serial:      {info['serial']}")
        print(f"  Firmware:    {info['firmware']}")
        print(f"  Wavelength:  {info['wavelength']}")
        print(f"  Max current: {info['max_current_ma']} mA")

        # Show all preset stages
        print("\n  Preset stages:")
        for stage in lumidox.get_all_stages():
            print(
                f"    Stage {stage['stage']}: {stage['current_ma']} mA  "
                f"({stage['total_power']} {stage['total_units']})"
            )

        # Fire stage 1 for 10 seconds
        print("\n  Firing stage 1 for 10 s ...")
        lumidox.fire_stage(1)
        time.sleep(15)
        lumidox.turn_off()
        print("  Done.")


# =============================================================================
# Example 2: Timed Exposure Experiment (preset stage)
# =============================================================================

def example_timed_exposure_stage():
    """
    Run a single-stage timed exposure using the experiment framework.

    The experiment records device info and exposure details in
    standardised metadata that is saved as JSON.
    """
    print("\n" + "=" * 60)
    print("Example 2: Timed Exposure – Preset Stage")
    print("=" * 60)

    with LumidoxInstrument() as lumidox:
        exp = LumidoxExposureExperiment(
            user_name="Lachlan",
            duration_seconds=120,       # 2 minutes
            stage=3,                    # preset stage 3
            lumidox=lumidox,
        )
        metadata = exp.run()

        print(f"\n  Experiment ID : {metadata.experiment_id}")
        print(f"  Status        : {metadata.status}")
        print(f"  Exposure      : {metadata.results_summary.get('exposure')}")
        print(f"  Metadata saved: {metadata.output_directory}")


# =============================================================================
# Example 3: Timed Exposure Experiment (custom current)
# =============================================================================

def example_timed_exposure_custom():
    """
    Same as Example 2 but with a user-specified current in mA.
    """
    print("\n" + "=" * 60)
    print("Example 3: Timed Exposure – Custom Current")
    print("=" * 60)

    with LumidoxInstrument() as lumidox:
        exp = LumidoxExposureExperiment(
            user_name="Lachlan",
            duration_seconds=60,
            current_ma=150,             # custom current
            lumidox=lumidox,
        )
        metadata = exp.run()

        print(f"\n  Experiment ID : {metadata.experiment_id}")
        print(f"  Status        : {metadata.status}")
        print(f"  Exposure      : {metadata.results_summary.get('exposure')}")


# =============================================================================
# Example 4: Multi-Stage Sweep
# =============================================================================

def example_multi_stage():
    """
    Cycle through all 5 preset stages, illuminating for 30 s each
    with a 5 s pause between stages.
    """
    print("\n" + "=" * 60)
    print("Example 4: Multi-Stage Sweep")
    print("=" * 60)

    with LumidoxInstrument() as lumidox:
        exp = LumidoxMultiStageExperiment(
            user_name="Lachlan",
            stages=[1, 2, 3, 4, 5],
            duration_per_stage=30,
            pause_between_stages=5,
            lumidox=lumidox,
        )
        metadata = exp.run()

        print(f"\n  Total stages run: {metadata.results_summary.get('total_stages')}")
        print(f"  Metadata saved  : {metadata.output_directory}")


# =============================================================================
# Example 5: Custom Current Sequence
# =============================================================================

def example_custom_sequence():
    """
    Define an arbitrary sequence of illumination steps, each with
    its own current and duration.
    """
    print("\n" + "=" * 60)
    print("Example 5: Custom Current Sequence")
    print("=" * 60)

    sequence = [
        {"current_ma": 50,  "duration_seconds": 15},
        {"current_ma": 100, "duration_seconds": 30},
        {"current_ma": 200, "duration_seconds": 60},
        {"current_ma": 100, "duration_seconds": 30},
        {"current_ma": 50,  "duration_seconds": 15},
    ]

    with LumidoxInstrument() as lumidox:
        exp = LumidoxCustomSequenceExperiment(
            user_name="Lachlan",
            sequence=sequence,
            pause_between_steps=5,
            lumidox=lumidox,
        )
        metadata = exp.run()

        print(f"\n  Total steps  : {metadata.results_summary.get('total_steps')}")
        print(f"  Metadata saved: {metadata.output_directory}")


# =============================================================================
# Example 6: Specify COM Port Manually
# =============================================================================

def example_manual_port():
    """
    If you know the exact COM port, pass it via LumidoxConfig.
    """
    print("\n" + "=" * 60)
    print("Example 6: Manual COM Port")
    print("=" * 60)

    config = LumidoxConfig(port="COM3", auto_detect=False)

    with LumidoxInstrument(config=config) as lumidox:
        info = lumidox.get_device_info()
        print(f"  Connected to {info['model']} on COM3")
        lumidox.timed_exposure(duration_seconds=10, stage=1)
        print("  Exposure complete.")


# =============================================================================
# Example 7: Lumidox + OT-2 Combined (Custom Experiment)
# =============================================================================

def example_combined_workflow_snippet():
    """
    Pseudo-code showing how Lumidox can be combined with the OT-2.

    This does not run as-is—it illustrates the pattern for building
    a custom experiment that mixes multiple instruments.
    """
    print("\n" + "=" * 60)
    print("Example 7: Combined Workflow (code snippet)")
    print("=" * 60)

    code = '''
    from project_unity import (
        BaseExperiment,
        OT2Instrument,
        LumidoxInstrument,
    )

    class PrepareAndIlluminate(BaseExperiment):
        EXPERIMENT_TYPE = "PrepareAndIlluminate"
        REQUIRED_INSTRUMENTS = ["ot2", "lumidox"]

        def __init__(self, user_name, protocol_path, stage, duration, **instruments):
            super().__init__(user_name=user_name, **instruments)
            self.protocol_path = protocol_path
            self.stage = stage
            self.duration = duration

        def setup(self):
            ot2 = self.instruments["ot2"]
            ot2.upload_protocol(self.protocol_path)

        def execute(self):
            ot2 = self.instruments["ot2"]
            lumidox = self.instruments["lumidox"]

            # Step 1: prepare samples on the OT-2
            ot2.run_protocol("prepare_plate.py")

            # Step 2: illuminate with Lumidox
            input("Move plate to Lumidox and press Enter...")
            lumidox.timed_exposure(self.duration, stage=self.stage)

    # Usage:
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
    '''
    print(code)


# =============================================================================
# Main Menu
# =============================================================================

if __name__ == "__main__":
    print("\nLumidox II LED Controller – Examples")
    print("=" * 60)
    print("1. Direct instrument control (fire stage 1 for 10 s)")
    print("2. Timed exposure experiment (preset stage)")
    print("3. Timed exposure experiment (custom current)")
    print("4. Multi-stage sweep (stages 1-5)")
    print("5. Custom current sequence")
    print("6. Manual COM port selection")
    print("7. Combined OT-2 + Lumidox workflow (code snippet)")
    print("=" * 60)

    choice = input("Select an example (1-7): ").strip()

    examples = {
        "1": example_direct_control,
        "2": example_timed_exposure_stage,
        "3": example_timed_exposure_custom,
        "4": example_multi_stage,
        "5": example_custom_sequence,
        "6": example_manual_port,
        "7": example_combined_workflow_snippet,
    }

    func = examples.get(choice)
    if func:
        func()
    else:
        print("Invalid choice.")
