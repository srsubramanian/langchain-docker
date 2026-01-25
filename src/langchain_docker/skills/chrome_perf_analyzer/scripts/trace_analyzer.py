#!/usr/bin/env python3
"""
Chrome Performance Trace Analyzer

Parses and queries Chrome DevTools Performance trace JSON files.
Supports filtering by time windows, categories, and finding slow operations.
"""

import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import argparse


@dataclass
class TraceEvent:
    name: str
    cat: str  # category
    ph: str   # phase: B=begin, E=end, X=complete, etc.
    ts: float # timestamp in microseconds
    dur: Optional[float]  # duration in microseconds (for X events)
    pid: int  # process id
    tid: int  # thread id
    args: dict

    @property
    def ts_ms(self) -> float:
        """Timestamp in milliseconds"""
        return self.ts / 1000

    @property
    def dur_ms(self) -> Optional[float]:
        """Duration in milliseconds"""
        return self.dur / 1000 if self.dur else None

    @property
    def end_ts(self) -> Optional[float]:
        """End timestamp in microseconds"""
        return self.ts + self.dur if self.dur else None

    @property
    def end_ts_ms(self) -> Optional[float]:
        """End timestamp in milliseconds"""
        return self.end_ts / 1000 if self.end_ts else None


class TraceAnalyzer:
    def __init__(self, trace_path: str):
        self.trace_path = Path(trace_path)
        self.events: list[TraceEvent] = []
        self.metadata: dict = {}
        self._load_trace()

    def _load_trace(self):
        """Load and parse the trace file"""
        with open(self.trace_path, 'r') as f:
            data = json.load(f)

        # Handle both array format and object format
        if isinstance(data, list):
            raw_events = data
        elif isinstance(data, dict):
            raw_events = data.get('traceEvents', [])
            self.metadata = {k: v for k, v in data.items() if k != 'traceEvents'}
        else:
            raise ValueError("Unknown trace format")

        for e in raw_events:
            if not isinstance(e, dict):
                continue
            self.events.append(TraceEvent(
                name=e.get('name', ''),
                cat=e.get('cat', ''),
                ph=e.get('ph', ''),
                ts=e.get('ts', 0),
                dur=e.get('dur'),
                pid=e.get('pid', 0),
                tid=e.get('tid', 0),
                args=e.get('args', {})
            ))

        # Sort by timestamp
        self.events.sort(key=lambda x: x.ts)

    @property
    def start_ts(self) -> float:
        """First timestamp in the trace (microseconds)"""
        return self.events[0].ts if self.events else 0

    @property
    def end_ts(self) -> float:
        """Last timestamp in the trace (microseconds)"""
        if not self.events:
            return 0
        last = self.events[-1]
        return last.end_ts if last.end_ts else last.ts

    @property
    def duration_ms(self) -> float:
        """Total trace duration in milliseconds"""
        return (self.end_ts - self.start_ts) / 1000

    def relative_ts(self, event: TraceEvent) -> float:
        """Get timestamp relative to trace start (in ms)"""
        return (event.ts - self.start_ts) / 1000

    def filter_by_time(self, start_ms: float, end_ms: float) -> list[TraceEvent]:
        """Filter events within a time window (relative to trace start, in ms)"""
        start_us = self.start_ts + (start_ms * 1000)
        end_us = self.start_ts + (end_ms * 1000)
        return [e for e in self.events if start_us <= e.ts <= end_us]

    def filter_by_category(self, category: str) -> list[TraceEvent]:
        """Filter events by category (supports partial match)"""
        return [e for e in self.events if category.lower() in e.cat.lower()]

    def filter_by_name(self, name: str) -> list[TraceEvent]:
        """Filter events by name (supports partial match)"""
        return [e for e in self.events if name.lower() in e.name.lower()]

    def get_network_requests(self) -> list[dict]:
        """Extract network requests with timing information"""
        requests = {}

        for e in self.events:
            if e.name == 'ResourceSendRequest':
                url = e.args.get('data', {}).get('url', '')
                req_id = e.args.get('data', {}).get('requestId', '')
                if req_id:
                    requests[req_id] = {
                        'url': url,
                        'start_ts': e.ts,
                        'start_ms': self.relative_ts(e),
                        'method': e.args.get('data', {}).get('requestMethod', 'GET'),
                    }

            elif e.name == 'ResourceReceiveResponse':
                req_id = e.args.get('data', {}).get('requestId', '')
                if req_id in requests:
                    requests[req_id]['response_ts'] = e.ts
                    requests[req_id]['status'] = e.args.get('data', {}).get('statusCode')
                    requests[req_id]['mime'] = e.args.get('data', {}).get('mimeType', '')

            elif e.name == 'ResourceFinish':
                req_id = e.args.get('data', {}).get('requestId', '')
                if req_id in requests:
                    requests[req_id]['end_ts'] = e.ts
                    requests[req_id]['end_ms'] = self.relative_ts(e)
                    requests[req_id]['encoded_size'] = e.args.get('data', {}).get('encodedDataLength')
                    # Calculate duration
                    start = requests[req_id].get('start_ts', 0)
                    requests[req_id]['duration_ms'] = (e.ts - start) / 1000

        return list(requests.values())

    def get_network_in_window(self, start_ms: float, end_ms: float) -> list[dict]:
        """Get network requests that started within a time window"""
        all_requests = self.get_network_requests()
        return [r for r in all_requests if start_ms <= r.get('start_ms', 0) <= end_ms]

    def get_long_tasks(self, threshold_ms: float = 50) -> list[TraceEvent]:
        """Get tasks longer than threshold (default 50ms for Long Tasks)"""
        long_tasks = []
        for e in self.events:
            if e.dur_ms and e.dur_ms >= threshold_ms:
                long_tasks.append(e)
        return sorted(long_tasks, key=lambda x: x.dur or 0, reverse=True)

    def get_slowest_events(self, n: int = 10, category: Optional[str] = None) -> list[TraceEvent]:
        """Get the N slowest events, optionally filtered by category"""
        events = self.events
        if category:
            events = self.filter_by_category(category)

        with_duration = [e for e in events if e.dur is not None]
        return sorted(with_duration, key=lambda x: x.dur or 0, reverse=True)[:n]

    def get_main_thread_events(self) -> list[TraceEvent]:
        """Get events from the main thread (renderer main)"""
        # Find the main thread - typically has most events with devtools.timeline category
        thread_counts = {}
        for e in self.events:
            if 'devtools.timeline' in e.cat:
                key = (e.pid, e.tid)
                thread_counts[key] = thread_counts.get(key, 0) + 1

        if not thread_counts:
            return []

        main_pid, main_tid = max(thread_counts, key=thread_counts.get)
        return [e for e in self.events if e.pid == main_pid and e.tid == main_tid]

    def summary(self) -> dict:
        """Get a summary of the trace"""
        categories = {}
        for e in self.events:
            for cat in e.cat.split(','):
                cat = cat.strip()
                if cat:
                    categories[cat] = categories.get(cat, 0) + 1

        network = self.get_network_requests()
        long_tasks = self.get_long_tasks()

        return {
            'total_events': len(self.events),
            'duration_ms': self.duration_ms,
            'categories': categories,
            'network_requests': len(network),
            'long_tasks_count': len(long_tasks),
            'slowest_network': sorted(network, key=lambda x: x.get('duration_ms', 0), reverse=True)[:5],
        }

    def print_network_table(self, requests: list[dict]):
        """Print network requests as a formatted table"""
        if not requests:
            print("No network requests found.")
            return

        # Sort by start time
        requests = sorted(requests, key=lambda x: x.get('start_ms', 0))

        print(f"\n{'Start (ms)':<12} {'Duration (ms)':<14} {'Status':<8} {'Size':<12} {'URL'}")
        print("-" * 100)

        for r in requests:
            start = f"{r.get('start_ms', 0):.1f}"
            dur = f"{r.get('duration_ms', 0):.1f}" if r.get('duration_ms') else '-'
            status = str(r.get('status', '-'))
            size = f"{r.get('encoded_size', 0):,}" if r.get('encoded_size') else '-'
            url = r.get('url', '')[:60]
            print(f"{start:<12} {dur:<14} {status:<8} {size:<12} {url}")

    def print_events_table(self, events: list[TraceEvent], show_relative: bool = True):
        """Print events as a formatted table"""
        if not events:
            print("No events found.")
            return

        print(f"\n{'Time (ms)':<12} {'Duration (ms)':<14} {'Category':<25} {'Name'}")
        print("-" * 100)

        for e in events:
            ts = f"{self.relative_ts(e):.1f}" if show_relative else f"{e.ts_ms:.1f}"
            dur = f"{e.dur_ms:.1f}" if e.dur_ms else '-'
            cat = e.cat[:24]
            print(f"{ts:<12} {dur:<14} {cat:<25} {e.name}")


def main():
    parser = argparse.ArgumentParser(description='Analyze Chrome Performance traces')
    parser.add_argument('trace_file', help='Path to the trace JSON file')
    parser.add_argument('--summary', action='store_true', help='Show trace summary')
    parser.add_argument('--network', action='store_true', help='Show all network requests')
    parser.add_argument('--network-window', nargs=2, type=float, metavar=('START_MS', 'END_MS'),
                        help='Show network requests in time window')
    parser.add_argument('--slowest', type=int, metavar='N', help='Show N slowest events')
    parser.add_argument('--long-tasks', type=float, nargs='?', const=50, metavar='THRESHOLD_MS',
                        help='Show long tasks (default threshold: 50ms)')
    parser.add_argument('--filter-name', type=str, help='Filter events by name')
    parser.add_argument('--filter-category', type=str, help='Filter events by category')
    parser.add_argument('--time-window', nargs=2, type=float, metavar=('START_MS', 'END_MS'),
                        help='Filter events by time window')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    analyzer = TraceAnalyzer(args.trace_file)

    if args.summary:
        summary = analyzer.summary()
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"\n=== Trace Summary ===")
            print(f"Total events: {summary['total_events']:,}")
            print(f"Duration: {summary['duration_ms']:.1f} ms")
            print(f"Network requests: {summary['network_requests']}")
            print(f"Long tasks (>50ms): {summary['long_tasks_count']}")
            print(f"\nTop categories:")
            for cat, count in sorted(summary['categories'].items(), key=lambda x: -x[1])[:10]:
                print(f"  {cat}: {count}")
            if summary['slowest_network']:
                print(f"\nSlowest network requests:")
                for r in summary['slowest_network']:
                    print(f"  {r.get('duration_ms', 0):.1f}ms - {r.get('url', '')[:60]}")

    elif args.network:
        requests = analyzer.get_network_requests()
        if args.json:
            print(json.dumps(requests, indent=2))
        else:
            analyzer.print_network_table(requests)

    elif args.network_window:
        start, end = args.network_window
        requests = analyzer.get_network_in_window(start, end)
        if args.json:
            print(json.dumps(requests, indent=2))
        else:
            print(f"\nNetwork requests between {start}ms and {end}ms:")
            analyzer.print_network_table(requests)

    elif args.slowest:
        events = analyzer.get_slowest_events(args.slowest, args.filter_category)
        if args.json:
            print(json.dumps([{'name': e.name, 'cat': e.cat, 'dur_ms': e.dur_ms,
                              'ts_ms': analyzer.relative_ts(e)} for e in events], indent=2))
        else:
            print(f"\n{args.slowest} Slowest Events:")
            analyzer.print_events_table(events)

    elif args.long_tasks is not None:
        threshold = args.long_tasks
        events = analyzer.get_long_tasks(threshold)
        if args.json:
            print(json.dumps([{'name': e.name, 'cat': e.cat, 'dur_ms': e.dur_ms,
                              'ts_ms': analyzer.relative_ts(e)} for e in events], indent=2))
        else:
            print(f"\nLong Tasks (>{threshold}ms): {len(events)} found")
            analyzer.print_events_table(events[:20])

    else:
        # Default: apply filters and show events
        events = analyzer.events

        if args.time_window:
            start, end = args.time_window
            events = analyzer.filter_by_time(start, end)

        if args.filter_name:
            events = [e for e in events if args.filter_name.lower() in e.name.lower()]

        if args.filter_category:
            events = [e for e in events if args.filter_category.lower() in e.cat.lower()]

        if args.json:
            print(json.dumps([{'name': e.name, 'cat': e.cat, 'dur_ms': e.dur_ms,
                              'ts_ms': analyzer.relative_ts(e), 'args': e.args} for e in events[:100]], indent=2))
        else:
            print(f"\nFound {len(events)} events")
            analyzer.print_events_table(events[:50])
            if len(events) > 50:
                print(f"\n... and {len(events) - 50} more events")


if __name__ == '__main__':
    main()
