# Backup and Restore Procedures

This document describes how to perform backups and restores for Neo4j Enterprise Edition databases in the blue/green deployment system.

## Overview

Neo4j Enterprise Edition supports **online backups** using the `neo4j-admin` utility. This allows you to backup databases while they are running, without downtime.

**Important**: 
- Online backups are **only available in Neo4j Enterprise Edition**
- Community Edition does not support online backups (would require stopping the database)
- This solution assumes Neo4j Enterprise Edition

## Backup Procedures

### Basic Backup Command

```bash
neo4j-admin database backup <database-name> --to-path=<backup-directory> --backup-name=<backup-name>
```

**Example:**
```bash
neo4j-admin database backup customer1-1767741527 \
  --to-path=/var/neo4j/backups \
  --backup-name=customer1-1767741527-20260106
```

### Backup All Customer Databases

To backup all active customer databases (those with aliases):

```bash
#!/bin/bash
# backup_all_customers.sh

BACKUP_BASE="/var/neo4j/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_BASE}/${TIMESTAMP}"

mkdir -p "${BACKUP_DIR}"

# Get all databases with aliases (active deployments)
neo4j-admin database list | grep -E "customer[0-9]+-[0-9]+" | while read db_name; do
  echo "Backing up ${db_name}..."
  neo4j-admin database backup "${db_name}" \
    --to-path="${BACKUP_DIR}" \
    --backup-name="${db_name}-${TIMESTAMP}"
done

echo "Backups completed in ${BACKUP_DIR}"
```

### Scheduled Backups (Cron)

For production, schedule regular backups using cron:

```bash
# Edit crontab
crontab -e

# Add entry for daily backups at 2 AM
0 2 * * * /path/to/backup_all_customers.sh >> /var/log/neo4j-backups.log 2>&1
```

### Cluster Environments

In a Neo4j cluster, **one server must be configured as the backup server**.

1. **Configure Backup Server** (in `neo4j.conf`):
   ```properties
   dbms.backup.enabled=true
   dbms.backup.address=0.0.0.0:6362
   ```

2. **Run Backup Command** (on backup server or from client):
   ```bash
   neo4j-admin database backup <database-name> \
     --to-path=<backup-directory> \
     --backup-name=<backup-name> \
     --from=<backup-server-address>:6362
   ```

3. **Verify Backup Server**:
   ```bash
   # Check if backup server is running
   neo4j-admin server status
   ```

## Restore Procedures

### Basic Restore Command

```bash
neo4j-admin database restore <database-name> \
  --from-path=<backup-directory>/<backup-name>
```

**Example:**
```bash
neo4j-admin database restore customer1-1767741527 \
  --from-path=/var/neo4j/backups/customer1-1767741527-20260106
```

### Restore to New Database (Point-in-Time Recovery)

To restore a backup to a new database (useful for testing or recovery):

```bash
# Restore backup to a new database name
neo4j-admin database restore customer1-restored \
  --from-path=/var/neo4j/backups/customer1-1767741527-20260106

# Create alias pointing to restored database
# (Use manage_aliases.py or Cypher)
```

### Restore and Switch Alias (Blue/Green Recovery)

To restore a backup and switch the alias (zero-downtime recovery):

```bash
#!/bin/bash
# restore_and_switch.sh

CUSTOMER_ID="customer1"
BACKUP_PATH="/var/neo4j/backups/customer1-1767741527-20260106"
TIMESTAMP=$(date +%s)
NEW_DB_NAME="${CUSTOMER_ID}-${TIMESTAMP}"

# Restore to new database
neo4j-admin database restore "${NEW_DB_NAME}" \
  --from-path="${BACKUP_PATH}"

# Switch alias to restored database
python scripts/manage_aliases.py create "${CUSTOMER_ID}" "${NEW_DB_NAME}"

echo "Restored ${CUSTOMER_ID} to ${NEW_DB_NAME} and switched alias"
```

## Integration with Blue/Green Deployment

### Backup Strategy

1. **Backup Active Database** (the one the alias points to):
   ```bash
   # Get active database from alias
   ACTIVE_DB=$(python scripts/manage_aliases.py get-target customer1)
   
   # Backup active database
   neo4j-admin database backup "${ACTIVE_DB}" \
     --to-path=/var/neo4j/backups \
     --backup-name="${ACTIVE_DB}-$(date +%Y%m%d_%H%M%S)"
   ```

2. **Backup Before Cutover** (recommended):
   - Always backup the current active database before switching aliases
   - This provides a rollback point if the new deployment has issues

3. **Backup After Cutover** (optional):
   - Backup the new active database after successful cutover
   - This ensures you have a backup of the latest state

### Recovery Strategy

1. **Point-in-Time Recovery**:
   - Restore backup to a new database
   - Test the restored database
   - Switch alias if recovery is successful

2. **Rollback Procedure**:
   ```bash
   # If new deployment has issues, restore previous backup
   # and switch alias back
   python scripts/manage_aliases.py create customer1 customer1-1767741427
   ```

## Best Practices

### Backup Frequency

- **Production**: Daily backups (minimum)
- **High-Volume**: Multiple backups per day (e.g., every 6 hours)
- **Critical Systems**: Continuous backup (if supported by infrastructure)

### Backup Retention

- **Keep at least 7 days** of daily backups
- **Keep at least 4 weeks** of weekly backups
- **Keep at least 12 months** of monthly backups
- **Keep backups before major deployments** (indefinitely or until verified)

### Backup Storage

- **Store backups off-server** (separate storage, cloud storage, etc.)
- **Encrypt backups** if they contain sensitive data
- **Test restore procedures** regularly (at least monthly)
- **Monitor backup success** (alert on failures)

### Backup Verification

```bash
# Verify backup integrity
neo4j-admin database info --backup=/var/neo4j/backups/customer1-1767741527-20260106
```

## Monitoring

### Check Backup Status

```bash
# List all backups
ls -lh /var/neo4j/backups/

# Check backup size
du -sh /var/neo4j/backups/*
```

### Backup Logging

Backup operations are logged to Neo4j logs. Monitor for:
- Backup failures
- Backup completion times
- Backup sizes (detect anomalies)

## Troubleshooting

### Backup Fails

1. **Check disk space**:
   ```bash
   df -h /var/neo4j/backups
   ```

2. **Check Neo4j status**:
   ```bash
   neo4j-admin server status
   ```

3. **Check permissions**:
   ```bash
   ls -la /var/neo4j/backups
   ```

### Restore Fails

1. **Verify backup integrity**:
   ```bash
   neo4j-admin database info --backup=<backup-path>
   ```

2. **Check database doesn't exist** (or drop it first):
   ```bash
   # Drop existing database if needed
   python scripts/manage_aliases.py drop-database customer1-1767741527
   ```

3. **Check disk space** for restore target

## Example: Complete Backup Workflow

```bash
#!/bin/bash
# complete_backup_workflow.sh

BACKUP_BASE="/var/neo4j/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_BASE}/${TIMESTAMP}"

mkdir -p "${BACKUP_DIR}"

# Get all active databases (those with aliases)
ACTIVE_DBS=$(python scripts/manage_aliases.py list-aliases | \
  grep -oE "customer[0-9]+-[0-9]+" | sort -u)

for db_name in ${ACTIVE_DBS}; do
  echo "Backing up ${db_name}..."
  
  BACKUP_NAME="${db_name}-${TIMESTAMP}"
  
  if neo4j-admin database backup "${db_name}" \
    --to-path="${BACKUP_DIR}" \
    --backup-name="${BACKUP_NAME}"; then
    echo "✅ Backup successful: ${BACKUP_NAME}"
  else
    echo "❌ Backup failed: ${db_name}"
    # Send alert (email, Slack, etc.)
  fi
done

# Clean up old backups (keep last 30 days)
find "${BACKUP_BASE}" -type d -mtime +30 -exec rm -rf {} \;

echo "Backup workflow completed"
```

## References

- [Neo4j Enterprise Backup Documentation](https://neo4j.com/docs/operations-manual/current/backup/)
- [Neo4j Admin Commands](https://neo4j.com/docs/operations-manual/current/tools/neo4j-admin/)
- [Cluster Backup Configuration](https://neo4j.com/docs/operations-manual/current/clustering/backup/)

