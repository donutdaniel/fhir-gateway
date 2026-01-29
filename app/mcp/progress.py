"""
Progress tracking utilities for MCP tools.

This module provides utilities for reporting progress during long-running
FHIR operations using MCP progress tokens.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.config.logging import get_logger

try:
    from mcp.server.fastmcp import Context
except ImportError:
    Context = None

logger = get_logger(__name__)


class ProgressTracker:
    """
    Helper class for tracking and reporting progress of operations.

    Usage:
        tracker = ProgressTracker(ctx, total_steps=5)
        await tracker.start("Beginning operation")
        await tracker.advance("Fetching patient data")
        await tracker.advance("Processing resources")
        await tracker.complete("Operation complete")
    """

    def __init__(
        self,
        ctx: "Context | None",
        total_steps: int = 100,
        operation_name: str = "operation",
    ):
        """
        Initialize progress tracker.

        Args:
            ctx: MCP context for reporting progress (may be None if not available)
            total_steps: Total number of steps in the operation
            operation_name: Name of the operation for logging
        """
        self.ctx = ctx
        self.total_steps = total_steps
        self.current_step = 0
        self.operation_name = operation_name

    async def report(self, message: str) -> None:
        """Report current progress with a message."""
        if self.ctx is not None:
            try:
                await self.ctx.report_progress(
                    progress=self.current_step,
                    total=self.total_steps,
                )
                logger.debug(
                    "Progress reported",
                    extra={
                        "operation": self.operation_name,
                        "current": self.current_step,
                        "total": self.total_steps,
                        "message": message,
                    },
                )
            except Exception as ex:
                # Progress reporting is best-effort, don't fail the operation
                logger.debug(
                    "Failed to report progress",
                    extra={"error": str(ex)},
                )

    async def start(self, message: str = "Starting") -> None:
        """Mark the start of an operation."""
        self.current_step = 0
        await self.report(message)

    async def advance(self, message: str = "Processing", steps: int = 1) -> None:
        """Advance progress by specified steps."""
        self.current_step = min(self.current_step + steps, self.total_steps)
        await self.report(message)

    async def complete(self, message: str = "Complete") -> None:
        """Mark the operation as complete."""
        self.current_step = self.total_steps
        await self.report(message)

    async def set_progress(self, current: int, message: str = "Processing") -> None:
        """Set progress to a specific value."""
        self.current_step = min(max(0, current), self.total_steps)
        await self.report(message)


@asynccontextmanager
async def track_progress(
    ctx: "Context | None",
    total_steps: int = 100,
    operation_name: str = "operation",
) -> AsyncGenerator[ProgressTracker, None]:
    """
    Context manager for tracking operation progress.

    Usage:
        async with track_progress(ctx, total_steps=5, operation_name="fetch_patient") as tracker:
            await tracker.start("Fetching patient")
            # ... do work
            await tracker.advance("Processing")
            # ... more work
            await tracker.complete("Done")

    Args:
        ctx: MCP context for reporting progress
        total_steps: Total number of steps
        operation_name: Name for logging

    Yields:
        ProgressTracker instance
    """
    tracker = ProgressTracker(ctx, total_steps, operation_name)
    try:
        yield tracker
    finally:
        # Ensure we report completion on exit
        if tracker.current_step < tracker.total_steps:
            await tracker.complete("Operation finished")
