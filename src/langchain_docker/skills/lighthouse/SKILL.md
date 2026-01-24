---
id: lighthouse
name: Lighthouse Performance Analysis
version: 1.0.0
category: performance
description: Comprehensive Lighthouse CLI performance analysis - automated audits, Core Web Vitals, opportunities, and diagnostics

tool_configs:
  - name: lighthouse_audit
    description: Run comprehensive Lighthouse performance audit with Core Web Vitals, opportunities, and diagnostics
    method: lighthouse_audit
    args:
      - name: url
        type: string
        required: true
        description: The URL to audit
      - name: device
        type: string
        required: false
        description: Device emulation - 'mobile' (default) or 'desktop'
        default: mobile

  - name: lighthouse_cwv
    description: Get Core Web Vitals metrics with pass/fail status and score weights
    method: lighthouse_cwv
    args:
      - name: url
        type: string
        required: true
        description: The URL to analyze
      - name: device
        type: string
        required: false
        description: Device emulation - 'mobile' (default) or 'desktop'
        default: mobile

  - name: lighthouse_opportunities
    description: Get prioritized performance optimization opportunities with estimated savings
    method: lighthouse_opportunities
    args:
      - name: url
        type: string
        required: true
        description: The URL to analyze
      - name: device
        type: string
        required: false
        description: Device emulation - 'mobile' (default) or 'desktop'
        default: mobile

  - name: lighthouse_diagnostics
    description: Get detailed diagnostics including DOM size, main thread work, and long tasks
    method: lighthouse_diagnostics
    args:
      - name: url
        type: string
        required: true
        description: The URL to analyze
      - name: device
        type: string
        required: false
        description: Device emulation - 'mobile' (default) or 'desktop'
        default: mobile

resource_configs:
  - name: cwv_thresholds
    description: Core Web Vitals threshold reference (2024)

  - name: lighthouse_scoring
    description: Lighthouse performance score calculation weights

  - name: metric_explanations
    description: Detailed explanations of each performance metric
---

# Lighthouse Performance Analysis Skill

This skill provides **automated website performance analysis using Lighthouse CLI**. It focuses on pre-computed metrics, automated audits, and actionable recommendations.

## When to Use This Skill

| Use Case | This Skill (Lighthouse) | Web Performance Skill (DevTools) |
|----------|------------------------|----------------------------------|
| Quick performance audit | Yes | No |
| Core Web Vitals check | Yes | Yes (manual) |
| Automated CI/CD testing | Yes | No |
| Interactive debugging | No | Yes |
| Network request inspection | No | Yes |
| Live profiling | No | Yes |

## Quick Start

```
lighthouse_audit(url="https://example.com", device="mobile")
```

---

## Understanding Performance Scores

### Score Ranges

| Score Range | Status | Color | Meaning |
|-------------|--------|-------|---------|
| 90-100 | Good | Green | Excellent performance, minimal improvements needed |
| 50-89 | Needs Improvement | Orange | Noticeable issues affecting user experience |
| 0-49 | Poor | Red | Significant problems requiring immediate attention |

### How Lighthouse Calculates Performance Score

| Metric | Weight | Description |
|--------|--------|-------------|
| **Total Blocking Time (TBT)** | 30% | Time the main thread was blocked, preventing user input |
| **Largest Contentful Paint (LCP)** | 25% | When the largest content element becomes visible |
| **Cumulative Layout Shift (CLS)** | 25% | How much visible content shifts during page load |
| **First Contentful Paint (FCP)** | 10% | When first text or image is painted |
| **Speed Index (SI)** | 10% | How quickly content is visually displayed |

---

## Core Web Vitals Reference

### LCP (Largest Contentful Paint) - Loading

| Threshold | Value | What It Means |
|-----------|-------|---------------|
| Good | <= 2.5s | Users perceive the page as loading quickly |
| Needs Improvement | 2.5s - 4.0s | Loading feels sluggish, some users may leave |
| Poor | > 4.0s | Page appears broken or unresponsive |

### TBT (Total Blocking Time) - Interactivity

| Threshold | Value | What It Means |
|-----------|-------|---------------|
| Good | <= 200ms | Main thread rarely blocked |
| Needs Improvement | 200ms - 600ms | Some blocking affects responsiveness |
| Poor | > 600ms | Significant blocking, page feels frozen |

### CLS (Cumulative Layout Shift) - Visual Stability

| Threshold | Value | What It Means |
|-----------|-------|---------------|
| Good | <= 0.1 | Page is visually stable |
| Needs Improvement | 0.1 - 0.25 | Some content moves, may cause misclicks |
| Poor | > 0.25 | Significant jumping, frustrating experience |

### FCP (First Contentful Paint) - Initial Render

| Threshold | Value | What It Means |
|-----------|-------|---------------|
| Good | <= 1.8s | Page starts rendering quickly |
| Needs Improvement | 1.8s - 3.0s | Noticeable wait before content appears |
| Poor | > 3.0s | Page appears blank for too long |

### Speed Index - Visual Completeness

| Threshold | Value | What It Means |
|-----------|-------|---------------|
| Good | <= 3.4s | Content appears quickly and progressively |
| Needs Improvement | 3.4s - 5.8s | Visual loading feels slow |
| Poor | > 5.8s | Page takes too long to look complete |

---

## Tool Selection Guide

| Tool | Output | Best For |
|------|--------|----------|
| `lighthouse_audit` | Score, all metrics, opportunities, diagnostics | Complete analysis |
| `lighthouse_cwv` | LCP, TBT, CLS, FCP, SI with thresholds | Quick health check |
| `lighthouse_opportunities` | Prioritized list with time savings | Finding what to fix |
| `lighthouse_diagnostics` | DOM size, long tasks, render blocking | Deep investigation |

---

## Configuration

### Chrome Path (Optional)

| Platform | Environment Variable | Example Value |
|----------|---------------------|---------------|
| macOS | `LIGHTHOUSE_CHROME_PATH` | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` |
| Linux | `LIGHTHOUSE_CHROME_PATH` | `/usr/bin/chromium` |
| Windows | `LIGHTHOUSE_CHROME_PATH` | `C:\Program Files\Google\Chrome\Application\chrome.exe` |
