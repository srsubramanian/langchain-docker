"""Human-in-the-Loop (HITL) tool wrapper.

This module provides a wrapper that intercepts tool execution and requires
human approval before proceeding. It integrates with LangGraph's interrupt
mechanism to pause agent execution while waiting for approval.
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from langchain_core.tools import BaseTool, StructuredTool

from langchain_docker.api.services.approval_service import (
    ApprovalConfig,
    ApprovalRequest,
    ApprovalService,
    ApprovalStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class HITLConfig:
    """Configuration for HITL behavior on a tool.

    Attributes:
        enabled: Whether HITL is enabled for this tool
        message: Message shown when requesting approval
        show_args: Whether to show tool arguments in approval UI
        timeout_seconds: Auto-reject after this many seconds (0 = no timeout)
        require_reason_on_reject: Whether rejection requires a reason
        impact_calculator: Optional function to calculate impact summary
    """

    enabled: bool = False
    message: str = "Approve this action?"
    show_args: bool = True
    timeout_seconds: int = 300
    require_reason_on_reject: bool = False
    impact_calculator: Optional[Callable[[dict[str, Any]], str]] = None

    def to_approval_config(self) -> ApprovalConfig:
        """Convert to ApprovalConfig."""
        return ApprovalConfig(
            message=self.message,
            show_args=self.show_args,
            timeout_seconds=self.timeout_seconds,
            require_reason_on_reject=self.require_reason_on_reject,
        )


class HITLToolWrapper:
    """Wrapper that adds HITL approval to tools.

    This wrapper intercepts tool execution and:
    1. Creates an approval request
    2. Sends an approval_request event via SSE
    3. Waits for human decision (blocking via LangGraph interrupt)
    4. Executes the tool if approved, or returns rejection message

    The wrapper integrates with LangGraph's interrupt/resume mechanism
    to properly pause and resume agent execution.
    """

    def __init__(
        self,
        approval_service: ApprovalService,
        on_approval_needed: Optional[Callable[[ApprovalRequest], None]] = None,
    ):
        """Initialize the HITL wrapper.

        Args:
            approval_service: Service for managing approval requests
            on_approval_needed: Callback when approval is needed (e.g., to send SSE)
        """
        self._approval_service = approval_service
        self._on_approval_needed = on_approval_needed

    def wrap_tool(
        self,
        tool: BaseTool,
        config: HITLConfig,
        session_id: str,
        thread_id: str,
    ) -> BaseTool:
        """Wrap a tool with HITL approval logic.

        Args:
            tool: The tool to wrap
            config: HITL configuration
            session_id: Current chat session ID
            thread_id: LangGraph thread ID for resuming

        Returns:
            Wrapped tool that requires approval before execution
        """
        if not config.enabled:
            return tool

        original_func = tool._run if hasattr(tool, "_run") else tool.func
        wrapper = self

        def hitl_wrapper(*args, **kwargs) -> str:
            """Wrapper function that intercepts tool execution."""
            # Build tool args for display
            tool_args = {}
            if args:
                tool_args["args"] = list(args)
            if kwargs:
                tool_args.update(kwargs)

            # Calculate impact summary if configured
            impact_summary = None
            if config.impact_calculator:
                try:
                    impact_summary = config.impact_calculator(tool_args)
                except Exception as e:
                    logger.warning(f"Impact calculator failed: {e}")

            # Create approval request
            # Note: tool_call_id should be set by the caller via thread-local or context
            tool_call_id = kwargs.pop("__tool_call_id__", "unknown")

            approval = wrapper._approval_service.create(
                tool_call_id=tool_call_id,
                session_id=session_id,
                thread_id=thread_id,
                tool_name=tool.name,
                tool_args=tool_args if config.show_args else {},
                config=config.to_approval_config(),
                impact_summary=impact_summary,
            )

            logger.info(
                f"HITL approval requested: {approval.id} for {tool.name} "
                f"in session {session_id}"
            )

            # Notify that approval is needed (e.g., send SSE event)
            if wrapper._on_approval_needed:
                wrapper._on_approval_needed(approval)

            # In synchronous context, we need to poll for approval
            # The actual blocking/interrupt happens at the LangGraph level
            # This wrapper just returns the approval ID for the interrupt handler

            return f"__HITL_PENDING__:{approval.id}"

        # Create wrapped tool
        wrapped_tool = StructuredTool(
            name=tool.name,
            description=tool.description + " [Requires approval]",
            func=hitl_wrapper,
            args_schema=tool.args_schema,
        )

        # Store reference to original for later execution
        wrapped_tool._original_tool = tool
        wrapped_tool._hitl_config = config

        return wrapped_tool


class HITLInterruptHandler:
    """Handler for HITL interrupts in LangGraph.

    This handler processes tool outputs that indicate HITL pending status,
    and manages the interrupt/resume flow.
    """

    def __init__(self, approval_service: ApprovalService):
        """Initialize the handler.

        Args:
            approval_service: Service for managing approval requests
        """
        self._approval_service = approval_service

    def is_hitl_pending(self, tool_output: str) -> bool:
        """Check if a tool output indicates HITL pending status.

        Args:
            tool_output: Output from tool execution

        Returns:
            True if the output indicates HITL pending
        """
        return isinstance(tool_output, str) and tool_output.startswith("__HITL_PENDING__:")

    def extract_approval_id(self, tool_output: str) -> Optional[str]:
        """Extract approval ID from HITL pending output.

        Args:
            tool_output: Output from tool execution

        Returns:
            Approval ID or None
        """
        if not self.is_hitl_pending(tool_output):
            return None
        return tool_output.split(":", 1)[1] if ":" in tool_output else None

    def get_approval_status(self, approval_id: str) -> Optional[ApprovalStatus]:
        """Get the current status of an approval request.

        Args:
            approval_id: The approval request ID

        Returns:
            Current status or None if not found
        """
        approval = self._approval_service.get(approval_id)
        return approval.status if approval else None

    def should_resume(self, approval_id: str) -> tuple[bool, Optional[str]]:
        """Check if an approval has been resolved and can resume.

        Args:
            approval_id: The approval request ID

        Returns:
            Tuple of (should_resume, rejection_reason)
            - (True, None) if approved
            - (True, reason) if rejected
            - (False, None) if still pending
        """
        approval = self._approval_service.get(approval_id)
        if not approval:
            return (True, "Approval request not found")

        if approval.status == ApprovalStatus.APPROVED:
            return (True, None)
        elif approval.status in (
            ApprovalStatus.REJECTED,
            ApprovalStatus.EXPIRED,
            ApprovalStatus.CANCELLED,
        ):
            reason = approval.rejection_reason or f"Action {approval.status.value}"
            return (True, reason)
        else:
            return (False, None)

    def execute_approved_tool(
        self,
        approval_id: str,
        original_tool: BaseTool,
        original_args: dict[str, Any],
    ) -> str:
        """Execute a tool that has been approved.

        Args:
            approval_id: The approval request ID
            original_tool: The original unwrapped tool
            original_args: The original arguments

        Returns:
            Tool execution result
        """
        approval = self._approval_service.get(approval_id)
        if not approval:
            return "Error: Approval request not found"

        if approval.status != ApprovalStatus.APPROVED:
            return f"Error: Action was not approved ({approval.status.value})"

        # Execute the original tool
        try:
            # Remove any HITL-specific keys
            args = {k: v for k, v in original_args.items() if not k.startswith("__")}
            result = original_tool.invoke(args)
            return result
        except Exception as e:
            logger.error(f"Error executing approved tool: {e}")
            return f"Error executing tool: {str(e)}"


def create_hitl_tool(
    tool: BaseTool,
    approval_service: ApprovalService,
    config: HITLConfig,
    session_id: str,
    thread_id: str,
    on_approval_needed: Optional[Callable[[ApprovalRequest], None]] = None,
) -> BaseTool:
    """Convenience function to create a HITL-wrapped tool.

    Args:
        tool: The tool to wrap
        approval_service: Service for managing approval requests
        config: HITL configuration
        session_id: Current chat session ID
        thread_id: LangGraph thread ID
        on_approval_needed: Callback when approval is needed

    Returns:
        Wrapped tool with HITL approval
    """
    wrapper = HITLToolWrapper(approval_service, on_approval_needed)
    return wrapper.wrap_tool(tool, config, session_id, thread_id)
