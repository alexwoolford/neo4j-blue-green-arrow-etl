# Cluster Deployment Guide

This document describes how the blue/green deployment system works in Neo4j cluster environments.

## Overview

The blue/green deployment system is **fully cluster-compatible**. All operations use the Neo4j Bolt protocol, which works transparently with both single-instance and clustered Neo4j deployments.

## Cluster Compatibility ✅

### All Operations Use Bolt Protocol

Every operation in the system uses the Neo4j Bolt protocol, which is cluster-aware:

```python
# All database operations use Bolt protocol
driver = neo4j.GraphDatabase.driver(
    "bolt://neo4j-cluster:7687",  # Cluster endpoint
    auth=neo4j.basic_auth(user, password)
)
```

**Key Points:**
- ✅ **No file-based operations** - No direct database file access
- ✅ **No embedded mode** - All operations go through Neo4j server
- ✅ **Cluster-transparent** - Works with single-instance or cluster
- ✅ **Load balancing** - Bolt driver automatically balances across cluster members

### Operations That Work in Clusters

1. **Database Creation** (via Arrow protocol)
   - Arrow protocol works with clustered Neo4j
   - Database is created on all cluster members

2. **Database Aliases**
   - Aliases work across the cluster
   - Alias changes are replicated to all members

3. **Data Loading** (via Arrow protocol)
   - Arrow protocol distributes load across cluster
   - Data is replicated to all cluster members

4. **Health Checks**
   - Health checks query any cluster member
   - Results reflect cluster-wide state

5. **Database Management**
   - `CREATE DATABASE`, `DROP DATABASE` work in clusters
   - Operations are replicated across cluster

## Cluster Configuration

### Connection String

For cluster deployments, use a cluster-aware connection string:

```yaml
neo4j:
  host: neo4j-cluster.example.com  # Cluster endpoint or load balancer
  bolt_port: 7687
  # ... other config
```

**Options:**
1. **Load Balancer** (recommended):
   - Point to a load balancer that distributes across cluster members
   - Example: `host: neo4j-lb.example.com`

2. **Individual Members** (for testing):
   - Can point to any cluster member
   - Bolt driver will discover other members
   - Example: `host: neo4j-core1.example.com`

3. **Multiple Endpoints** (advanced):
   - Neo4j driver supports multiple endpoints
   - Automatically fails over if one is unavailable
   - Example: `host: neo4j-core1.example.com,neo4j-core2.example.com`

### Backup Server Configuration

In cluster environments, **one server must be configured as the backup server**.

**Configure Backup Server** (in `neo4j.conf` on backup server):

```properties
# Enable backup server
dbms.backup.enabled=true
dbms.backup.address=0.0.0.0:6362
```

**Run Backups** (from backup server or client):

```bash
neo4j-admin database backup <database-name> \
  --to-path=<backup-directory> \
  --backup-name=<backup-name> \
  --from=<backup-server-address>:6362
```

See [BACKUP_RESTORE.md](BACKUP_RESTORE.md) for detailed backup procedures.

## Health Checks in Clusters

The orchestrator's health checks work in cluster environments:

```python
# Health check queries any cluster member
with driver.session() as session:
    result = session.run("RETURN 1 AS health")
    # This works with any cluster member
```

**Considerations:**
- Health checks query the connected cluster member
- Results reflect cluster-wide state (databases, aliases are cluster-wide)
- Memory checks (JMX) query the specific member connected to
- For cluster-wide health, consider querying multiple members

## Load Balancing

### Arrow Protocol

The Arrow protocol automatically distributes load across cluster members:

- Arrow client connects to cluster endpoint
- Neo4j distributes Arrow operations across cluster
- Data is replicated to all cluster members

### Bolt Protocol

The Neo4j Bolt driver automatically:
- Discovers all cluster members
- Load balances read operations
- Routes write operations to appropriate members
- Handles failover automatically

## High Availability Considerations

### Zero-Downtime Deployments

The blue/green deployment pattern provides zero-downtime deployments:

1. **Load new database** (green) - Works while cluster is running
2. **Switch alias** - Atomic operation, no downtime
3. **Cleanup old database** - Can be done after cutover

### Cluster Member Failover

If a cluster member fails:
- Bolt driver automatically fails over to another member
- Operations continue without interruption
- No code changes needed

### Rolling Upgrades

For Neo4j cluster upgrades:
1. Upgrade cluster members one at a time (rolling upgrade)
2. Blue/green deployment system continues to work
3. No special handling needed

## Performance Considerations

### Read Replicas

If using read replicas in the cluster:
- Read operations can be distributed to replicas
- Write operations go to core members
- Arrow protocol operations go to core members

### Write Distribution

- Database creation and data loading go to core members
- Operations are replicated to all members
- Consider cluster member capacity when loading large datasets

## Monitoring in Clusters

### Health Check Endpoints

Monitor cluster health:
- Query any cluster member for health status
- Check cluster member status via `neo4j-admin server status`
- Monitor cluster metrics via Neo4j metrics endpoints

### Orchestrator Status

The orchestrator status file reflects cluster-wide state:
- Database counts include all databases in cluster
- Alias information reflects cluster-wide aliases
- Health checks query the connected member

## Troubleshooting

### Connection Issues

If connection fails:
1. **Check cluster endpoint** - Verify load balancer or cluster member is reachable
2. **Check cluster status** - Verify cluster members are running
3. **Check network** - Verify network connectivity to cluster

### Database Not Found

If database operations fail:
1. **Check cluster membership** - Verify database exists on all members
2. **Check replication** - Verify database replication completed
3. **Check alias** - Verify alias exists on all members

### Performance Issues

If performance degrades:
1. **Check cluster member load** - Monitor individual member resources
2. **Check network latency** - Monitor network between members
3. **Check replication lag** - Monitor replication delays

## Best Practices

### Cluster Configuration

1. **Use Load Balancer** - Point to load balancer, not individual members
2. **Configure Backup Server** - Designate one member as backup server
3. **Monitor Cluster Health** - Set up monitoring for all cluster members
4. **Test Failover** - Regularly test cluster member failover

### Deployment Strategy

1. **Load During Low Traffic** - Schedule large loads during low-traffic periods
2. **Monitor During Load** - Watch cluster member resources during loads
3. **Test Cutover** - Test alias switching in cluster environment
4. **Backup Before Cutover** - Always backup before switching aliases

### Resource Management

1. **Distribute Load** - Consider cluster member capacity when loading
2. **Monitor Memory** - Watch JVM heap on all cluster members
3. **Monitor Network** - Watch network bandwidth between members
4. **Plan Capacity** - Ensure cluster has capacity for new databases

## Example: Cluster Deployment

```yaml
# config.yaml for cluster deployment
neo4j:
  host: neo4j-cluster-lb.example.com  # Load balancer endpoint
  arrow_port: 8491
  bolt_port: 7687
  user: neo4j
  password: ${NEO4J_PASSWORD}
  tls: true  # Use TLS in production

orchestrator:
  num_workers: 2  # Can run multiple workers in cluster
  # ... other config
```

**Deployment Steps:**

1. **Configure Cluster** - Set up Neo4j cluster with load balancer
2. **Configure Backup Server** - Designate one member as backup server
3. **Update Config** - Point to cluster endpoint
4. **Test Connection** - Verify connection to cluster
5. **Run Orchestrator** - Start orchestrator (works transparently)

## References

- [Neo4j Clustering Documentation](https://neo4j.com/docs/operations-manual/current/clustering/)
- [Neo4j Bolt Driver Cluster Support](https://neo4j.com/docs/python-manual/current/driver-manual/#driver-cluster)
- [Neo4j Enterprise Features](https://neo4j.com/product/enterprise/)

