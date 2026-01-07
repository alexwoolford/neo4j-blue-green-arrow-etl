from typing import Any, Callable, Dict, List, Union, Tuple
from pathlib import Path

import pickle
import os
import sys
import time
import multiprocessing as mp
import subprocess as sub
import logging

import pyarrow as pa
from pyarrow import parquet as pq

# Import neo4j_arrow_client - handle both relative (when in package) and absolute (when imported directly)
try:
    from . import neo4j_arrow_client as na
except ImportError:
    # Fallback for when imported directly or in subprocess
    import sys
    from pathlib import Path
    # Try to find the package
    current_file = Path(__file__).resolve()
    src_path = current_file.parent.parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from blue_green_etl import neo4j_arrow_client as na

# Set up logger for this module
logger = logging.getLogger("neo4j_pq")

_worker_na_client = None


def _initializer(client: na.Neo4jArrowClient):
    """Initializer for our multiprocessing Pool members."""
    # log(f"Inside initializer {arrow_table_size} of type {type(arrow_table_size)}")

    global _worker_na_client
    _worker_na_client = client


def _process_nodes(nodes, **kwargs) -> Tuple[int, int]:
    """Streams the given PyArrow table to the Neo4j server using a Neo4jArrowClient."""
    global _worker_na_client
    assert _worker_na_client

    def split_labels(value):
        if(',' in value):
            return value.split(",")
        return [value]

    def update_batch(batch, new_schema):
        columns = []
        my_columns = ['labels','LABELS']
        for column_name in batch.column_names:
            column_data = batch[column_name]
            if column_name in my_columns:
                column_data = pa.array(batch[column_name].to_pandas().apply(split_labels))
            columns.append(column_data)
        
        updated_batch = pa.RecordBatch.from_arrays(
            columns,
            schema=new_schema
        )

        return updated_batch

    # Perform last mile renaming of any fields in our PyArrow Table
    def map_batch(batch):
        new_schema = batch.schema
        for idx, name in enumerate(batch.schema.names):  # assumption: they're in the column order
            field = new_schema.field(name)
            if idx == 0:
                new_schema = new_schema.set(idx, field.with_name("nodeId"))
            elif idx == 1:
                new_schema = new_schema.set(idx, field.with_name("labels"))
                new_schema = new_schema.set(idx, pa.field('labels', pa.list_(pa.string())))

        # Convert comma separated label string to an arrow array 
        return update_batch(batch, new_schema)

    # feed the graph
    return _worker_na_client.write_nodes(nodes, map_batch)


def _process_edges(edges, **kwargs) -> Tuple[int, int]:
    """Streams the given PyArrow table to the Neo4j server using a Neo4jArrowClient."""
    global _worker_na_client
    assert _worker_na_client

    # Perform last mile renaming of any fields in our PyArrow Table/Recordbatch
    def map_batch(batch):
        new_schema = batch.schema
        for idx, name in enumerate(batch.schema.names):  # assumption: they're in the column order
            field = new_schema.field(name)
            if idx == 0:
                new_schema = new_schema.set(idx, field.with_name("sourceNodeId"))
            elif idx == 1:
                new_schema = new_schema.set(idx, field.with_name("targetNodeId"))
            elif idx == 2:
                new_schema = new_schema.set(idx, field.with_name("relationshipType"))
        return batch.from_arrays(batch.columns, schema=new_schema)

    # feed the graph
    return _worker_na_client.write_edges(edges, map_batch)


def worker(work: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Main logic for our subprocessing children"""

    name = f"worker-{os.getpid()}"
    if isinstance(work, dict):
        work = [work]

    def consume_fragment(consumer, **kwargs):
        """Apply consumer to a PyArrow Fragment in the form of a generator"""

        fragment = kwargs["fragment"]
        scanner = fragment.scanner(batch_size=kwargs["table_size"])

        def batch_generator():
            for recordBatch in scanner.to_batches():
                yield recordBatch

        yield consumer(batch_generator(), **kwargs)

    total_rows, total_bytes = 0, 0

    # For now, we identify the work type based on its schema
    for task in work:
        if "key" in task:
            fn = _process_nodes
        elif "src" in task:
            fn = _process_edges
        else:
            raise Exception(f"{name} can't pick a consuming function")
        for rows, nbytes in consume_fragment(fn, **task):
            total_rows += rows
            total_bytes += nbytes
    return {"name": name, "rows": total_rows, "bytes": total_bytes}


###############################################################################
###############################################################################
#    _   _            _  _   _              _
#   | \ | | ___  ___ | || | (_)    _       / \   _ __ _ __ _____      __
#   |  \| |/ _ \/ _ \| || |_| |  _| |_    / _ \ | '__| '__/ _ \ \ /\ / /
#   | |\  |  __/ (_) |__   _| | |_   _|  / ___ \| |  | | | (_) \ V  V /
#   |_| \_|\___|\___/   |_|_/ |   |_|   /_/   \_\_|  |_|  \___/ \_/\_/
#                         |__/
#              __  __             _
#      _____  |  \/  | __ _  __ _(_) ___
#     |_____| | |\/| |/ _` |/ _` | |/ __|
#     |_____| | |  | | (_| | (_| | | (__
#             |_|  |_|\__,_|\__, |_|\___|
#                           |___/
###############################################################################
#
#  Below this point is the main entrypoint for the worker processes. Do not
#  change this area if you don't know what you're doing ;-)
#
###############################################################################

def fan_out(client: na.Neo4jArrowClient, data: str, arrow_table_size: int,
            processes: int = 0, timeout: int = 1000000) -> Tuple[List[Any], float]:
    """
    This is where the magic happens. Pop open a subprocess that execs this same
    module. Once the child is alive, send it some pickled objects to bootstrap
    the workload. The child will drive the worker pool and communicate back
    data via stdout and messaging via stderr.

    This design solves problems with Jupyter kernels mismanaging children.
    """
    config = {"processes": processes, "client": client.copy(), "arrow_table_size": arrow_table_size}
    payload = pickle.dumps((config, data))

    # Use absolute path to neo4j_pq.py based on this file's location
    neo4j_pq_path = Path(__file__).resolve()
    argv = [sys.executable, str(neo4j_pq_path)]
    
    # Capture stderr to log subprocess output in real-time (stdout must stay binary for pickle)
    import threading
    
    with sub.Popen(argv, stdin=sub.PIPE, stdout=sub.PIPE, stderr=sub.PIPE, bufsize=0) as proc:
        try:
            # Send payload
            proc.stdin.write(payload)
            proc.stdin.close()
            
            # Read stderr in real-time in a separate thread
            stderr_done = threading.Event()
            
            def read_stderr():
                """Read stderr line by line and log immediately."""
                lines_read = 0
                try:
                    # Read stderr line by line - this blocks until data is available
                    for line_bytes in iter(proc.stderr.readline, b''):
                        if not line_bytes:
                            break
                        line = line_bytes.decode('utf-8', errors='replace').rstrip()
                        if line:  # Only log non-empty lines
                            lines_read += 1
                            # Use the neo4j_pq logger (which inherits from root)
                            # This ensures proper formatting and goes to all handlers
                            logger.info(line)
                            # Force immediate flush of all handlers
                            root_logger = logging.getLogger()
                            for handler in root_logger.handlers:
                                handler.flush()
                                # For file handlers, also sync to disk
                                if hasattr(handler, 'stream') and handler.stream and hasattr(handler.stream, 'fileno'):
                                    try:
                                        import os
                                        os.fsync(handler.stream.fileno())
                                    except (OSError, AttributeError):
                                        pass
                    # Log if we read any lines (for debugging)
                    if lines_read == 0:
                        logger.warning("read_stderr: No lines read from subprocess stderr")
                    else:
                        logger.debug(f"read_stderr: Read {lines_read} lines from subprocess stderr")
                except Exception as e:
                    # Log the full exception for debugging
                    import traceback
                    logger.error(f"Error reading stderr: {e}\n{traceback.format_exc()}")
                finally:
                    stderr_done.set()
            
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()
            
            # Read stdout (binary for pickle)
            out = proc.stdout.read()
            
            # Wait for process to finish
            proc.wait(timeout=timeout)
            
            # Wait for stderr thread to finish (with timeout)
            stderr_done.wait(timeout=2.0)
            
            (res, delta) = pickle.loads(out)
            return (res, delta)
        except sub.TimeoutExpired as to_err:
            logger.error(f"timed out waiting for subprocess response...killing child")
            proc.terminate()
            return ([], 0)


if __name__ == "__main__":
    results, delta = [], 0.0

    def log(msg, newline=True):
        """
        Write message to stderr.
        
        The parent process (fan_out) will capture stderr and log it to the log file.
        This ensures all subprocess output appears in the parent's log file.
        """
        if newline:
            sys.stderr.write(f"{msg}{os.linesep}")
        else:
            sys.stderr.write(f"{msg}")
        sys.stderr.flush()


    try:
        # Read our payload from stdin and unpickle
        (config, data) = pickle.load(sys.stdin.buffer)

        work = []
        arrow_table_size = config['arrow_table_size']
        # Create pyarrow parquet dataset from passed uri location
        pyarrow_dataset = pq.ParquetDataset(data)
        log(f"Dataset {type(pyarrow_dataset)} created from: {data}")

        # Break the pyarrow parquet dataset into fragments
        if "nodes" in data:
            work = [dict(key="node", fragment=fragment, table_size=arrow_table_size) for fragment in
                    pyarrow_dataset.fragments]

        elif "relationships" in data:
            work = [dict(src="edge", fragment=fragment, table_size=arrow_table_size) for fragment in
                    pyarrow_dataset.fragments]

        client = config["client"]
        log(f"Using: 🚀 {client}")

        processes = min(len(work), config.get("processes") or int(mp.cpu_count() * 1.3))
        log(f"Spawning {processes:,} workers 🧑‍🏭 to process {len(work):,} dataset fragments 📋")

        numTicks = 33
        if (int(len(work) / numTicks) == 0):
            numTicks = int(len(work) / 0.25)

        # Make a pretty progress bar
        ticks = [n for n in range(1, len(work), numTicks)] + [len(work)]
        ticks.reverse()

        mp.set_start_method("fork")
        with mp.Pool(processes=processes, initializer=_initializer,
                     initargs=[client]) as pool:

            # The main processing loop
            log("⚙️ Loading: [", newline=False)
            start = time.time()
            for result in pool.imap_unordered(worker, work):
                results.append(result)
                if ticks and len(results) == ticks[-1]:
                    log("➶", newline=False)
                    ticks.pop()
            log("]\n", newline=False)
            delta = time.time() - start
        log(f"🏁 Completed in {round(delta, 2)}s")
        # log(f"Results {results}")
    except Exception as e:
        log(f"⚠️ Error: {e}")

    pickle.dump((results, delta), sys.stdout.buffer)
