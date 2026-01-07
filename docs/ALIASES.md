# Database Aliases - How They Work

## What Are Aliases?

Database aliases are alternative names that point to actual databases. They allow you to:
- Use a stable name (e.g., `customer1`) that doesn't change
- Switch which database it points to without changing application code
- Support blue/green deployments

## Example Setup

After running the demo workflow, you might have:
- **Alias**: `customer1`
- **Points to**: `customer1-1767741527` (the latest/green deployment)

**Note**: The actual alias target depends on which deployment is currently active. Use `python scripts/manage_aliases.py list-aliases` to see current alias targets.

## Using Aliases

### In Neo4j Browser or Cypher Shell

**Neo4j Browser:**
```cypher
:use customer1
```

**Cypher Query:**
```cypher
USE customer1
MATCH (n:Entity)
RETURN count(n)
```

**Note**: The `:use` command is a Neo4j Browser command (not standard Cypher). In standard Cypher, use `USE customer1` at the start of your query.

### In Python with GDS

```python
from graphdatascience import GraphDataScience

gds = GraphDataScience(
    "bolt://localhost:7687",
    auth=("neo4j", "password"),
    database="customer1"  # Use the alias name here
)

# Now all queries run against customer1-1767741427
result = gds.run_cypher("MATCH (n) RETURN count(n) AS count")
```

### In Python with Neo4j Driver

```python
import neo4j

driver = neo4j.GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=neo4j.basic_auth("neo4j", "password")
)

with driver.session(database="customer1") as session:  # Use alias name
    result = session.run("MATCH (n) RETURN count(n) AS count")
    print(result.single()["count"])
```

## Blue/Green Deployment Pattern

1. **Load new deployment** (green) without switching:
   ```bash
   python scripts/load_with_aliases.py --customer customer1 --timestamp 1767741527 --no-switch
   ```

2. **Verify the new database** directly:
   ```cypher
   USE customer1-1767741527
   MATCH (n) RETURN count(n)
   ```
   
   **Note**: In Neo4j Browser, you can use `:use customer1-1767741527` as a command, or `USE customer1-1767741527` in a Cypher query.

3. **Switch alias** to point to the new database:
   ```bash
   python scripts/manage_aliases.py create customer1 customer1-1767741527
   ```

4. **Now all queries using `customer1`** automatically use the new database!

## Managing Aliases

```bash
# List all aliases
python scripts/manage_aliases.py list-aliases

# Create/update an alias
python scripts/manage_aliases.py create customer1 customer1-1767741527

# Drop an alias
python scripts/manage_aliases.py drop customer1

# List all databases
python scripts/manage_aliases.py list-databases
```

## Important Notes

- Aliases are **not** databases - they're just pointers
- You can query the alias name directly (e.g., `USE customer1`)
- When you switch an alias, all new connections using that alias name will use the new database
- Old connections may still use the previous database until they reconnect

