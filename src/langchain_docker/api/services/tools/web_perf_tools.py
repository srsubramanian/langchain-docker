"""Web Performance tool provider for performance analysis using Chrome DevTools MCP.

This provider creates tools that guide agents through website performance analysis
workflows using the chrome-devtools MCP server integration.
"""

import logging
from typing import TYPE_CHECKING, Callable

from langchain_docker.api.services.tools.base import (
    ToolParameter,
    ToolProvider,
    ToolTemplate,
)

if TYPE_CHECKING:
    from langchain_docker.api.services.skill_registry import (
        SkillRegistry,
        WebPerformanceSkill,
    )

logger = logging.getLogger(__name__)


class WebPerformanceToolProvider(ToolProvider):
    """Tool provider for web performance analysis.

    Provides tools for:
    - Loading web performance skill (progressive disclosure)
    - Comprehensive performance analysis guidance
    - Caching analysis guidance
    - API performance analysis guidance
    - Optimization recommendations

    These tools work in conjunction with the chrome-devtools MCP server
    to provide browser-based performance profiling capabilities.
    """

    def get_skill_id(self) -> str:
        """Return the web performance skill ID."""
        return "web_performance"

    def get_templates(self) -> list[ToolTemplate]:
        """Return all web performance tool templates."""
        return [
            ToolTemplate(
                id="load_web_performance_skill",
                name="Load Web Performance Skill",
                description=(
                    "Load the web performance analysis skill with Core Web Vitals guidance, "
                    "MCP tool references, and analysis workflows. Call this before analyzing "
                    "website performance."
                ),
                category="performance",
                parameters=[],
                factory=self._create_load_skill_tool,
            ),
            ToolTemplate(
                id="perf_analyze",
                name="Analyze Performance",
                description=(
                    "Get a structured step-by-step plan for comprehensive performance analysis "
                    "of a URL using Chrome DevTools. Returns guidance on using MCP tools for "
                    "Core Web Vitals, network analysis, and performance tracing."
                ),
                category="performance",
                parameters=[
                    ToolParameter(
                        name="url",
                        type="string",
                        description="The URL to analyze",
                        required=True,
                    ),
                ],
                factory=self._create_analyze_tool,
            ),
            ToolTemplate(
                id="perf_check_caching",
                name="Check Caching",
                description=(
                    "Get guidance for analyzing HTTP caching headers and strategies. "
                    "Explains how to check Cache-Control, ETag, Expires headers and "
                    "identify caching issues for static resources."
                ),
                category="performance",
                parameters=[
                    ToolParameter(
                        name="url",
                        type="string",
                        description="The URL to check caching for",
                        required=True,
                    ),
                ],
                factory=self._create_caching_tool,
            ),
            ToolTemplate(
                id="perf_analyze_api",
                name="Analyze API Calls",
                description=(
                    "Get guidance for analyzing API/XHR performance including timing "
                    "breakdown, identifying slow endpoints, waterfall issues, and "
                    "auth bottlenecks."
                ),
                category="performance",
                parameters=[
                    ToolParameter(
                        name="url",
                        type="string",
                        description="The URL to analyze API calls for",
                        required=True,
                    ),
                ],
                factory=self._create_api_tool,
            ),
            ToolTemplate(
                id="perf_recommendations",
                name="Get Performance Recommendations",
                description=(
                    "Get optimization recommendations based on performance analysis. "
                    "Provides actionable suggestions for improving Core Web Vitals, "
                    "caching, API performance, and image optimization."
                ),
                category="performance",
                parameters=[
                    ToolParameter(
                        name="metrics",
                        type="string",
                        description="JSON string or description of performance metrics from analysis",
                        required=True,
                    ),
                ],
                factory=self._create_recommendations_tool,
            ),
            ToolTemplate(
                id="perf_cwv_thresholds",
                name="Core Web Vitals Thresholds",
                description=(
                    "Get the Core Web Vitals threshold reference table with explanations "
                    "for LCP, INP, CLS, FCP, and TTFB metrics."
                ),
                category="performance",
                parameters=[],
                factory=self._create_cwv_thresholds_tool,
            ),
            ToolTemplate(
                id="perf_caching_headers",
                name="Caching Headers Reference",
                description=(
                    "Get a reference guide for HTTP caching headers including Cache-Control "
                    "directives, ETag, and recommended values by resource type."
                ),
                category="performance",
                parameters=[],
                factory=self._create_caching_headers_tool,
            ),
        ]

    def _create_load_skill_tool(self) -> Callable[[], str]:
        """Create load web performance skill tool for progressive disclosure."""
        skill = self.get_skill()

        def load_web_performance_skill() -> str:
            """Load the web performance skill with analysis guidance and MCP tool references.

            Call this tool before analyzing website performance to get:
            - Core Web Vitals thresholds and explanations
            - MCP tool references for Chrome DevTools
            - Step-by-step analysis workflows
            - Common performance issues to look for

            Returns:
                Web performance analysis guidance and MCP tool references
            """
            return skill.load_core()

        return load_web_performance_skill

    def _create_analyze_tool(self) -> Callable[[str], str]:
        """Create comprehensive performance analysis tool."""
        skill = self.get_skill()

        def analyze_performance(url: str) -> str:
            """Get a structured plan for comprehensive performance analysis.

            Provides step-by-step guidance for using Chrome DevTools MCP tools
            to analyze Core Web Vitals, network waterfall, and performance traces.

            Args:
                url: The URL to analyze

            Returns:
                Detailed analysis plan with MCP tool commands
            """
            return skill.analyze_performance(url)

        return analyze_performance

    def _create_caching_tool(self) -> Callable[[str], str]:
        """Create caching analysis tool."""
        skill = self.get_skill()

        def check_caching(url: str) -> str:
            """Get guidance for analyzing caching headers and strategies.

            Explains how to use Chrome DevTools MCP tools to check:
            - Cache-Control headers
            - ETag and conditional requests
            - Content-Encoding (compression)
            - Resource-specific caching recommendations

            Args:
                url: The URL to check caching for

            Returns:
                Caching analysis guidance with header reference
            """
            return skill.check_caching(url)

        return check_caching

    def _create_api_tool(self) -> Callable[[str], str]:
        """Create API performance analysis tool."""
        skill = self.get_skill()

        def analyze_api_calls(url: str) -> str:
            """Get guidance for analyzing API/XHR performance.

            Explains how to use Chrome DevTools MCP tools to analyze:
            - API response times and timing breakdown
            - Request waterfall and parallelization opportunities
            - Authentication bottlenecks
            - Payload sizes and pagination needs

            Args:
                url: The URL to analyze API calls for

            Returns:
                API analysis guidance with timing references
            """
            return skill.analyze_api_calls(url)

        return analyze_api_calls

    def _create_recommendations_tool(self) -> Callable[[str], str]:
        """Create performance recommendations tool."""
        skill = self.get_skill()

        def get_recommendations(metrics: str) -> str:
            """Get optimization recommendations based on performance analysis.

            Provides actionable suggestions organized by impact:
            - Critical rendering path optimizations
            - Caching improvements
            - API optimization strategies
            - Image optimization techniques

            Args:
                metrics: JSON string or description of performance metrics

            Returns:
                Prioritized optimization recommendations
            """
            return skill.get_recommendations(metrics)

        return get_recommendations

    def _create_cwv_thresholds_tool(self) -> Callable[[], str]:
        """Create Core Web Vitals thresholds reference tool."""
        skill = self.get_skill()

        def get_cwv_thresholds() -> str:
            """Get Core Web Vitals threshold reference.

            Returns the 2024 thresholds for:
            - LCP (Largest Contentful Paint)
            - INP (Interaction to Next Paint)
            - CLS (Cumulative Layout Shift)
            - FCP (First Contentful Paint)
            - TTFB (Time to First Byte)

            Returns:
                Core Web Vitals thresholds table with explanations
            """
            return skill.load_details("cwv_thresholds")

        return get_cwv_thresholds

    def _create_caching_headers_tool(self) -> Callable[[], str]:
        """Create caching headers reference tool."""
        skill = self.get_skill()

        def get_caching_headers() -> str:
            """Get HTTP caching headers reference.

            Returns guidance on:
            - Cache-Control directives and their meanings
            - Recommended cache values by resource type
            - ETag and Last-Modified headers

            Returns:
                Caching headers reference guide
            """
            return skill.load_details("caching_headers")

        return get_caching_headers
