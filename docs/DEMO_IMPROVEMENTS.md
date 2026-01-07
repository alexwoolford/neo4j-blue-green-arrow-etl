# Demo Experience Improvements

This document analyzes options for improving the demo experience, including whether Prefect would be beneficial.

## Current Demo Experience

### Strengths
- ✅ Simple, self-contained orchestrator
- ✅ Works well for demos
- ✅ No external dependencies
- ✅ Clear logging output

### Pain Points
- ⚠️ No visual UI (logs only)
- ⚠️ Polling-based file detection (30s scan interval)
- ⚠️ Limited observability during demos
- ⚠️ Hard to show progress visually
- ⚠️ Status file (JSON) requires manual inspection

## Would Prefect Help?

### Prefect Overview

**Prefect** is a workflow orchestration platform that provides:
- Web UI for monitoring workflows
- Better observability and visualization
- Built-in retry logic and error handling
- File system triggers
- Task dependencies and scheduling

### Prefect for Long-Running File Watchers

**Yes, Prefect works well for long-running processes triggered by file arrivals**:

#### ✅ Pros
1. **File Triggers**: Prefect has `FileTrigger` that can watch for file/directory changes
2. **Production-Grade UI**: First-class observability, not demo-ware
3. **Task History**: Complete audit trail of all runs
4. **Built-in Retries**: Visual retry tracking and error handling
5. **Workflow Dependencies**: Can model complex workflows if needed
6. **Team Collaboration**: Multiple users can monitor and manage workflows
7. **Enterprise Features**: RBAC, audit logs, notifications available

#### ⚠️ Considerations
1. **Setup Required**: Need Prefect server (local or cloud)
2. **Refactoring**: Need to wrap existing code in Prefect flows/tasks
3. **Learning Curve**: Team needs to learn Prefect (but it's straightforward)
4. **Long-Running Flows**: Use Prefect agents or scheduled flows for continuous watching

**The setup is worth it** because you get production-grade observability instead of maintaining custom dashboard code.

### Prefect Implementation Approach

If using Prefect, you'd typically:

1. **Option A: Scheduled Flow** (Polling)
   ```python
   from prefect import flow, task
   from prefect.triggers import FileTrigger
   
   @flow
   def watch_for_snapshots():
       # Run every 30 seconds
       scan_and_load_snapshots()
   ```

2. **Option B: File Trigger** (Event-Driven)
   ```python
   from prefect import flow
   from prefect.filesystems import LocalFileSystem
   
   @flow
   def load_snapshot_on_detection(snapshot_path: str):
       # Triggered when file appears
       load_database(snapshot_path)
   ```

3. **Option C: Long-Running Agent** (Best for your use case)
   ```python
   # Run a Prefect agent that watches for work
   # Agent polls for scheduled flows or listens for events
   ```

**For your use case**: Option C (agent-based) would work best, but requires:
- Prefect server running
- Agent process running
- Flows deployed to server

## Alternative Improvements (Simpler)

### Option 1: Enhanced Status Dashboard (Recommended)

**Simplest improvement** - Add a simple web dashboard without Prefect:

```python
# scripts/dashboard.py
from flask import Flask, jsonify
import json
from pathlib import Path

app = Flask(__name__)

@app.route('/status')
def status():
    status_file = Path('orchestrator_status.json')
    if status_file.exists():
        return jsonify(json.loads(status_file.read_text()))
    return jsonify({'status': 'not_running'})

@app.route('/')
def dashboard():
    # Simple HTML dashboard showing status
    return """
    <html>
    <head><title>Orchestrator Status</title></head>
    <body>
        <h1>Blue/Green Deployment Orchestrator</h1>
        <div id="status">Loading...</div>
        <script>
            setInterval(() => {
                fetch('/status').then(r => r.json()).then(data => {
                    document.getElementById('status').innerHTML = 
                        JSON.stringify(data, null, 2);
                });
            }, 2000);
        </script>
    </body>
    </html>
    """
```

**Benefits**:
- ✅ Simple, no new dependencies
- ✅ Visual status for demos
- ✅ Real-time updates
- ✅ Works with existing orchestrator

### Option 2: Better File Watching (Watchdog)

Replace polling with event-driven file watching:

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class SnapshotHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            # New snapshot directory created
            process_snapshot(event.src_path)
```

**Benefits**:
- ✅ Immediate detection (no 30s delay)
- ✅ Event-driven (more efficient)
- ✅ Lightweight dependency

### Option 3: Rich Terminal UI

Use `rich` library for better terminal output:

```python
from rich.console import Console
from rich.table import Table
from rich.live import Live

console = Console()
# Beautiful terminal UI with progress bars, tables, etc.
```

**Benefits**:
- ✅ Better visual output in terminal
- ✅ Progress bars, tables, colors
- ✅ No web server needed
- ✅ Great for demos

### Option 4: Prefect (Full Implementation) ⭐ **Recommended**

**Why Prefect is Better Than Custom Dashboard**:
- ✅ **Production-grade UI** - Not demo-ware, but a first-class orchestration platform
- ✅ **Task history** - Complete audit trail of all runs, retries, failures
- ✅ **Better observability** - Visual workflow graphs, task dependencies, logs
- ✅ **No maintenance** - Don't need to maintain custom dashboard code
- ✅ **Professional appearance** - Shows this is production-ready, not a hack

**Setup Required**:
1. Install Prefect: `poetry add prefect`
2. Start Prefect server: `poetry run prefect server start` (runs locally on port 4200)
3. Refactor orchestrator as Prefect flows
4. Run agent: `prefect agent start --pool default`

**Code Changes**:
```python
from prefect import flow, task
from prefect.tasks import task_input_hash
from datetime import timedelta
from pathlib import Path
import time

@task(
    retries=3,
    retry_delay_seconds=2,
    log_prints=True
)
def load_database_task(customer_id: str, timestamp: int, config: dict):
    """Load database - existing logic wrapped as Prefect task."""
    from scripts.load_with_aliases import load_database
    data_path = Path(config['dataset']['base_path']) / customer_id / str(timestamp)
    return load_database(customer_id, timestamp, config, data_path)

@task
def check_health_task(config: dict) -> bool:
    """Health check before loading."""
    from scripts.orchestrator import Neo4jHealthChecker
    checker = Neo4jHealthChecker(config)
    is_healthy, _ = checker.check_health()
    return is_healthy

@flow(name="process-snapshot")
def process_snapshot_flow(customer_id: str, timestamp: int, config: dict):
    """Process a single snapshot - visible as a workflow in Prefect UI."""
    # Health check
    if not check_health_task(config):
        raise Exception("Health check failed")
    
    # Load database
    result = load_database_task(customer_id, timestamp, config)
    
    # Switch alias if latest
    from scripts.load_with_aliases import set_alias
    # ... alias switching logic
    
    return result

@flow(name="watch-for-snapshots", log_prints=True)
def watch_for_snapshots_flow(config: dict):
    """Long-running flow that watches for new snapshots."""
    processed = set()
    
    while True:
        # Scan for new snapshots (existing logic)
        data_path = Path(config['dataset']['base_path'])
        for customer_dir in data_path.iterdir():
            if not customer_dir.is_dir():
                continue
            
            customer_id = customer_dir.name
            for timestamp_dir in customer_dir.iterdir():
                if not timestamp_dir.is_dir():
                    continue
                
                try:
                    timestamp = int(timestamp_dir.name)
                except ValueError:
                    continue
                
                snapshot_key = (customer_id, timestamp)
                if snapshot_key in processed:
                    continue
                
                # Check if complete
                nodes_path = timestamp_dir / "nodes"
                relationships_path = timestamp_dir / "relationships"
                if nodes_path.exists() and relationships_path.exists():
                    if any(nodes_path.iterdir()) and any(relationships_path.iterdir()):
                        # Submit as async task - visible in Prefect UI
                        process_snapshot_flow.submit(
                            customer_id, 
                            timestamp, 
                            config
                        )
                        processed.add(snapshot_key)
        
        time.sleep(30)  # Poll interval
```

**What You Get**:
- ✅ **Prefect UI** at `http://localhost:4200` showing:
  - All workflow runs
  - Task status (running, completed, failed)
  - Retry attempts
  - Execution logs
  - Task dependencies
  - Timeline view
- ✅ **Production-ready** - Not a demo hack, but real orchestration
- ✅ **Task history** - Complete audit trail
- ✅ **Better error handling** - Visual retry tracking

## Recommendation

### **Prefect is the Better Choice** ✅

**Why Prefect over custom dashboard**:
1. **Production-grade UI** - Not demo-ware, but a first-class orchestration platform
2. **Built-in observability** - Task history, retries, dependencies, logs all in one place
3. **No maintenance burden** - Don't need to maintain custom dashboard code
4. **Better for demos** - Professional UI that shows this is production-ready
5. **Future-proof** - Scales from demo to production without rewrite

**The key insight**: If you're going to build a dashboard anyway, Prefect gives you:
- ✅ Production-grade UI (not a quick Flask hack)
- ✅ Task history and audit trail
- ✅ Better error handling and retry visualization
- ✅ Workflow dependencies and scheduling
- ✅ Team collaboration features
- ✅ Enterprise features if needed later

**Custom dashboard downsides**:
- ❌ Demo-ware that needs maintenance
- ❌ Limited features (just status display)
- ❌ No task history or audit trail
- ❌ Would need to rebuild for production anyway

### When Prefect Makes Sense

**Prefect is the right choice if**:
- You want production-grade observability (not just demo visuals)
- You want to show this is a serious, production-ready solution
- You want task history, retries, and dependencies visible
- You want to avoid maintaining custom dashboard code
- You might need workflow features later (scheduling, dependencies, etc.)

**The orchestrator is solid** - Prefect would wrap it in a production-grade UI and workflow system, making it even better for both demos and production.

## Quick Wins (No Prefect)

### 1. Add Rich Terminal Output

```bash
poetry add rich
```

```python
# In orchestrator.py
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Replace logger.info with console.print for key events
console.print(f"[green]✅[/green] Loaded {db_name}")
console.print(f"[yellow]⚠️[/yellow]  Health check failed: {message}")
```

### 2. Add Simple Web Dashboard

```bash
poetry add flask
```

```python
# scripts/dashboard.py - Simple status server
from flask import Flask, jsonify, render_template_string
import json
from pathlib import Path

app = Flask(__name__)

@app.route('/api/status')
def api_status():
    status_file = Path('orchestrator_status.json')
    if status_file.exists():
        return jsonify(json.loads(status_file.read_text()))
    return jsonify({'status': 'not_running'})

@app.route('/')
def dashboard():
    # Simple HTML with auto-refresh
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Orchestrator Status</title>
        <meta http-equiv="refresh" content="2">
        <style>
            body { font-family: monospace; padding: 20px; }
            .status { background: #f0f0f0; padding: 10px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>Blue/Green Deployment Orchestrator</h1>
        <div class="status">
            <pre id="status">Loading...</pre>
        </div>
        <script>
            fetch('/api/status')
                .then(r => r.json())
                .then(d => document.getElementById('status').textContent = 
                    JSON.stringify(d, null, 2));
        </script>
    </body>
    </html>
    """
    return html

if __name__ == '__main__':
    app.run(port=5000, debug=True)
```

### 3. Improve File Watching (Optional)

```bash
poetry add watchdog
```

Replace polling with event-driven watching (see Option 2 above).

## Conclusion

**Prefect is the right choice** because:
- ✅ **Production-grade UI** - Not demo-ware, but a first-class orchestration platform
- ✅ **Shows professionalism** - Demonstrates this is a serious, production-ready solution
- ✅ **Better than custom dashboard** - Why build what Prefect already provides?
- ✅ **Future-proof** - Works for demos AND production without rewrite
- ✅ **No maintenance burden** - Don't need to maintain custom dashboard code

**The orchestrator logic is solid** - Prefect would:
1. Wrap it in production-grade workflows
2. Provide first-class UI and observability
3. Add task history, retries, dependencies
4. Make it demo-ready AND production-ready

**Recommendation**: Use Prefect. It's not overkill - it's the right tool for the job if you want production-grade observability rather than a quick demo hack.

