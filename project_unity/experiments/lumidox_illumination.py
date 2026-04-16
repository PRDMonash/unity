"""
Lumidox II illumination experiments.

Experiment templates for controlling LED illumination on
multi-well plates using the Lumidox II controller.
"""

import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..utils.logging import log_msg
from .base import BaseExperiment


class LumidoxExposureExperiment(BaseExperiment):
    """
    Simple timed LED exposure experiment.

    Illuminates a plate at a given power stage (or custom current) for a
    specified duration, then turns the LEDs off.

    Example:
        from project_unity.instruments import LumidoxInstrument
        from project_unity.experiments import LumidoxExposureExperiment

        with LumidoxInstrument() as lumidox:
            exp = LumidoxExposureExperiment(
                user_name="Lachlan",
                duration_seconds=120,
                stage=3,
                lumidox=lumidox,
            )
            metadata = exp.run()
    """

    EXPERIMENT_TYPE = "LumidoxExposure"
    REQUIRED_INSTRUMENTS = ["lumidox"]

    def __init__(
        self,
        user_name: str,
        duration_seconds: float = 60.0,
        stage: Optional[int] = None,
        current_ma: Optional[int] = None,
        experiment_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        **instruments,
    ):
        """
        Initialize timed exposure experiment.

        Exactly one of ``stage`` or ``current_ma`` must be provided.

        Args:
            user_name: Name of the user.
            duration_seconds: Illumination time in seconds.
            stage: Preset power stage (1-5).
            current_ma: Custom drive current in mA.
            experiment_name: Human-readable name.
            output_dir: Output directory for metadata.
            **instruments: Must include ``lumidox=LumidoxInstrument()``.
        """
        if stage is None and current_ma is None:
            stage = 1  # sensible default
        if stage is not None and current_ma is not None:
            raise ValueError("Provide only one of 'stage' or 'current_ma'")

        label = (
            f"Stage {stage}" if stage is not None
            else f"{current_ma} mA"
        )
        super().__init__(
            user_name=user_name,
            experiment_name=experiment_name or f"Lumidox Exposure ({label}, {duration_seconds}s)",
            output_dir=output_dir,
            **instruments,
        )

        self.duration_seconds = duration_seconds
        self.stage = stage
        self.current_ma = current_ma

        self.metadata.add_parameter("duration_seconds", duration_seconds)
        self.metadata.add_parameter("stage", stage)
        self.metadata.add_parameter("current_ma", current_ma)

    def setup(self) -> None:
        """Log device info and record parameters."""
        lumidox = self.instruments["lumidox"]
        info = lumidox.get_device_info()
        self.metadata.add_parameter("device_info", info)
        self.log_event("setup", "Device info recorded", info)

    def execute(self) -> None:
        """Run the timed illumination."""
        lumidox = self.instruments["lumidox"]
        result = lumidox.timed_exposure(
            duration_seconds=self.duration_seconds,
            stage=self.stage,
            current_ma=self.current_ma,
        )
        self.metadata.add_result("exposure", result)
        self.log_event("illumination", "Exposure completed", result)


class LumidoxMultiStageExperiment(BaseExperiment):
    """
    Cycle through multiple illumination stages with configurable durations.

    Useful for dose-response or multi-intensity experiments where the
    plate is illuminated at several power levels in sequence.

    Example:
        from project_unity.instruments import LumidoxInstrument
        from project_unity.experiments import LumidoxMultiStageExperiment

        with LumidoxInstrument() as lumidox:
            exp = LumidoxMultiStageExperiment(
                user_name="Lachlan",
                stages=[1, 2, 3, 4, 5],
                duration_per_stage=60,
                lumidox=lumidox,
            )
            metadata = exp.run()
    """

    EXPERIMENT_TYPE = "LumidoxMultiStage"
    REQUIRED_INSTRUMENTS = ["lumidox"]

    def __init__(
        self,
        user_name: str,
        stages: Optional[List[int]] = None,
        duration_per_stage: float = 60.0,
        pause_between_stages: float = 0.0,
        experiment_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        **instruments,
    ):
        """
        Initialize multi-stage experiment.

        Args:
            user_name: Name of the user.
            stages: List of stage numbers (1-5) to cycle through.
                    Defaults to ``[1, 2, 3, 4, 5]``.
            duration_per_stage: Seconds to illuminate at each stage.
            pause_between_stages: Seconds to wait (LEDs off) between stages.
            experiment_name: Human-readable name.
            output_dir: Output directory for metadata.
            **instruments: Must include ``lumidox=LumidoxInstrument()``.
        """
        stages = stages or [1, 2, 3, 4, 5]

        super().__init__(
            user_name=user_name,
            experiment_name=experiment_name or f"Lumidox Multi-Stage ({len(stages)} stages)",
            output_dir=output_dir,
            **instruments,
        )

        self.stages = stages
        self.duration_per_stage = duration_per_stage
        self.pause_between_stages = pause_between_stages
        self.results: List[Dict[str, Any]] = []

        self.metadata.add_parameter("stages", stages)
        self.metadata.add_parameter("duration_per_stage", duration_per_stage)
        self.metadata.add_parameter("pause_between_stages", pause_between_stages)

    def setup(self) -> None:
        """Log device info and stage details."""
        lumidox = self.instruments["lumidox"]
        info = lumidox.get_device_info()
        self.metadata.add_parameter("device_info", info)

        stage_details = [lumidox.get_stage_info(s) for s in self.stages]
        self.metadata.add_parameter("stage_details", stage_details)
        self.log_event("setup", "Device and stage info recorded")

    def execute(self) -> None:
        """Cycle through each stage, illuminating for the configured duration."""
        lumidox = self.instruments["lumidox"]

        for i, stage in enumerate(self.stages):
            step = i + 1
            log_msg(f"\nStep {step}/{len(self.stages)}: Stage {stage}")

            start = datetime.now()
            result = lumidox.timed_exposure(
                duration_seconds=self.duration_per_stage,
                stage=stage,
            )
            result["step"] = step
            result["timestamp"] = start.isoformat()
            self.results.append(result)

            self.log_event(
                "illumination",
                f"Stage {stage} completed ({self.duration_per_stage}s)",
                result,
            )

            # Pause between stages (except after last)
            if self.pause_between_stages > 0 and step < len(self.stages):
                log_msg(f"Pausing {self.pause_between_stages}s before next stage...")
                time.sleep(self.pause_between_stages)

        self.metadata.add_result("exposures", self.results)
        self.metadata.add_result("total_stages", len(self.results))


class LumidoxCustomSequenceExperiment(BaseExperiment):
    """
    Execute an arbitrary sequence of illumination steps defined by
    a list of ``(current_ma, duration_seconds)`` tuples.

    Example:
        from project_unity.instruments import LumidoxInstrument
        from project_unity.experiments import LumidoxCustomSequenceExperiment

        sequence = [
            {"current_ma": 100, "duration_seconds": 30},
            {"current_ma": 200, "duration_seconds": 60},
            {"current_ma": 50,  "duration_seconds": 45},
        ]

        with LumidoxInstrument() as lumidox:
            exp = LumidoxCustomSequenceExperiment(
                user_name="Lachlan",
                sequence=sequence,
                lumidox=lumidox,
            )
            metadata = exp.run()
    """

    EXPERIMENT_TYPE = "LumidoxCustomSequence"
    REQUIRED_INSTRUMENTS = ["lumidox"]

    def __init__(
        self,
        user_name: str,
        sequence: List[Dict[str, Any]],
        pause_between_steps: float = 0.0,
        experiment_name: Optional[str] = None,
        output_dir: Optional[str] = None,
        **instruments,
    ):
        """
        Initialize custom sequence experiment.

        Args:
            user_name: Name of the user.
            sequence: List of dicts, each with either ``stage`` or
                      ``current_ma`` and ``duration_seconds``.
            pause_between_steps: Seconds to wait (LEDs off) between steps.
            experiment_name: Human-readable name.
            output_dir: Output directory.
            **instruments: Must include ``lumidox=LumidoxInstrument()``.
        """
        super().__init__(
            user_name=user_name,
            experiment_name=experiment_name or f"Lumidox Custom Sequence ({len(sequence)} steps)",
            output_dir=output_dir,
            **instruments,
        )

        self.sequence = sequence
        self.pause_between_steps = pause_between_steps
        self.results: List[Dict[str, Any]] = []

        self.metadata.add_parameter("sequence", sequence)
        self.metadata.add_parameter("pause_between_steps", pause_between_steps)

    def setup(self) -> None:
        """Record device info."""
        lumidox = self.instruments["lumidox"]
        info = lumidox.get_device_info()
        self.metadata.add_parameter("device_info", info)
        self.log_event("setup", "Device info recorded", info)

    def execute(self) -> None:
        """Run each step in the sequence."""
        lumidox = self.instruments["lumidox"]

        for i, step_def in enumerate(self.sequence):
            step_num = i + 1
            duration = step_def["duration_seconds"]
            stage = step_def.get("stage")
            current = step_def.get("current_ma")

            label = f"stage {stage}" if stage is not None else f"{current} mA"
            log_msg(f"\nStep {step_num}/{len(self.sequence)}: {label} for {duration}s")

            start = datetime.now()
            result = lumidox.timed_exposure(
                duration_seconds=duration,
                stage=stage,
                current_ma=current,
            )
            result["step"] = step_num
            result["timestamp"] = start.isoformat()
            self.results.append(result)

            self.log_event(
                "illumination",
                f"Step {step_num} completed ({label}, {duration}s)",
                result,
            )

            if self.pause_between_steps > 0 and step_num < len(self.sequence):
                log_msg(f"Pausing {self.pause_between_steps}s...")
                time.sleep(self.pause_between_steps)

        self.metadata.add_result("exposures", self.results)
        self.metadata.add_result("total_steps", len(self.results))
