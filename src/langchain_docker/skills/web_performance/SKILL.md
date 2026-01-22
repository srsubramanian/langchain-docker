---
id: web_performance
name: Web Performance Analysis
version: 1.0.0
category: performance
description: Analyze website performance including Core Web Vitals, caching, API latency, and provide optimization recommendations

tool_configs:
  - name: perf_analyze
    description: Get structured guidance for comprehensive performance analysis of a URL
    method: analyze_performance
    args:
      - name: url
        type: string
        required: true
        description: The URL to analyze
    requires_skill_loaded: true

  - name: perf_check_caching
    description: Get guidance for analyzing caching headers and strategies
    method: check_caching
    args:
      - name: url
        type: string
        required: true
        description: The URL to check caching for
    requires_skill_loaded: true

  - name: perf_analyze_api
    description: Get guidance for analyzing API/XHR performance
    method: analyze_api_calls
    args:
      - name: url
        type: string
        required: true
        description: The URL to analyze API calls for
    requires_skill_loaded: true

  - name: perf_recommendations
    description: Get optimization recommendations based on analysis
    method: get_recommendations
    args:
      - name: metrics
        type: string
        required: true
        description: JSON string or description of performance metrics
    requires_skill_loaded: true

resource_configs:
  - name: cwv_thresholds
    description: Core Web Vitals threshold reference
    content: |
      ## Core Web Vitals Thresholds (2024)
      | Metric | Good | Needs Improvement | Poor |
      |--------|------|-------------------|------|
      | LCP | <=2.5s | 2.5s-4.0s | >4.0s |
      | INP | <=200ms | 200ms-500ms | >500ms |
      | CLS | <=0.1 | 0.1-0.25 | >0.25 |
      | FCP | <=1.8s | 1.8s-3.0s | >3.0s |
      | TTFB | <=0.8s | 0.8s-1.8s | >1.8s |
---

# Web Performance Analysis Skill

This skill enables comprehensive website performance analysis using Chrome DevTools via MCP integration.

## Capabilities

1. **Core Web Vitals Analysis**: Measure LCP, INP, CLS, FCP, TTFB with guidance on thresholds
2. **Caching Analysis**: Check Cache-Control, ETag, Expires headers for static resources
3. **API Performance**: Analyze XHR/Fetch request timing, identify slow endpoints
4. **Resource Loading**: Identify render-blocking resources and optimization opportunities
5. **Optimization Recommendations**: Actionable improvement suggestions based on analysis

## MCP Server Requirements

This skill requires the **chrome-devtools** MCP server to be enabled. The MCP tools provide:
- `mcp__chrome-devtools__performance_start_trace` - Start performance recording
- `mcp__chrome-devtools__performance_stop_trace` - Stop and get results
- `mcp__chrome-devtools__performance_analyze_insight` - Detailed performance insights
- `mcp__chrome-devtools__list_network_requests` - Network request analysis
- `mcp__chrome-devtools__get_network_request` - Individual request details
- `mcp__chrome-devtools__navigate_page` - Page navigation
- `mcp__chrome-devtools__tabs_create_mcp` - Create new browser tab

## Workflow

### Basic Performance Analysis
1. Load this skill: `load_web_performance_skill`
2. Create a browser tab: `mcp__chrome-devtools__tabs_create_mcp`
3. Start performance trace: `mcp__chrome-devtools__performance_start_trace` with `reload: true, autoStop: true`
4. Navigate to URL: `mcp__chrome-devtools__navigate_page`
5. Analyze insights: `mcp__chrome-devtools__performance_analyze_insight`
6. Get recommendations: `perf_recommendations`

### Caching Analysis
1. Navigate to the target URL
2. List network requests: `mcp__chrome-devtools__list_network_requests`
3. Check headers for static resources using `mcp__chrome-devtools__get_network_request`
4. Use `perf_check_caching` for guidance on interpreting headers

### API Performance Analysis
1. Navigate and interact with the page
2. Filter network requests: `mcp__chrome-devtools__list_network_requests` with `resourceTypes: ["xhr", "fetch"]`
3. Analyze slow requests using `mcp__chrome-devtools__get_network_request`
4. Use `perf_analyze_api` for interpretation guidance

## Core Web Vitals Reference

| Metric | Description | Good | Poor |
|--------|-------------|------|------|
| **LCP** (Largest Contentful Paint) | Loading performance | <=2.5s | >4.0s |
| **INP** (Interaction to Next Paint) | Interactivity | <=200ms | >500ms |
| **CLS** (Cumulative Layout Shift) | Visual stability | <=0.1 | >0.25 |
| **FCP** (First Contentful Paint) | First render | <=1.8s | >3.0s |
| **TTFB** (Time to First Byte) | Server response | <=0.8s | >1.8s |

## Common Performance Issues

### Loading Issues
- Large uncompressed JavaScript bundles
- Render-blocking CSS in `<head>`
- No resource preloading for critical assets
- Missing lazy loading for below-fold images

### Caching Issues
- Missing Cache-Control headers
- Short TTL for static assets
- No ETag for conditional requests
- Missing compression (gzip/brotli)

### API Issues
- Sequential API calls that could be parallel
- Large JSON payloads without pagination
- Repeated auth/token refresh calls
- Missing response caching
