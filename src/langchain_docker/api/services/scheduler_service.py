"""Scheduler service for automated agent execution."""

import logging
from datetime import datetime
from typing import Any, Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing scheduled agent executions using APScheduler."""

    def __init__(self):
        """Initialize the scheduler service."""
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._jobs: dict[str, dict[str, Any]] = {}  # agent_id -> job info
        self._execution_callback: Optional[Callable[[str, str], None]] = None
        self._started = False

    def start(self) -> None:
        """Start the scheduler."""
        if not self._started:
            self._scheduler.start()
            self._started = True
            logger.info("Scheduler service started")

    def shutdown(self) -> None:
        """Shutdown the scheduler."""
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False
            logger.info("Scheduler service stopped")

    def set_execution_callback(
        self, callback: Callable[[str, str], None]
    ) -> None:
        """Set the callback function for agent execution.

        Args:
            callback: Function that takes (agent_id, trigger_prompt) and executes the agent
        """
        self._execution_callback = callback

    def add_schedule(
        self,
        agent_id: str,
        cron_expression: str,
        trigger_prompt: str,
        timezone: str = "UTC",
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Add or update a schedule for an agent.

        Args:
            agent_id: The agent's unique ID
            cron_expression: Cron expression (5 parts: min hour day month weekday)
            trigger_prompt: The prompt to send when triggered
            timezone: Timezone for the schedule
            enabled: Whether the schedule is active

        Returns:
            Schedule info including next run time
        """
        # Remove existing job if any
        self.remove_schedule(agent_id)

        # Parse cron expression
        parts = cron_expression.strip().split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have 5 parts")

        minute, hour, day, month, day_of_week = parts

        # Create cron trigger
        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            timezone=timezone,
        )

        # Store job info
        self._jobs[agent_id] = {
            "cron_expression": cron_expression,
            "trigger_prompt": trigger_prompt,
            "timezone": timezone,
            "enabled": enabled,
            "job_id": None,
        }

        if enabled:
            # Add job to scheduler
            job = self._scheduler.add_job(
                self._execute_agent,
                trigger=trigger,
                args=[agent_id, trigger_prompt],
                id=f"agent_{agent_id}",
                replace_existing=True,
            )
            self._jobs[agent_id]["job_id"] = job.id
            next_run = job.next_run_time.isoformat() if job.next_run_time else None
        else:
            next_run = None

        logger.info(
            f"Schedule {'added' if enabled else 'configured (disabled)'} for agent {agent_id}: "
            f"{cron_expression} ({timezone})"
        )

        return {
            "agent_id": agent_id,
            "cron_expression": cron_expression,
            "trigger_prompt": trigger_prompt,
            "timezone": timezone,
            "enabled": enabled,
            "next_run": next_run,
        }

    def remove_schedule(self, agent_id: str) -> bool:
        """Remove a schedule for an agent.

        Args:
            agent_id: The agent's unique ID

        Returns:
            True if schedule was removed, False if not found
        """
        if agent_id not in self._jobs:
            return False

        job_info = self._jobs[agent_id]
        if job_info.get("job_id"):
            try:
                self._scheduler.remove_job(job_info["job_id"])
            except Exception:
                pass  # Job might not exist

        del self._jobs[agent_id]
        logger.info(f"Schedule removed for agent {agent_id}")
        return True

    def enable_schedule(self, agent_id: str) -> bool:
        """Enable a paused schedule.

        Args:
            agent_id: The agent's unique ID

        Returns:
            True if enabled, False if not found
        """
        if agent_id not in self._jobs:
            return False

        job_info = self._jobs[agent_id]
        if job_info["enabled"]:
            return True  # Already enabled

        # Re-add the job
        return self.add_schedule(
            agent_id=agent_id,
            cron_expression=job_info["cron_expression"],
            trigger_prompt=job_info["trigger_prompt"],
            timezone=job_info["timezone"],
            enabled=True,
        ) is not None

    def disable_schedule(self, agent_id: str) -> bool:
        """Disable (pause) a schedule without removing it.

        Args:
            agent_id: The agent's unique ID

        Returns:
            True if disabled, False if not found
        """
        if agent_id not in self._jobs:
            return False

        job_info = self._jobs[agent_id]
        if job_info.get("job_id"):
            try:
                self._scheduler.remove_job(job_info["job_id"])
            except Exception:
                pass

        job_info["enabled"] = False
        job_info["job_id"] = None
        logger.info(f"Schedule disabled for agent {agent_id}")
        return True

    def get_schedule(self, agent_id: str) -> Optional[dict[str, Any]]:
        """Get schedule info for an agent.

        Args:
            agent_id: The agent's unique ID

        Returns:
            Schedule info or None if not found
        """
        if agent_id not in self._jobs:
            return None

        job_info = self._jobs[agent_id].copy()

        # Get next run time if job is active
        if job_info.get("job_id"):
            job = self._scheduler.get_job(job_info["job_id"])
            if job and job.next_run_time:
                job_info["next_run"] = job.next_run_time.isoformat()
            else:
                job_info["next_run"] = None
        else:
            job_info["next_run"] = None

        return job_info

    def list_schedules(self) -> list[dict[str, Any]]:
        """List all schedules.

        Returns:
            List of schedule info dictionaries
        """
        result = []
        for agent_id in self._jobs:
            info = self.get_schedule(agent_id)
            if info:
                info["agent_id"] = agent_id
                result.append(info)
        return result

    def _execute_agent(self, agent_id: str, trigger_prompt: str) -> None:
        """Execute the agent with the trigger prompt.

        Args:
            agent_id: The agent's unique ID
            trigger_prompt: The prompt to send
        """
        logger.info(f"Executing scheduled agent {agent_id} with prompt: {trigger_prompt[:50]}...")

        if self._execution_callback:
            try:
                self._execution_callback(agent_id, trigger_prompt)
                logger.info(f"Scheduled execution completed for agent {agent_id}")
            except Exception as e:
                logger.error(f"Scheduled execution failed for agent {agent_id}: {e}")
        else:
            logger.warning(f"No execution callback set, skipping agent {agent_id}")

    def get_next_run_time(self, agent_id: str) -> Optional[str]:
        """Get the next scheduled run time for an agent.

        Args:
            agent_id: The agent's unique ID

        Returns:
            ISO format timestamp or None
        """
        info = self.get_schedule(agent_id)
        return info.get("next_run") if info else None
