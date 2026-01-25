# Chrome Trace Event Format Reference

Quick reference for the Trace Event Format used by Chrome DevTools Performance traces.

## Event Structure

```json
{
  "name": "EventName",
  "cat": "category,list",
  "ph": "X",
  "ts": 123456789,
  "dur": 5000,
  "pid": 1234,
  "tid": 5678,
  "args": { ... }
}
```

| Field | Description |
|-------|-------------|
| `name` | Event name |
| `cat` | Comma-separated categories |
| `ph` | Phase (event type) |
| `ts` | Timestamp in **microseconds** |
| `dur` | Duration in microseconds (for `X` phase) |
| `pid` | Process ID |
| `tid` | Thread ID |
| `args` | Event-specific data |

## Phase Types (`ph`)

| Phase | Meaning | Notes |
|-------|---------|-------|
| `B` | Begin | Paired with `E` |
| `E` | End | Paired with `B` |
| `X` | Complete | Has `dur` field |
| `I` | Instant | Single point in time |
| `M` | Metadata | Process/thread names |
| `N` | Object created | |
| `D` | Object destroyed | |
| `R` | Mark | Navigation timing marks |

## Key Categories

| Category | Contains |
|----------|----------|
| `devtools.timeline` | Main thread activity, layout, paint |
| `v8` | JavaScript execution |
| `v8.execute` | Script execution |
| `blink` | Rendering engine |
| `blink.user_timing` | User Timing API marks/measures |
| `loading` | Resource loading |
| `netlog` | Network operations |
| `disabled-by-default-devtools.timeline` | Detailed timeline (stack traces) |

## Network Events

### `ResourceSendRequest`
```json
{
  "args": {
    "data": {
      "requestId": "123.1",
      "url": "https://...",
      "requestMethod": "GET",
      "priority": "High"
    }
  }
}
```

### `ResourceReceiveResponse`
```json
{
  "args": {
    "data": {
      "requestId": "123.1",
      "statusCode": 200,
      "mimeType": "text/html",
      "fromCache": false
    }
  }
}
```

### `ResourceFinish`
```json
{
  "args": {
    "data": {
      "requestId": "123.1",
      "encodedDataLength": 12345,
      "didFail": false
    }
  }
}
```

## Main Thread Events

| Event | Description |
|-------|-------------|
| `RunTask` | Generic task execution |
| `FunctionCall` | JS function call |
| `EvaluateScript` | Script evaluation |
| `ParseHTML` | HTML parsing |
| `ParseAuthorStyleSheet` | CSS parsing |
| `Layout` | Layout calculation |
| `UpdateLayoutTree` | Style recalculation |
| `Paint` | Painting |
| `CompositeLayers` | Layer compositing |
| `RequestMainThreadFrame` | Frame request |
| `FireIdleCallback` | `requestIdleCallback` |
| `TimerFire` | `setTimeout`/`setInterval` |
| `EventDispatch` | DOM event dispatch |

## Common Queries

### Find all network requests
Filter by: `name` contains `ResourceSendRequest`

### Find layout thrashing
Filter by: `name` = `Layout` with high frequency in short window

### Find long JavaScript tasks
Filter by: `cat` contains `v8`, `dur` > 50000 (50ms)

### Find paint operations
Filter by: `name` = `Paint`

### Find main thread blocking
Filter by: `name` = `RunTask`, `dur` > 50000 (50ms)

## Time Conversions

- Trace timestamps are in **microseconds**
- To milliseconds: `ts / 1000`
- To seconds: `ts / 1000000`
- Relative time: `event.ts - first_event.ts`
