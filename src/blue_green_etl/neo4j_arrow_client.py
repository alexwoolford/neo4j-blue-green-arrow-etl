from typing import Any, Dict, Iterable, Union, Tuple, Optional
from enum import Enum
import json
import os
import sys
import time
import base64
import secrets
import logging

import pyarrow as pa
import pyarrow.flight as flight
from pyarrow.flight import ClientMiddleware, ClientMiddlewareFactory

# Import neo4j_arrow_error - handle both relative (when in package) and absolute (when imported directly)
try:
    from . import neo4j_arrow_error as error
except ImportError:
    # Fallback for when imported directly or in subprocess
    import sys
    from pathlib import Path
    # Try to find the package
    current_file = Path(__file__).resolve()
    src_path = current_file.parent.parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from blue_green_etl import neo4j_arrow_error as error


class ClientState(Enum):
    READY = "ready"
    FEEDING_NODES = "feeding_nodes"
    FEEDING_EDGES = "feeding_edges"
    AWAITING_GRAPH = "awaiting_graph"
    GRAPH_READY = "done"


class Neo4jArrowClient():
    def __init__(self, host: str, *, port: int, user: str,
                 password: str, tls: bool = False,
                 concurrency: int = 4, database: str, projection: str = None):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.tls = tls
        self.client: flight.FlightClient = None
        self.call_opts = None
        self.database = database
        self.projection= projection
        self.concurrency = concurrency
        self.state = ClientState.READY
        self.logger = logging.getLogger("Neo4jArrowClient")

    def __str__(self):
        return f"Neo4jArrowClient{{{self.user}@{self.host}:{self.port}/{self.database}}}"

    def __getstate__(self):
        state = self.__dict__.copy()
        # Remove the FlightClient and CallOpts as they're not serializable
        if "client" in state:
            del state["client"]
        if "call_opts" in state:
            del state["call_opts"]
        return state

    def copy(self):
        client = Neo4jArrowClient(self.host, port=self.port, user=self.user,
                                  password=self.password,
                                  tls=self.tls, concurrency=self.concurrency,
                                  database=self.database,projection=self.projection)
        client.state = self.state
        return client

    def _client(self):

        '''location = (
            flight.Location.for_grpc_tls(self.host, self.port)
            if self.tls
            else flight.Location.for_grpc_tcp(self.host, self.port)
        )'''
        
        location = flight.Location.for_grpc_tcp(self.host, self.port)

        client_options: Dict[str, Any] = {"disable_server_verification": False}
        auth = (self.user, self.password)
        if auth:
            client_options["middleware"] = [AuthFactory(auth)]

        self.client = flight.FlightClient(location, **client_options)
        self.call_opts = flight.FlightCallOptions(timeout=None)

        return self.client

    def abort(self, name: Optional[str] = None) -> bool:
        """Try aborting an existing import process.
        
        Returns:
            True if process was aborted, False if no process exists (normal case)
        """
        config = {
            "name": name or self.database,
        }
        try:
            result = self._send_action("ABORT", config, silent_not_found=True)
            if result and result.get("name", None) == config["name"]:
                self.state = ClientState.READY
                return True

            raise error.Neo4jArrowException(f"invalid response for abort of graph {self.database}, got {result}")
        except error.NotFound:
            # No process to abort - this is normal, not an error
            # Don't log anything, just return False
            return False
        except Exception as e:
            # Only log if it's not a NotFound (which should have been caught above)
            # but interpret it first to be sure
            interpreted = error.interpret(e)
            if not isinstance(interpreted, error.NotFound):
                self.logger.error(f"error aborting {self.database}: {e}")
        return False

    def _send_action(self, action: str, body: Dict[str, Any], silent_not_found: bool = False) -> dict:
        """
        Communicates an Arrow Action message to the GDS Arrow Service.
        
        Args:
            action: The action name
            body: The action body
            silent_not_found: If True, don't print error for NotFound exceptions (expected case)
        """
        client = self._client()
        try:
            payload = json.dumps(body).encode("utf-8")
            result = client.do_action(
                flight.Action(action, payload),
                options=self.call_opts
            )
            return json.loads(next(result).body.to_pybytes().decode())
        except Exception as e:
            # Interpret the exception to check if it's a NotFound error
            interpreted = error.interpret(e)
            
            # Don't log error for NotFound if silent_not_found is True (expected case)
            if not (silent_not_found and isinstance(interpreted, error.NotFound)):
                self.logger.error(f"send_action error: {e}")
            
            # Raise the interpreted exception so callers can handle it properly
            raise interpreted


    def _write_table(self, desc: bytes, table: pa.Table, mappingfn = None) -> Tuple[int, int]:
        """
        Write a PyArrow Table to the GDS Flight service.
        """
        client = self._client()
        fn = mappingfn or self._nop
        upload_descriptor = flight.FlightDescriptor.for_command(
            json.dumps(desc).encode("utf-8")
        )
        
        writer, _ = client.do_put(upload_descriptor, table.schema, options=self.call_opts)
        with writer:
            try:
                writer.write_table(table)
                client.close()
                return table.num_rows, table.get_total_buffer_size()
            except Exception as e:
                self.logger.error(f"_write_table error: {e}")
        client.close()
        return 0, 0

    @classmethod
    def _nop(*args, **kwargs):
        pass

    def _write_batches(self, desc: bytes, batches, mappingfn = None) -> Tuple[int, int]:
        """
        Write PyArrow RecordBatches to the GDS Flight service.
        """
        batches = iter(batches)
        fn = mappingfn or self._nop

        first = fn(next(batches, None))
        if not first:
            raise Exception("empty iterable of record batches provided")
        
        client = self._client()
        upload_descriptor = flight.FlightDescriptor.for_command(
            json.dumps(desc).encode("utf-8")
        )
        rows, nbytes = 0, 0
        writer, reader = client.do_put(upload_descriptor, first.schema, options=self.call_opts)
        with writer:
            try:
                writer.write_batch(first)
                rows += first.num_rows
                nbytes += first.get_total_buffer_size()
                for remaining in batches:
                    writer.write_batch(fn(remaining))
                    rows += remaining.num_rows
                    nbytes += remaining.get_total_buffer_size()
            except Exception as e:
                self.logger.error(f"_write_batches error: {e}")
        client.close()
        return rows, nbytes

    def retry_on_failure(max_retries, delay=1):
        def decorator(func):
            def wrapper(self, *args, **kwargs):
                for attempt in range(max_retries):
                    try:
                        result = func(self, *args, **kwargs)
                        return result
                    except Exception as e:
                        if attempt < max_retries - 1:
                            self.logger.warning(f"Error occurred: {e}. Retrying... (attempt {attempt + 1}/{max_retries})")
                            time.sleep(delay)
                        else:
                            self.logger.error(f"Maximum retries ({max_retries}) exceeded. Function failed.")
                            raise
            return wrapper
        return decorator

    @retry_on_failure(max_retries=10, delay=3)
    def create_database(self, action: str = "CREATE_DATABASE", config: Dict[str, Any] = {}) -> Dict[str, Any]:
        self.state == ClientState.READY
        if not config:
            config = {
                "name": self.database, 
                "concurrency": self.concurrency,
                "high_io": True,
                "force": True,
                "record_format": "aligned",
                "id_property": "id",
                "id_type": "INTEGER"
            }
        
        result = self._send_action(action, config)
        if result:
            self.state = ClientState.FEEDING_NODES
        return result
    
    def create_projection(self, action: str = "CREATE_GRAPH", config: Dict[str, Any] = {}) -> Dict[str, Any]:
        assert self.state == ClientState.READY
        if not config:
            config = {
                "name": self.projection, 
                "database_name": self.database, 
                "concurrency": self.concurrency,
            }
        result = self._send_action(action, config)
        if result:
            self.state = ClientState.FEEDING_NODES
        return result

    def write_nodes(self, nodes: Union[pa.Table, Iterable[pa.RecordBatch]], mappingfn = None) -> Tuple[int, int]:
        assert self.state == ClientState.FEEDING_NODES
        desc = { "name": self.database if self.projection == None else self.projection, "entity_type": "node" }
        
        if isinstance(nodes, pa.Table):
            return self._write_table(desc, nodes, mappingfn)
        return self._write_batches(desc, nodes, mappingfn)

    def nodes_done(self) -> Dict[str, Any]:
        assert self.state == ClientState.FEEDING_NODES
        result = self._send_action("NODE_LOAD_DONE", { "name": self.database if self.projection == None else self.projection })
        if result:
            self.state = ClientState.FEEDING_EDGES
        return result

    def write_edges(self, edges: Union[pa.Table, Iterable[pa.RecordBatch]], mappingfn = None) -> Tuple[int, int]:
        assert self.state == ClientState.FEEDING_EDGES
        
        desc = { "name": self.database if self.projection == None else self.projection, "entity_type": "relationship" }

        if isinstance(edges, pa.Table):
            return self._write_table(desc, edges, mappingfn)
        
        return self._write_batches(desc, edges, mappingfn)

    def edges_done(self) -> Dict[str, Any]:
        assert self.state == ClientState.FEEDING_EDGES
        result = self._send_action("RELATIONSHIP_LOAD_DONE",
                                   { "name": self.database if self.projection == None else self.projection })
        if result:
            self.state = ClientState.AWAITING_GRAPH
        client = self._client()
        client.close()
        return result

    def wait(timeout: int = 0):
        """wait for completion"""
        assert self.state == ClientState.AWAITING_GRAPH
        self.state = ClientState.AWAITING_GRAPH
        pass

class AuthFactory(ClientMiddlewareFactory):  # type: ignore
    def __init__(self, auth: Tuple[str, str], *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._auth = auth
        self._token: Optional[str] = None
        self._token_timestamp = 0

    def start_call(self, info: Any) -> "AuthMiddleware":
        return AuthMiddleware(self)

    def token(self) -> Optional[str]:
        # check whether the token is older than 10 minutes. If so, reset it.
        
        #if self._token and int(time.time()) - self._token_timestamp > 600:
        #Always set token to none to reset token
        self._token = None
      
        return self._token

    def set_token(self, token: str) -> None:
        self._token = token
        self._token_timestamp = int(time.time())

    @property
    def auth(self) -> Tuple[str, str]:
        return self._auth


class AuthMiddleware(ClientMiddleware):  # type: ignore
    
    def __init__(self, factory: AuthFactory, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._factory = factory

    def received_headers(self, headers: Dict[str, Any]) -> None:
        auth_header: str = headers.get("Authorization", None)
        if not auth_header:
            return
        [auth_type, token] = auth_header.split(" ", 1)
        if auth_type == "Bearer":
            self._factory.set_token(token)

    def sending_headers(self) -> Dict[str, str]:
        token = self._factory.token()
        if not token:
            username, password = self._factory.auth
            auth_token = f"{username}:{password}"
            auth_token = "Basic " + base64.b64encode(auth_token.encode("utf-8")).decode("ASCII")
            # There seems to be a bug, `authorization` must be lower key
            return {"authorization": auth_token}
        else:
            return {"authorization": "Bearer " + token}

