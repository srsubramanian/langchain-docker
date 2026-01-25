"""Chrome Performance Trace Analyzer Tool Provider.

Provides tools for analyzing Chrome DevTools Performance trace JSON files
from the session workspace.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from langchain_docker.api.services.tools.base import (
    ToolParameter,
    ToolProvider,
    ToolTemplate,
)

# Add skills directory to path for trace_analyzer import
# Path: tools/ -> services/ -> api/ -> langchain_docker/ -> skills/
SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "skills"
sys.path.insert(0, str(SKILLS_DIR / "chrome_perf_analyzer" / "scripts"))

from trace_analyzer import TraceAnalyzer

logger = logging.getLogger(__name__)


class ChromePerfToolProvider(ToolProvider):
    """Tool provider for Chrome Performance Trace analysis.

    Unlike other providers, this one needs access to the workspace service
    to read trace files from the session's working folder.
    """

    def __init__(
        self,
        skill_registry: Any,
        workspace_service: Any = None,
        session_id_getter: Callable[[], str] = None,
    ):
        """Initialize the Chrome Performance tool provider.

        Args:
            skill_registry: The SkillRegistry instance
            workspace_service: The WorkspaceService instance for file access
            session_id_getter: Callable that returns the current session ID
        """
        super().__init__(skill_registry)
        self._workspace_service = workspace_service
        self._get_session_id = session_id_getter

    def get_skill_id(self) -> str:
        return "chrome_perf_analyzer"

    def get_templates(self) -> list[ToolTemplate]:
        return [
            ToolTemplate(
                id="load_chrome_perf_skill",
                name="Load Chrome Performance Analyzer",
                description=(
                    "Load the Chrome Performance Trace Analyzer skill for analyzing "
                    "Chrome DevTools Performance trace JSON files. Use when user uploads "
                    "a trace and asks about network requests, timing, or performance."
                ),
                category="performance",
                parameters=[],
                factory=self._create_load_skill_tool,
            ),
            ToolTemplate(
                id="trace_summary",
                name="Trace Summary",
                description=(
                    "Get a summary overview of a Chrome Performance trace file including "
                    "duration, event counts, categories, and slowest network requests."
                ),
                category="performance",
                parameters=[
                    ToolParameter(
                        name="filename",
                        type="string",
                        description="Trace JSON filename in the working folder",
                        required=True,
                    ),
                ],
                factory=self._create_summary_tool,
            ),
            ToolTemplate(
                id="trace_network",
                name="Trace Network Requests",
                description="Get all network requests from a trace, sorted by start time.",
                category="performance",
                parameters=[
                    ToolParameter(
                        name="filename",
                        type="string",
                        description="Trace JSON filename in the working folder",
                        required=True,
                    ),
                ],
                factory=self._create_network_tool,
            ),
            ToolTemplate(
                id="trace_network_window",
                name="Trace Network Window",
                description=(
                    "Get network requests within a specific time window. "
                    "Times are in milliseconds relative to trace start."
                ),
                category="performance",
                parameters=[
                    ToolParameter(
                        name="filename",
                        type="string",
                        description="Trace JSON filename in the working folder",
                        required=True,
                    ),
                    ToolParameter(
                        name="start_ms",
                        type="number",
                        description="Start time in milliseconds (relative to trace start)",
                        required=True,
                    ),
                    ToolParameter(
                        name="end_ms",
                        type="number",
                        description="End time in milliseconds (relative to trace start)",
                        required=True,
                    ),
                ],
                factory=self._create_network_window_tool,
            ),
            ToolTemplate(
                id="trace_long_tasks",
                name="Trace Long Tasks",
                description=(
                    "Find long tasks that blocked the main thread. "
                    "Default threshold is 50ms (standard Long Tasks definition)."
                ),
                category="performance",
                parameters=[
                    ToolParameter(
                        name="filename",
                        type="string",
                        description="Trace JSON filename in the working folder",
                        required=True,
                    ),
                    ToolParameter(
                        name="threshold_ms",
                        type="number",
                        description="Minimum task duration in ms (default: 50)",
                        required=False,
                    ),
                ],
                factory=self._create_long_tasks_tool,
            ),
            ToolTemplate(
                id="trace_slowest",
                name="Trace Slowest Events",
                description="Get the N slowest events in the trace, optionally filtered by category.",
                category="performance",
                parameters=[
                    ToolParameter(
                        name="filename",
                        type="string",
                        description="Trace JSON filename in the working folder",
                        required=True,
                    ),
                    ToolParameter(
                        name="count",
                        type="number",
                        description="Number of slowest events to return (default: 10)",
                        required=False,
                    ),
                    ToolParameter(
                        name="category",
                        type="string",
                        description="Optional category filter (e.g., 'v8', 'blink', 'devtools.timeline')",
                        required=False,
                    ),
                ],
                factory=self._create_slowest_tool,
            ),
            ToolTemplate(
                id="trace_filter",
                name="Trace Filter Events",
                description="Filter trace events by name, category, or time window.",
                category="performance",
                parameters=[
                    ToolParameter(
                        name="filename",
                        type="string",
                        description="Trace JSON filename in the working folder",
                        required=True,
                    ),
                    ToolParameter(
                        name="name",
                        type="string",
                        description="Filter by event name (partial match)",
                        required=False,
                    ),
                    ToolParameter(
                        name="category",
                        type="string",
                        description="Filter by category (partial match)",
                        required=False,
                    ),
                    ToolParameter(
                        name="start_ms",
                        type="number",
                        description="Filter by start time (ms)",
                        required=False,
                    ),
                    ToolParameter(
                        name="end_ms",
                        type="number",
                        description="Filter by end time (ms)",
                        required=False,
                    ),
                ],
                factory=self._create_filter_tool,
            ),
        ]

    def _get_trace_path(self, filename: str) -> Optional[Path]:
        """Get the full path to a trace file in the workspace."""
        if not self._workspace_service or not self._get_session_id:
            return None

        session_id = self._get_session_id()
        if not session_id:
            return None

        return self._workspace_service.get_file_path(session_id, filename)

    def _create_load_skill_tool(self) -> Callable[[], str]:
        """Create the load skill tool."""
        skill = self.get_skill()

        def load_chrome_perf_skill() -> str:
            """Load the Chrome Performance Trace Analyzer skill with instructions and tool reference."""
            if skill:
                return skill.load_core()
            return "Chrome Performance Analyzer skill not available"

        return load_chrome_perf_skill

    def _create_summary_tool(self) -> Callable[[str], str]:
        """Create the trace summary tool."""
        provider = self

        def trace_summary(filename: str) -> str:
            """Get a summary of a Chrome Performance trace."""
            trace_path = provider._get_trace_path(filename)
            if not trace_path:
                return f"Error: File '{filename}' not found in working folder. Use workspace_list to see available files."

            try:
                analyzer = TraceAnalyzer(str(trace_path))
                summary = analyzer.summary()

                # Format the summary as markdown
                result = f"""## Trace Summary: {filename}

**Duration:** {summary['duration_ms']:.1f} ms ({summary['duration_ms']/1000:.2f} seconds)
**Total Events:** {summary['total_events']:,}
**Network Requests:** {summary['network_requests']}
**Long Tasks (>50ms):** {summary['long_tasks_count']}

### Top Categories
| Category | Event Count |
|----------|-------------|
"""
                for cat, count in sorted(summary['categories'].items(), key=lambda x: -x[1])[:10]:
                    result += f"| {cat} | {count:,} |\n"

                if summary['slowest_network']:
                    result += "\n### Slowest Network Requests\n"
                    result += "| Duration | URL |\n|----------|-----|\n"
                    for r in summary['slowest_network']:
                        dur = f"{r.get('duration_ms', 0):.1f}ms"
                        url = r.get('url', '')[:70]
                        result += f"| {dur} | {url} |\n"

                return result

            except Exception as e:
                logger.error(f"Error analyzing trace {filename}: {e}")
                return f"Error analyzing trace: {str(e)}"

        return trace_summary

    def _create_network_tool(self) -> Callable[[str], str]:
        """Create the network requests tool."""
        provider = self

        def trace_network(filename: str) -> str:
            """Get all network requests from a trace."""
            trace_path = provider._get_trace_path(filename)
            if not trace_path:
                return f"Error: File '{filename}' not found in working folder."

            try:
                analyzer = TraceAnalyzer(str(trace_path))
                requests = analyzer.get_network_requests()

                if not requests:
                    return "No network requests found in trace."

                # Sort by start time
                requests = sorted(requests, key=lambda x: x.get('start_ms', 0))

                result = f"## Network Requests ({len(requests)} total)\n\n"
                result += "| Start (ms) | Duration | Status | Size | URL |\n"
                result += "|------------|----------|--------|------|-----|\n"

                for r in requests[:50]:  # Limit to 50 for readability
                    start = f"{r.get('start_ms', 0):.1f}"
                    dur = f"{r.get('duration_ms', 0):.1f}ms" if r.get('duration_ms') else '-'
                    status = str(r.get('status', '-'))
                    size = f"{r.get('encoded_size', 0):,}" if r.get('encoded_size') else '-'
                    url = r.get('url', '')[:50]
                    result += f"| {start} | {dur} | {status} | {size} | {url} |\n"

                if len(requests) > 50:
                    result += f"\n*...and {len(requests) - 50} more requests*"

                return result

            except Exception as e:
                return f"Error analyzing trace: {str(e)}"

        return trace_network

    def _create_network_window_tool(self) -> Callable[[str, float, float], str]:
        """Create the network window tool."""
        provider = self

        def trace_network_window(filename: str, start_ms: float, end_ms: float) -> str:
            """Get network requests within a time window."""
            trace_path = provider._get_trace_path(filename)
            if not trace_path:
                return f"Error: File '{filename}' not found in working folder."

            try:
                analyzer = TraceAnalyzer(str(trace_path))
                requests = analyzer.get_network_in_window(start_ms, end_ms)

                if not requests:
                    return f"No network requests found between {start_ms}ms and {end_ms}ms."

                requests = sorted(requests, key=lambda x: x.get('start_ms', 0))

                result = f"## Network Requests: {start_ms}ms - {end_ms}ms ({len(requests)} found)\n\n"
                result += "| Start (ms) | Duration | Status | URL |\n"
                result += "|------------|----------|--------|-----|\n"

                for r in requests:
                    start = f"{r.get('start_ms', 0):.1f}"
                    dur = f"{r.get('duration_ms', 0):.1f}ms" if r.get('duration_ms') else '-'
                    status = str(r.get('status', '-'))
                    url = r.get('url', '')[:60]
                    result += f"| {start} | {dur} | {status} | {url} |\n"

                return result

            except Exception as e:
                return f"Error analyzing trace: {str(e)}"

        return trace_network_window

    def _create_long_tasks_tool(self) -> Callable[[str, Optional[float]], str]:
        """Create the long tasks tool."""
        provider = self

        def trace_long_tasks(filename: str, threshold_ms: Optional[float] = 50) -> str:
            """Find long tasks in the trace."""
            trace_path = provider._get_trace_path(filename)
            if not trace_path:
                return f"Error: File '{filename}' not found in working folder."

            threshold = threshold_ms or 50

            try:
                analyzer = TraceAnalyzer(str(trace_path))
                tasks = analyzer.get_long_tasks(threshold)

                if not tasks:
                    return f"No tasks longer than {threshold}ms found."

                result = f"## Long Tasks (>{threshold}ms): {len(tasks)} found\n\n"
                result += "| Time (ms) | Duration | Category | Name |\n"
                result += "|-----------|----------|----------|------|\n"

                for t in tasks[:30]:  # Limit for readability
                    ts = f"{analyzer.relative_ts(t):.1f}"
                    dur = f"{t.dur_ms:.1f}ms" if t.dur_ms else '-'
                    cat = t.cat[:20]
                    result += f"| {ts} | {dur} | {cat} | {t.name} |\n"

                if len(tasks) > 30:
                    result += f"\n*...and {len(tasks) - 30} more long tasks*"

                # Add summary statistics
                total_blocking = sum(t.dur_ms or 0 for t in tasks)
                result += f"\n\n**Total blocking time:** {total_blocking:.1f}ms"

                return result

            except Exception as e:
                return f"Error analyzing trace: {str(e)}"

        return trace_long_tasks

    def _create_slowest_tool(self) -> Callable[[str, Optional[int], Optional[str]], str]:
        """Create the slowest events tool."""
        provider = self

        def trace_slowest(
            filename: str,
            count: Optional[int] = 10,
            category: Optional[str] = None
        ) -> str:
            """Get the slowest events in the trace."""
            trace_path = provider._get_trace_path(filename)
            if not trace_path:
                return f"Error: File '{filename}' not found in working folder."

            n = count or 10

            try:
                analyzer = TraceAnalyzer(str(trace_path))
                events = analyzer.get_slowest_events(n, category)

                if not events:
                    cat_msg = f" in category '{category}'" if category else ""
                    return f"No events with duration found{cat_msg}."

                cat_msg = f" (category: {category})" if category else ""
                result = f"## {n} Slowest Events{cat_msg}\n\n"
                result += "| Time (ms) | Duration | Category | Name |\n"
                result += "|-----------|----------|----------|------|\n"

                for e in events:
                    ts = f"{analyzer.relative_ts(e):.1f}"
                    dur = f"{e.dur_ms:.1f}ms" if e.dur_ms else '-'
                    cat = e.cat[:20]
                    result += f"| {ts} | {dur} | {cat} | {e.name} |\n"

                return result

            except Exception as e:
                return f"Error analyzing trace: {str(e)}"

        return trace_slowest

    def _create_filter_tool(
        self
    ) -> Callable[[str, Optional[str], Optional[str], Optional[float], Optional[float]], str]:
        """Create the filter events tool."""
        provider = self

        def trace_filter(
            filename: str,
            name: Optional[str] = None,
            category: Optional[str] = None,
            start_ms: Optional[float] = None,
            end_ms: Optional[float] = None,
        ) -> str:
            """Filter trace events by various criteria."""
            trace_path = provider._get_trace_path(filename)
            if not trace_path:
                return f"Error: File '{filename}' not found in working folder."

            try:
                analyzer = TraceAnalyzer(str(trace_path))
                events = analyzer.events

                # Apply filters
                filters_applied = []

                if start_ms is not None and end_ms is not None:
                    events = analyzer.filter_by_time(start_ms, end_ms)
                    filters_applied.append(f"time: {start_ms}-{end_ms}ms")
                elif start_ms is not None:
                    events = analyzer.filter_by_time(start_ms, analyzer.duration_ms)
                    filters_applied.append(f"time: >{start_ms}ms")
                elif end_ms is not None:
                    events = analyzer.filter_by_time(0, end_ms)
                    filters_applied.append(f"time: <{end_ms}ms")

                if name:
                    events = [e for e in events if name.lower() in e.name.lower()]
                    filters_applied.append(f"name: '{name}'")

                if category:
                    events = [e for e in events if category.lower() in e.cat.lower()]
                    filters_applied.append(f"category: '{category}'")

                if not events:
                    return f"No events found matching filters: {', '.join(filters_applied)}"

                filter_str = ', '.join(filters_applied) if filters_applied else 'none'
                result = f"## Filtered Events ({len(events)} found)\n"
                result += f"**Filters:** {filter_str}\n\n"
                result += "| Time (ms) | Duration | Category | Name |\n"
                result += "|-----------|----------|----------|------|\n"

                for e in events[:50]:
                    ts = f"{analyzer.relative_ts(e):.1f}"
                    dur = f"{e.dur_ms:.1f}ms" if e.dur_ms else '-'
                    cat = e.cat[:20]
                    result += f"| {ts} | {dur} | {cat} | {e.name} |\n"

                if len(events) > 50:
                    result += f"\n*...and {len(events) - 50} more events*"

                return result

            except Exception as e:
                return f"Error analyzing trace: {str(e)}"

        return trace_filter
