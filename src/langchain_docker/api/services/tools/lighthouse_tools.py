"""Lighthouse CLI Tool Provider for efficient web performance analysis.

Uses Lighthouse CLI to get pre-computed performance metrics in a single call,
significantly reducing token usage compared to multiple Chrome DevTools calls.

Supports:
- Headless mode (default) for public pages
- Remote debugging mode for authenticated/internal pages
- Desktop and mobile device emulation
"""

import json
import logging
import subprocess
import shutil
from typing import Callable

from langchain_docker.api.services.tools.base import (
    ToolProvider,
    ToolTemplate,
    ToolParameter,
)

logger = logging.getLogger(__name__)

# Metric weights in Lighthouse performance score
METRIC_WEIGHTS = {
    "FCP": 10,   # First Contentful Paint
    "LCP": 25,   # Largest Contentful Paint
    "TBT": 30,   # Total Blocking Time
    "CLS": 25,   # Cumulative Layout Shift
    "SI": 10,    # Speed Index
}

# Metric thresholds (good, needs improvement)
METRIC_THRESHOLDS = {
    "FCP": {"good": 1.8, "poor": 3.0, "unit": "s"},
    "LCP": {"good": 2.5, "poor": 4.0, "unit": "s"},
    "TBT": {"good": 200, "poor": 600, "unit": "ms"},
    "CLS": {"good": 0.1, "poor": 0.25, "unit": ""},
    "SI": {"good": 3.4, "poor": 5.8, "unit": "s"},
    "TTFB": {"good": 0.8, "poor": 1.8, "unit": "s"},
}


class LighthouseToolProvider(ToolProvider):
    """Tool provider for Lighthouse-based performance analysis.

    Lighthouse provides comprehensive performance audits in a single CLI call,
    returning pre-computed metrics including:
    - Performance score (0-100) with weighted metrics
    - Core Web Vitals (LCP, CLS, FCP, TBT, Speed Index, TTFB)
    - Opportunities for optimization with estimated savings
    - Diagnostics and recommendations

    Supports two modes:
    1. Headless (default): For public pages, runs in background
    2. Remote debugging: For authenticated pages, connects to existing browser
       - Launch Chrome with: --remote-debugging-port=9222
       - Use port=9222 parameter to connect
    """

    def __init__(self, skill_registry=None):
        super().__init__(skill_registry)
        # Prefer globally installed lighthouse, fall back to npx
        self._lighthouse_path = shutil.which("lighthouse")
        self._use_npx = self._lighthouse_path is None
        if self._use_npx:
            self._npx_path = shutil.which("npx")
            logger.info("Lighthouse CLI not found globally, will use npx")

    def get_skill_id(self) -> str:
        return "web_performance"

    def get_templates(self) -> list[ToolTemplate]:
        return [
            ToolTemplate(
                id="lighthouse_audit",
                name="Lighthouse Performance Audit",
                description=(
                    "Run a comprehensive Lighthouse performance audit on a URL. "
                    "Returns performance score, Core Web Vitals with weights, "
                    "optimization opportunities, and diagnostics."
                ),
                category="performance",
                parameters=[
                    ToolParameter(
                        name="url",
                        type="string",
                        description="The URL to audit (must be a valid http/https URL)",
                        required=True,
                    ),
                    ToolParameter(
                        name="device",
                        type="string",
                        description="Device to emulate: 'mobile' (default) or 'desktop'",
                        required=False,
                        default="mobile",
                    ),
                    ToolParameter(
                        name="port",
                        type="integer",
                        description=(
                            "Remote debugging port to connect to existing browser (e.g., 9222). "
                            "Use for authenticated pages. Launch Chrome with --remote-debugging-port=9222 first."
                        ),
                        required=False,
                        default=None,
                    ),
                    ToolParameter(
                        name="preserve_auth",
                        type="boolean",
                        description=(
                            "Preserve authentication (cookies/localStorage) during audit. "
                            "Only works with port parameter. Default: True when port is set."
                        ),
                        required=False,
                        default=True,
                    ),
                ],
                factory=self._create_audit_tool,
            ),
            ToolTemplate(
                id="lighthouse_cwv",
                name="Lighthouse Core Web Vitals",
                description=(
                    "Get Core Web Vitals metrics (LCP, CLS, FCP, TBT, TTFB) for a URL "
                    "with pass/fail status and score weights."
                ),
                category="performance",
                parameters=[
                    ToolParameter(
                        name="url",
                        type="string",
                        description="The URL to analyze",
                        required=True,
                    ),
                    ToolParameter(
                        name="device",
                        type="string",
                        description="Device: 'mobile' (default) or 'desktop'",
                        required=False,
                        default="mobile",
                    ),
                    ToolParameter(
                        name="port",
                        type="integer",
                        description="Remote debugging port for authenticated pages",
                        required=False,
                        default=None,
                    ),
                ],
                factory=self._create_cwv_tool,
            ),
            ToolTemplate(
                id="lighthouse_opportunities",
                name="Lighthouse Optimization Opportunities",
                description=(
                    "Get prioritized list of performance optimization opportunities "
                    "organized by category (resources, network, third-party)."
                ),
                category="performance",
                parameters=[
                    ToolParameter(
                        name="url",
                        type="string",
                        description="The URL to analyze",
                        required=True,
                    ),
                    ToolParameter(
                        name="device",
                        type="string",
                        description="Device: 'mobile' (default) or 'desktop'",
                        required=False,
                        default="mobile",
                    ),
                    ToolParameter(
                        name="port",
                        type="integer",
                        description="Remote debugging port for authenticated pages",
                        required=False,
                        default=None,
                    ),
                ],
                factory=self._create_opportunities_tool,
            ),
            ToolTemplate(
                id="lighthouse_diagnostics",
                name="Lighthouse Diagnostics",
                description=(
                    "Get detailed diagnostics including DOM size, main thread work, "
                    "long tasks, and other performance insights."
                ),
                category="performance",
                parameters=[
                    ToolParameter(
                        name="url",
                        type="string",
                        description="The URL to analyze",
                        required=True,
                    ),
                    ToolParameter(
                        name="device",
                        type="string",
                        description="Device: 'mobile' (default) or 'desktop'",
                        required=False,
                        default="mobile",
                    ),
                    ToolParameter(
                        name="port",
                        type="integer",
                        description="Remote debugging port for authenticated pages",
                        required=False,
                        default=None,
                    ),
                ],
                factory=self._create_diagnostics_tool,
            ),
        ]

    def _check_lighthouse_installed(self) -> bool:
        """Check if Lighthouse CLI is available (globally or via npx)."""
        return self._lighthouse_path is not None or (self._use_npx and self._npx_path is not None)

    def _run_lighthouse(
        self,
        url: str,
        device: str = "mobile",
        port: int | None = None,
        preserve_auth: bool = True,
    ) -> dict:
        """Run Lighthouse audit and return parsed JSON results.

        Args:
            url: URL to audit
            device: 'mobile' or 'desktop'
            port: Remote debugging port (for authenticated pages)
            preserve_auth: Preserve cookies/localStorage (only with port)

        Returns:
            Parsed Lighthouse JSON report
        """
        if not self._check_lighthouse_installed():
            raise RuntimeError(
                "Lighthouse CLI not found. Install with: npm install -g lighthouse (or ensure npx is available)"
            )

        # Build base command
        if self._use_npx:
            cmd = [self._npx_path, "lighthouse", url]
        else:
            cmd = [self._lighthouse_path, url]

        # Add output format
        cmd.extend(["--output=json", "--quiet"])

        # Add device emulation
        if device == "desktop":
            cmd.append("--preset=desktop")

        # Handle browser connection mode
        if port:
            # Remote debugging mode - connect to existing browser
            cmd.append(f"--port={port}")
            if preserve_auth:
                cmd.append("--disable-storage-reset")
            logger.info(f"Connecting to existing browser on port {port}")
        else:
            # Headless mode - launch new browser
            cmd.append("--chrome-flags=--headless --no-sandbox --disable-gpu")

        # Performance only for faster audits
        cmd.append("--only-categories=performance")

        logger.info(f"Running Lighthouse audit for {url} ({device}, port={port})")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180,  # 3 minute timeout for complex pages
            )

            if result.returncode != 0:
                error_msg = result.stderr[:500] if result.stderr else "Unknown error"
                # Check for common errors
                if "connect ECONNREFUSED" in error_msg:
                    raise RuntimeError(
                        f"Cannot connect to browser on port {port}. "
                        "Launch Chrome with: --remote-debugging-port=9222"
                    )
                raise RuntimeError(f"Lighthouse failed: {error_msg}")

            return json.loads(result.stdout)

        except subprocess.TimeoutExpired:
            raise RuntimeError("Lighthouse audit timed out after 180 seconds")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse Lighthouse output: {e}")

    def _format_audit_summary(self, report: dict, device: str = "mobile") -> str:
        """Format Lighthouse report into a comprehensive summary."""
        categories = report.get("categories", {})
        audits = report.get("audits", {})

        # Performance score
        perf = categories.get("performance", {})
        perf_score = int((perf.get("score") or 0) * 100)

        # Determine score status
        if perf_score >= 90:
            score_status = "Good"
        elif perf_score >= 50:
            score_status = "Needs Improvement"
        else:
            score_status = "Poor"

        # Core metrics with weights
        metrics_data = {
            "FCP": {"audit": audits.get("first-contentful-paint", {}), "weight": 10},
            "LCP": {"audit": audits.get("largest-contentful-paint", {}), "weight": 25},
            "TBT": {"audit": audits.get("total-blocking-time", {}), "weight": 30},
            "CLS": {"audit": audits.get("cumulative-layout-shift", {}), "weight": 25},
            "Speed Index": {"audit": audits.get("speed-index", {}), "weight": 10},
        }

        # TTFB (informational, not weighted)
        ttfb = audits.get("server-response-time", {})

        lines = [
            f"## Lighthouse Performance Audit ({device.title()})",
            "",
            f"**Performance Score: {perf_score}/100** ({score_status})",
            "",
            "### Core Web Vitals",
            "",
            "| Metric | Value | Weight | Score | Status |",
            "|--------|-------|--------|-------|--------|",
        ]

        for name, data in metrics_data.items():
            audit = data["audit"]
            weight = data["weight"]
            if audit:
                value = audit.get("displayValue", "N/A")
                score = audit.get("score")
                if score is not None:
                    score_pct = int(score * 100)
                    if score >= 0.9:
                        status = "Good"
                    elif score >= 0.5:
                        status = "Needs Improvement"
                    else:
                        status = "Poor"
                else:
                    score_pct = "N/A"
                    status = "N/A"
                lines.append(f"| {name} | {value} | {weight}% | {score_pct}% | {status} |")

        # Add TTFB separately
        if ttfb:
            ttfb_value = ttfb.get("displayValue", "N/A")
            ttfb_score = ttfb.get("score")
            if ttfb_score is not None:
                if ttfb_score >= 0.9:
                    ttfb_status = "Good"
                elif ttfb_score >= 0.5:
                    ttfb_status = "Needs Improvement"
                else:
                    ttfb_status = "Poor"
            else:
                ttfb_status = "N/A"
            lines.append(f"| TTFB | {ttfb_value} | - | - | {ttfb_status} |")

        # Collect opportunities
        opportunities = self._collect_opportunities(audits)
        if opportunities:
            lines.extend([
                "",
                f"### Top Optimization Opportunities ({len(opportunities)} found)",
                "",
                "| Priority | Opportunity | Est. Savings |",
                "|----------|-------------|--------------|",
            ])
            for i, opp in enumerate(opportunities[:5], 1):
                savings = opp["savings"] / 1000
                lines.append(f"| {i} | {opp['title']} | {savings:.1f}s |")

        # Collect diagnostics
        diagnostics = self._collect_diagnostics(audits)
        if diagnostics:
            lines.extend([
                "",
                f"### Diagnostics ({len(diagnostics)} issues)",
                "",
            ])
            for diag in diagnostics[:5]:
                lines.append(f"- {diag['title']}")

        return "\n".join(lines)

    def _format_cwv_summary(self, report: dict, device: str = "mobile") -> str:
        """Format Core Web Vitals with detailed thresholds."""
        audits = report.get("audits", {})
        categories = report.get("categories", {})

        perf = categories.get("performance", {})
        perf_score = int((perf.get("score") or 0) * 100)

        cwv_data = {
            "FCP (First Contentful Paint)": {
                "audit": audits.get("first-contentful-paint", {}),
                "good": "< 1.8s",
                "poor": "> 3.0s",
                "weight": "10%",
            },
            "LCP (Largest Contentful Paint)": {
                "audit": audits.get("largest-contentful-paint", {}),
                "good": "< 2.5s",
                "poor": "> 4.0s",
                "weight": "25%",
            },
            "TBT (Total Blocking Time)": {
                "audit": audits.get("total-blocking-time", {}),
                "good": "< 200ms",
                "poor": "> 600ms",
                "weight": "30%",
            },
            "CLS (Cumulative Layout Shift)": {
                "audit": audits.get("cumulative-layout-shift", {}),
                "good": "< 0.1",
                "poor": "> 0.25",
                "weight": "25%",
            },
            "Speed Index": {
                "audit": audits.get("speed-index", {}),
                "good": "< 3.4s",
                "poor": "> 5.8s",
                "weight": "10%",
            },
            "TTFB (Time to First Byte)": {
                "audit": audits.get("server-response-time", {}),
                "good": "< 0.8s",
                "poor": "> 1.8s",
                "weight": "-",
            },
        }

        lines = [
            f"## Core Web Vitals Report ({device.title()})",
            "",
            f"**Overall Score: {perf_score}/100**",
            "",
            "| Metric | Value | Good | Poor | Weight | Status |",
            "|--------|-------|------|------|--------|--------|",
        ]

        pass_count = 0
        fail_count = 0

        for name, data in cwv_data.items():
            audit = data["audit"]
            if audit:
                value = audit.get("displayValue", "N/A")
                score = audit.get("score")

                if score is not None:
                    if score >= 0.9:
                        status = "Pass"
                        pass_count += 1
                    elif score >= 0.5:
                        status = "Warning"
                    else:
                        status = "Fail"
                        fail_count += 1
                else:
                    status = "N/A"

                lines.append(
                    f"| {name} | {value} | {data['good']} | {data['poor']} | {data['weight']} | {status} |"
                )

        # Summary
        lines.extend([
            "",
            "### Summary",
            f"- **Passing**: {pass_count} metrics",
            f"- **Failing**: {fail_count} metrics",
            "",
            "### Thresholds",
            "- **Good (Pass)**: Meets Google's recommended threshold",
            "- **Needs Improvement (Warning)**: Between good and poor",
            "- **Poor (Fail)**: Exceeds poor threshold, needs attention",
        ])

        return "\n".join(lines)

    def _collect_opportunities(self, audits: dict) -> list[dict]:
        """Collect and sort optimization opportunities."""
        opportunities = []
        for audit_id, audit in audits.items():
            details = audit.get("details", {})
            if details.get("type") == "opportunity":
                savings = details.get("overallSavingsMs", 0)
                if savings > 0:
                    opportunities.append({
                        "id": audit_id,
                        "title": audit.get("title", audit_id),
                        "savings": savings,
                        "description": audit.get("description", ""),
                        "category": self._categorize_opportunity(audit_id),
                    })

        opportunities.sort(key=lambda x: x["savings"], reverse=True)
        return opportunities

    def _categorize_opportunity(self, audit_id: str) -> str:
        """Categorize an opportunity by type."""
        resource_audits = {
            "render-blocking-resources", "unused-css-rules", "unused-javascript",
            "modern-image-formats", "uses-optimized-images", "uses-responsive-images",
            "offscreen-images", "unminified-css", "unminified-javascript",
            "efficient-animated-content",
        }
        network_audits = {
            "uses-rel-preconnect", "uses-rel-preload", "server-response-time",
            "redirects", "uses-text-compression", "uses-long-cache-ttl",
            "uses-http2",
        }
        third_party_audits = {
            "third-party-summary", "third-party-facades",
        }

        if audit_id in resource_audits:
            return "Resource Optimization"
        elif audit_id in network_audits:
            return "Network Optimization"
        elif audit_id in third_party_audits:
            return "Third-Party Optimization"
        return "Other"

    def _format_opportunities(self, report: dict, device: str = "mobile") -> str:
        """Format optimization opportunities by category."""
        audits = report.get("audits", {})
        opportunities = self._collect_opportunities(audits)

        if not opportunities:
            return "## Performance Optimization Opportunities\n\nNo significant opportunities found. The page is well-optimized!"

        # Group by category
        by_category: dict[str, list] = {}
        for opp in opportunities:
            cat = opp["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(opp)

        total_savings = sum(o["savings"] for o in opportunities) / 1000

        lines = [
            f"## Performance Optimization Opportunities ({device.title()})",
            "",
            f"**Total Potential Savings: {total_savings:.1f}s**",
            "",
        ]

        priority = 1
        for category in ["Resource Optimization", "Network Optimization", "Third-Party Optimization", "Other"]:
            if category not in by_category:
                continue

            cat_opps = by_category[category]
            cat_savings = sum(o["savings"] for o in cat_opps) / 1000

            lines.extend([
                f"### {category} ({cat_savings:.1f}s potential)",
                "",
                "| # | Opportunity | Savings | Description |",
                "|---|-------------|---------|-------------|",
            ])

            for opp in cat_opps:
                savings = opp["savings"] / 1000
                # Clean description
                desc = opp["description"][:60]
                desc = desc.replace("[", "").replace("]", "").replace("(", "").replace(")", "")
                if len(opp["description"]) > 60:
                    desc += "..."
                lines.append(f"| {priority} | {opp['title']} | {savings:.1f}s | {desc} |")
                priority += 1

            lines.append("")

        return "\n".join(lines)

    def _collect_diagnostics(self, audits: dict) -> list[dict]:
        """Collect diagnostic issues."""
        diagnostics = []

        # Key diagnostic audits to check
        diagnostic_ids = {
            "dom-size": "DOM Size",
            "bootup-time": "JavaScript Execution Time",
            "mainthread-work-breakdown": "Main Thread Work",
            "font-display": "Font Display",
            "third-party-summary": "Third-Party Code",
            "largest-contentful-paint-element": "LCP Element",
            "layout-shifts": "Layout Shifts",
            "long-tasks": "Long Tasks",
            "non-composited-animations": "Non-Composited Animations",
            "unsized-images": "Unsized Images",
            "uses-passive-event-listeners": "Passive Event Listeners",
            "no-document-write": "document.write()",
            "bf-cache": "Back/Forward Cache",
        }

        for audit_id, display_name in diagnostic_ids.items():
            audit = audits.get(audit_id, {})
            if audit:
                score = audit.get("score")
                if score is not None and score < 0.9:
                    diagnostics.append({
                        "id": audit_id,
                        "title": audit.get("title", display_name),
                        "description": audit.get("description", ""),
                        "score": score,
                        "displayValue": audit.get("displayValue", ""),
                    })

        # Sort by score (worst first)
        diagnostics.sort(key=lambda x: x["score"] if x["score"] is not None else 1)
        return diagnostics

    def _format_diagnostics(self, report: dict, device: str = "mobile") -> str:
        """Format detailed diagnostics."""
        audits = report.get("audits", {})
        diagnostics = self._collect_diagnostics(audits)

        lines = [
            f"## Performance Diagnostics ({device.title()})",
            "",
            "Diagnostics provide additional insights that don't directly affect the score.",
            "",
        ]

        if not diagnostics:
            lines.append("**All diagnostics passed!** No issues found.")
            return "\n".join(lines)

        lines.extend([
            f"**{len(diagnostics)} issues found**",
            "",
            "| Issue | Details | Score |",
            "|-------|---------|-------|",
        ])

        for diag in diagnostics:
            score_pct = int(diag["score"] * 100) if diag["score"] is not None else "N/A"
            details = diag["displayValue"] or "-"
            lines.append(f"| {diag['title']} | {details} | {score_pct}% |")

        # Add recommendations for common issues
        lines.extend([
            "",
            "### Common Fixes",
            "",
        ])

        fix_map = {
            "dom-size": "- **DOM Size**: Reduce DOM nodes (aim for < 800 nodes)",
            "bootup-time": "- **JS Execution**: Split code, defer non-critical JS",
            "mainthread-work-breakdown": "- **Main Thread**: Minimize JS, use web workers",
            "long-tasks": "- **Long Tasks**: Break up tasks > 50ms",
            "unsized-images": "- **Images**: Add width/height attributes to prevent layout shifts",
            "uses-passive-event-listeners": "- **Scroll Performance**: Use passive event listeners",
        }

        for diag in diagnostics[:5]:
            if diag["id"] in fix_map:
                lines.append(fix_map[diag["id"]])

        return "\n".join(lines)

    def _create_audit_tool(self) -> Callable:
        """Create the full audit tool."""
        def lighthouse_audit(
            url: str,
            device: str = "mobile",
            port: int | None = None,
            preserve_auth: bool = True,
        ) -> str:
            """Run comprehensive Lighthouse performance audit.

            Args:
                url: URL to audit
                device: 'mobile' or 'desktop'
                port: Remote debugging port for authenticated pages
                preserve_auth: Keep cookies/localStorage when using port
            """
            try:
                report = self._run_lighthouse(url, device, port, preserve_auth)
                return self._format_audit_summary(report, device)
            except Exception as e:
                logger.error(f"Lighthouse audit failed: {e}")
                return f"Error running Lighthouse audit: {e}"

        return lighthouse_audit

    def _create_cwv_tool(self) -> Callable:
        """Create the Core Web Vitals tool."""
        def lighthouse_cwv(
            url: str,
            device: str = "mobile",
            port: int | None = None,
        ) -> str:
            """Get Core Web Vitals metrics for a URL."""
            try:
                report = self._run_lighthouse(url, device, port)
                return self._format_cwv_summary(report, device)
            except Exception as e:
                logger.error(f"Lighthouse CWV check failed: {e}")
                return f"Error getting Core Web Vitals: {e}"

        return lighthouse_cwv

    def _create_opportunities_tool(self) -> Callable:
        """Create the opportunities tool."""
        def lighthouse_opportunities(
            url: str,
            device: str = "mobile",
            port: int | None = None,
        ) -> str:
            """Get prioritized optimization opportunities for a URL."""
            try:
                report = self._run_lighthouse(url, device, port)
                return self._format_opportunities(report, device)
            except Exception as e:
                logger.error(f"Lighthouse opportunities check failed: {e}")
                return f"Error getting opportunities: {e}"

        return lighthouse_opportunities

    def _create_diagnostics_tool(self) -> Callable:
        """Create the diagnostics tool."""
        def lighthouse_diagnostics(
            url: str,
            device: str = "mobile",
            port: int | None = None,
        ) -> str:
            """Get detailed performance diagnostics for a URL."""
            try:
                report = self._run_lighthouse(url, device, port)
                return self._format_diagnostics(report, device)
            except Exception as e:
                logger.error(f"Lighthouse diagnostics failed: {e}")
                return f"Error getting diagnostics: {e}"

        return lighthouse_diagnostics
