# Lighthouse CLI Guide

A comprehensive guide to using Lighthouse CLI for performance analysis.

---

## Table of Contents

1. [Using Lighthouse with Existing Browser](#using-lighthouse-with-existing-browser)
2. [Performance Metrics](#performance-metrics)
3. [Opportunities](#opportunities)
4. [Diagnostics](#diagnostics)
5. [Additional Audits](#additional-audits)
6. [CLI Commands Reference](#cli-commands-reference)
7. [Extracting Key Metrics](#extracting-key-metrics)

---

## Using Lighthouse with Existing Browser

Use Lighthouse to audit pages in a browser you control - useful for authenticated pages, internal apps, or complex navigation flows.

## Step 1: Launch Chrome with Remote Debugging

### Mac
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

### Windows
```bash
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

### Linux
```bash
google-chrome --remote-debugging-port=9222
```

## Step 2: Navigate Manually

1. Browser opens with debugging enabled
2. Log in to your app
3. Navigate to the page you want to audit
4. Complete any setup needed (accept cookies, dismiss modals, etc.)

## Step 3: Run Lighthouse

### Basic HTML Report
```bash
lighthouse https://your-app.com/page \
  --port=9222 \
  --output html \
  --output-path report.html
```

### Authenticated Pages (Preserve Session)
```bash
lighthouse https://your-app.com/dashboard \
  --port=9222 \
  --disable-storage-reset \
  --output html \
  --output-path report.html \
  --preset desktop
```

### Performance Only (Faster)
```bash
lighthouse https://your-app.com/page \
  --port=9222 \
  --disable-storage-reset \
  --only-categories=performance \
  --output html \
  --output-path report.html
```

### HTML + JSON Output
```bash
lighthouse https://your-app.com/page \
  --port=9222 \
  --disable-storage-reset \
  --output html \
  --output json \
  --output-path ./report
```
This creates `report.html` and `report.json`.

## Key Flags Reference

| Flag | Purpose |
|------|---------|
| `--port=9222` | Connect to existing Chrome instance |
| `--disable-storage-reset` | Preserve cookies/localStorage (keeps you logged in) |
| `--preset desktop` | Desktop viewport (default is mobile) |
| `--only-categories=performance` | Run only performance audit |
| `--output html` | Generate HTML report |
| `--output json` | Generate JSON report |
| `--output-path ./report` | Output file path |
| `--chrome-flags="--headless"` | Headless mode (not for existing browser) |

## Notes

- Lighthouse will **reload the page** to run its audit
- Use `--disable-storage-reset` to stay logged in after reload
- The debugging port (9222) must match between Chrome launch and Lighthouse command
- Close other Chrome instances before launching with debugging, or use a different port

---

## Performance Metrics

These core metrics contribute to your Lighthouse Performance score:

| Metric | Weight | What It Measures |
|--------|--------|------------------|
| **First Contentful Paint (FCP)** | 10% | Time until first text/image renders |
| **Largest Contentful Paint (LCP)** | 25% | Time until largest content element renders |
| **Total Blocking Time (TBT)** | 30% | Sum of blocking time between FCP and TTI |
| **Cumulative Layout Shift (CLS)** | 25% | Visual stability (unexpected layout shifts) |
| **Speed Index** | 10% | How quickly content visually populates |

### Metric Thresholds

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| FCP | < 1.8s | 1.8s - 3s | > 3s |
| LCP | < 2.5s | 2.5s - 4s | > 4s |
| TBT | < 200ms | 200ms - 600ms | > 600ms |
| CLS | < 0.1 | 0.1 - 0.25 | > 0.25 |
| Speed Index | < 3.4s | 3.4s - 5.8s | > 5.8s |

---

## Opportunities

Actionable recommendations to improve load performance.

### Resource Optimization

| Audit | Description |
|-------|-------------|
| Eliminate render-blocking resources | Remove or defer CSS/JS that blocks rendering |
| Defer offscreen images | Lazy load images not in viewport |
| Properly size images | Serve images at correct dimensions |
| Serve images in modern formats | Use WebP, AVIF instead of JPEG/PNG |
| Efficiently encode images | Optimize image compression |
| Minify CSS | Remove unnecessary characters from CSS |
| Minify JavaScript | Remove unnecessary characters from JS |
| Remove unused CSS | Eliminate CSS rules not used on page |
| Remove unused JavaScript | Eliminate JS code not executed |
| Enable text compression | Use Gzip/Brotli for text resources |

### Network Optimization

| Audit | Description |
|-------|-------------|
| Preconnect to required origins | Establish early connections to third-party domains |
| Preload key requests | Prioritize critical resources |
| Reduce server response times (TTFB) | Optimize server/backend response |
| Avoid multiple page redirects | Minimize redirect chains |
| Use video formats for animated content | Replace GIFs with WebM/MP4 |
| Serve static assets with efficient cache policy | Configure proper cache headers |

### Third-Party Optimization

| Audit | Description |
|-------|-------------|
| Reduce impact of third-party code | Minimize third-party script impact |
| Lazy load third-party resources with facades | Defer third-party loading |

---

## Diagnostics

Additional insights that don't directly affect the score but indicate potential issues.

### DOM & Rendering

| Audit | Description |
|-------|-------------|
| Avoid excessive DOM size | Keep DOM nodes under 1,400 (warning at 800) |
| Avoid non-composited animations | Use GPU-accelerated animations |
| Avoid large layout shifts | Prevent unexpected content movement |
| Minimize main-thread work | Reduce JS execution on main thread |
| Reduce JavaScript execution time | Optimize JS performance |

### Network Analysis

| Audit | Description |
|-------|-------------|
| Avoid enormous network payloads | Keep total transfer size low |
| Avoid chaining critical requests | Minimize request dependency chains |
| Keep request counts low | Reduce number of network requests |
| Largest Contentful Paint element | Identifies the LCP element |
| Long tasks | Tasks blocking main thread > 50ms |

### Caching & Protocol

| Audit | Description |
|-------|-------------|
| Serve static assets with efficient cache policy | Proper cache-control headers |
| Uses HTTP/2 | Modern protocol for multiplexing |

### User Experience

| Audit | Description |
|-------|-------------|
| Page didn't prevent back/forward cache restoration | BFCache compatibility |
| Avoids document.write() | Deprecated blocking method |
| Uses passive listeners for scroll performance | Non-blocking scroll handlers |
| Avoids unload event handlers | BFCache-blocking handlers |

---

## Additional Audits

### Informational Audits

- Network RTT analysis
- Server backend latencies
- Screenshot timeline thumbnails
- Main thread work breakdown
- Network request waterfall
- Critical request chains
- User Timing marks and measures

---

## CLI Commands Reference

### Basic Commands

```bash
# Full audit with HTML report
lighthouse https://example.com --output html --output-path report.html

# Performance only (faster)
lighthouse https://example.com --only-categories=performance --output html --output-path report.html

# Desktop mode
lighthouse https://example.com --preset desktop --output html --output-path report.html

# Headless (no browser window)
lighthouse https://example.com --chrome-flags="--headless" --output html --output-path report.html
```

### Targeting Specific Audits

```bash
# Run only specific audits
lighthouse https://example.com \
  --only-audits=first-contentful-paint,largest-contentful-paint,total-blocking-time

# Skip specific audits
lighthouse https://example.com --skip-audits=screenshot-thumbnails

# List all available audits
lighthouse --list-all-audits
```

### Multiple Output Formats

```bash
# HTML + JSON
lighthouse https://example.com --output html --output json --output-path ./report

# JSON only (for programmatic use)
lighthouse https://example.com --output json --output-path report.json
```

### With Existing Browser (Authenticated Pages)

```bash
# Step 1: Launch Chrome with debugging
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Step 2: Navigate and log in manually

# Step 3: Run Lighthouse
lighthouse https://your-app.com/dashboard \
  --port=9222 \
  --disable-storage-reset \
  --output html \
  --output-path report.html \
  --preset desktop
```

---

## Extracting Key Metrics

### Using jq for JSON Processing

```bash
# Basic metrics extraction
cat report.json | jq '{
  score: .categories.performance.score,
  lcp: .audits["largest-contentful-paint"].numericValue,
  fcp: .audits["first-contentful-paint"].numericValue,
  tbt: .audits["total-blocking-time"].numericValue,
  cls: .audits["cumulative-layout-shift"].numericValue,
  ttfb: .audits["server-response-time"].numericValue
}'
```

### Extended Extraction with Opportunities

```bash
cat report.json | jq '{
  score: .categories.performance.score,
  metrics: {
    lcp: .audits["largest-contentful-paint"].numericValue,
    fcp: .audits["first-contentful-paint"].numericValue,
    tbt: .audits["total-blocking-time"].numericValue,
    cls: .audits["cumulative-layout-shift"].numericValue,
    si: .audits["speed-index"].numericValue,
    ttfb: .audits["server-response-time"].numericValue
  },
  opportunities: [
    .audits | to_entries[] |
    select(.value.details.overallSavingsMs > 100) |
    {id: .key, savings_ms: .value.details.overallSavingsMs}
  ],
  diagnostics: [
    .audits | to_entries[] |
    select(.value.score != null and .value.score < 0.9 and .value.scoreDisplayMode == "numeric") |
    {id: .key, score: .value.score}
  ]
}'
```

---

## Key Flags Reference

| Flag | Purpose |
|------|---------|
| `--port=9222` | Connect to existing Chrome instance |
| `--disable-storage-reset` | Preserve cookies/localStorage |
| `--preset desktop` | Desktop viewport (default is mobile) |
| `--only-categories=performance` | Run only performance audit |
| `--only-audits=<audit-ids>` | Run specific audits only |
| `--skip-audits=<audit-ids>` | Skip specific audits |
| `--output html` | Generate HTML report |
| `--output json` | Generate JSON report |
| `--output-path ./report` | Output file path |
| `--chrome-flags="--headless"` | Headless mode |
| `--list-all-audits` | List all available audit IDs |
| `--extra-headers` | Add custom headers (for auth) |

---

## Notes

- Lighthouse will **reload the page** to run its audit
- Use `--disable-storage-reset` to stay logged in after reload
- The debugging port (9222) must match between Chrome launch and Lighthouse command
- Close other Chrome instances before launching with debugging, or use a different port
- Mobile is the default viewport; use `--preset desktop` for desktop testing
- Performance scores can vary between runs due to network and CPU variability
