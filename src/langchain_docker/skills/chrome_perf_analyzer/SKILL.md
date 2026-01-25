---
name: chrome_perf_analyzer
description: Analyze Chrome DevTools Performance trace JSON files. Use when the user uploads a Chrome Performance trace (.json) and asks questions like "what network calls happened between X and Y", "what took the most time", "show me long tasks", "what was slow", or any query about timing, network requests, or performance bottlenecks in the trace.
category: performance
version: "1.0.0"
author: "system"

tool_configs:
  - name: trace_summary
    description: "Get a summary overview of a trace file including duration, event counts, and slowest requests"
    method: get_summary
    args:
      - name: filename
        type: string
        description: "Trace JSON filename in the working folder"
        required: true

  - name: trace_network
    description: "Get all network requests from a trace, sorted by start time"
    method: get_network_requests
    args:
      - name: filename
        type: string
        description: "Trace JSON filename in the working folder"
        required: true

  - name: trace_network_window
    description: "Get network requests within a specific time window"
    method: get_network_in_window
    args:
      - name: filename
        type: string
        description: "Trace JSON filename in the working folder"
        required: true
      - name: start_ms
        type: number
        description: "Start time in milliseconds (relative to trace start)"
        required: true
      - name: end_ms
        type: number
        description: "End time in milliseconds (relative to trace start)"
        required: true

  - name: trace_long_tasks
    description: "Find long tasks that blocked the main thread"
    method: get_long_tasks
    args:
      - name: filename
        type: string
        description: "Trace JSON filename in the working folder"
        required: true
      - name: threshold_ms
        type: number
        description: "Minimum task duration in ms (default: 50ms for Long Tasks)"
        required: false

  - name: trace_slowest
    description: "Get the N slowest events in the trace"
    method: get_slowest_events
    args:
      - name: filename
        type: string
        description: "Trace JSON filename in the working folder"
        required: true
      - name: count
        type: number
        description: "Number of slowest events to return (default: 10)"
        required: false
      - name: category
        type: string
        description: "Optional category filter (e.g., 'v8', 'blink', 'devtools.timeline')"
        required: false

  - name: trace_filter
    description: "Filter trace events by name, category, or time window"
    method: filter_events
    args:
      - name: filename
        type: string
        description: "Trace JSON filename in the working folder"
        required: true
      - name: name
        type: string
        description: "Filter by event name (partial match)"
        required: false
      - name: category
        type: string
        description: "Filter by category (partial match)"
        required: false
      - name: start_ms
        type: number
        description: "Filter by start time (ms)"
        required: false
      - name: end_ms
        type: number
        description: "Filter by end time (ms)"
        required: false

resource_configs:
  - name: trace_format
    description: "Chrome Trace Event Format reference"
    file: "references/trace_format.md"
---

# Chrome Performance Trace Analyzer

Analyze Chrome DevTools Performance trace JSON exports to answer questions about network requests, timing, and performance bottlenecks.

## Workflow

1. User uploads a Chrome Performance trace (.json) to the **Working Folder**
2. Use `trace_summary` to get an overview of the trace
3. Use specific tools to investigate:
   - `trace_network` - All network requests
   - `trace_network_window` - Network requests in a time range
   - `trace_long_tasks` - Main thread blocking tasks
   - `trace_slowest` - Slowest events overall
   - `trace_filter` - Custom filtering

## Common Questions

| User Question | Tool to Use |
|--------------|-------------|
| "What network calls happened between 2-5 seconds?" | `trace_network_window(start_ms=2000, end_ms=5000)` |
| "What took the most time?" | `trace_slowest(count=10)` |
| "Are there any long tasks?" | `trace_long_tasks(threshold_ms=50)` |
| "Show me JavaScript execution issues" | `trace_filter(category="v8")` |
| "What's in this trace?" | `trace_summary()` |

## Time Units

- All times are in **milliseconds relative to trace start**
- Use `trace_summary` to get total trace duration
- Network request times show when the request started and its duration

## Key Metrics to Look For

### Long Tasks (>50ms)
Tasks that block the main thread for more than 50ms cause jank and poor interactivity.

### Slow Network Requests
Requests taking >500ms may indicate:
- Server issues (high TTFB)
- Large payloads
- Missing caching

### Layout Thrashing
Frequent `Layout` events in a short window indicate forced synchronous layouts.

### JavaScript Execution
Look for long `v8.execute` or `FunctionCall` events.

## Reference

For trace event format details, load the `trace_format` resource.
