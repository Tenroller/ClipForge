# Video Processor Job Recovery System

## Overview

The video processor now includes a **persistent queue system** with automatic job recovery. Jobs are persisted to a database (PostgreSQL or Redis) to ensure they survive processor crashes, restarts, or network failures.

## Features

✅ **Automatic Job Recovery** - Queued jobs are automatically recovered on startup
✅ **Orphaned Job Detection** - Running jobs from crashed instances are automatically cancelled
✅ **Multiple Backend Support** - PostgreSQL (recommended) or Redis
✅ **Zero Data Loss** - All job state is persisted continuously
✅ **Graceful Degradation** - Falls back to in-memory mode if no persistence is configured

## How It Works

### Job Persistence

Every time a job is added, updated, or cancelled, its state is persisted to the database. This includes:

- Job metadata (ID, workflow, priority, status)
- Request parameters
- Execution state (queued, running, completed, failed, cancelled)
- Progress information
- Error messages and logs
- Queue position

### Startup Recovery Process

When the video processor starts up:

1. **Connect to Persistence Backend** - Establishes connection to PostgreSQL or Redis
2. **Load All Jobs** - Retrieves all jobs from persistent storage
3. **Recover Queued Jobs** - Re-queues jobs that were waiting to be processed
4. **Cancel Orphaned Jobs** - Marks running jobs as cancelled (they were interrupted by crash)
5. **Restore Queue Order** - Maintains the original priority-based queue order
6. **Notify Backend** - Sends callbacks to update backend job status

### Job States During Recovery

| Original State | Recovery Action | Reason |
|---------------|-----------------|---------|
| `queued` | Re-queue for processing | Job never started, safe to retry |
| `running` | Mark as `cancelled` | Job was interrupted, needs manual retry |
| `completed` | Load for reference only | Job finished successfully |
| `failed` | Load for reference only | Job already failed |
| `cancelled` | Load for reference only | Job was explicitly cancelled |

## Configuration

### Environment Variables

#### PostgreSQL Backend (Recommended)

```bash
# Enable persistence (default: true)
PROCESSOR_ENABLE_PERSISTENCE=true

# PostgreSQL connection string (takes priority over Redis)
DATABASE_URL=postgresql://user:password@localhost:5432/videohelper

# Processor identity
PROCESSOR_ID=processor-1
```

#### Redis Backend (Alternative)

```bash
# Enable persistence
PROCESSOR_ENABLE_PERSISTENCE=true

# Redis connection (used if DATABASE_URL is not set)
REDIS_URL=redis://localhost:6379
REDIS_DB=1

# Processor identity
PROCESSOR_ID=processor-1
```

#### Disable Persistence (Not Recommended)

```bash
# Disable persistence - jobs will NOT survive restarts!
PROCESSOR_ENABLE_PERSISTENCE=false
```

### Backend Priority

The system selects persistence backends in this order:

1. **PostgreSQL** (if `DATABASE_URL` is set)
2. **Redis** (if `REDIS_URL` is set)
3. **In-Memory Only** (no persistence, jobs lost on restart)

## Usage

### Automatic Recovery (No Code Changes Required)

Recovery happens automatically when the processor starts. You don't need to change any code:

```bash
# Start the video processor
python video-processor/main.py
```

On startup, you'll see logs like:

```
INFO - Connected to persistent job storage for processor processor-1
INFO - Recovering jobs from persistent storage...
INFO - Recovered queued job abc-123 (workflow: moneyprinter)
WARNING - Cancelled orphaned running job def-456 (was running when processor crashed)
INFO - Job recovery complete: 3 queued jobs recovered, 1 running jobs cancelled, 5 completed/failed jobs loaded
```

### Monitoring Recovery

Check the logs for recovery statistics:

- **Queued jobs recovered** - Jobs that will continue processing
- **Running jobs cancelled** - Jobs interrupted by crash (require manual retry)
- **Completed/failed jobs loaded** - Historical jobs loaded for reference

### Manual Job Retry

If a running job was cancelled due to processor crash, you can retry it using the backend API:

```bash
# Resume a cancelled job
curl -X POST http://localhost:9000/api/jobs/{job_id}/resume
```

## Architecture

### Database Schema (PostgreSQL)

```sql
CREATE TABLE processor_jobs (
    job_id VARCHAR PRIMARY KEY,
    workflow VARCHAR NOT NULL,
    priority VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    request_data JSONB NOT NULL,
    callback_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    progress VARCHAR,
    current_step VARCHAR,
    error_message TEXT,
    result_data JSONB,
    logs JSONB DEFAULT '[]',
    cancelled BOOLEAN DEFAULT FALSE,
    processor_id VARCHAR,
    queue_position INTEGER
);
```

### Redis Keys (Redis Backend)

```
processor:job:{job_id}           # Job data (JSON)
processor:jobs:status:{status}   # Set of job IDs by status
processor:queue:order            # List of job IDs in queue order
```

## Best Practices

### 1. Use PostgreSQL for Production

PostgreSQL provides:
- Strong consistency guarantees
- ACID transactions
- Better query capabilities
- Integration with existing backend database

### 2. Monitor Recovery Logs

Always check startup logs to see:
- How many jobs were recovered
- If any running jobs were cancelled
- Any errors during recovery

### 3. Handle Cancelled Jobs

Jobs marked as "cancelled due to restart" should be:
- Investigated for the cause of processor crash
- Manually retried if the input was valid
- Checked for partial outputs in the output directory

### 4. Regular Cleanup

Old completed/failed jobs are kept in the database. Clean them up periodically:

```python
# Cleanup jobs older than 24 hours
job_queue.cleanup_old_jobs(max_age_hours=24)
```

### 5. Database Backups

Since jobs are now persisted, back up your database regularly to prevent data loss.

## Troubleshooting

### Issue: Jobs Not Being Recovered

**Symptoms:** Video processor starts but doesn't recover queued jobs

**Solutions:**
1. Check `DATABASE_URL` or `REDIS_URL` is set correctly
2. Verify database/Redis is accessible
3. Check logs for connection errors
4. Ensure `PROCESSOR_ENABLE_PERSISTENCE=true`

### Issue: Orphaned Jobs Keep Coming Back

**Symptoms:** Same jobs get cancelled on every restart

**Solutions:**
1. Check if multiple processors have the same `PROCESSOR_ID`
2. Verify jobs are being properly cleaned up after completion
3. Manually delete old cancelled jobs from database

### Issue: Performance Degradation

**Symptoms:** Slower job processing after enabling persistence

**Solutions:**
1. Add database indexes (already included in PostgreSQL backend)
2. Use Redis instead of PostgreSQL for better performance
3. Clean up old jobs more frequently
4. Increase database connection pool size

### Issue: Connection Errors on Startup

**Symptoms:** Processor fails to start with database errors

**Solutions:**
1. Verify database credentials and connection string
2. Check network connectivity to database
3. Ensure database exists and is initialized
4. Fall back to in-memory mode by setting `PROCESSOR_ENABLE_PERSISTENCE=false`

## Performance Considerations

### PostgreSQL Backend

- **Writes per job:** 4-6 (create, start, updates, complete)
- **Storage:** ~10-50 KB per job (depending on logs and request data)
- **Connection pooling:** 5 connections by default
- **Recommended for:** Production deployments with existing PostgreSQL

### Redis Backend

- **Writes per job:** 4-6 (same as PostgreSQL)
- **Storage:** ~10-50 KB per job
- **Performance:** Faster than PostgreSQL (in-memory)
- **Recommended for:** High-throughput scenarios, separate Redis instance

### In-Memory Mode (No Persistence)

- **Writes per job:** 0 (all in-memory)
- **Storage:** 0 (lost on restart)
- **Performance:** Fastest (no I/O)
- **Recommended for:** Development, testing only

## Migration

### Migrating from In-Memory to Persistent Queue

1. **Set up Database:**
   ```bash
   # Option 1: PostgreSQL (recommended)
   export DATABASE_URL=postgresql://user:password@localhost:5432/videohelper

   # Option 2: Redis
   export REDIS_URL=redis://localhost:6379
   ```

2. **Restart Processor:**
   ```bash
   # Gracefully stop processor
   kill -TERM <processor_pid>

   # Start with persistence enabled
   python video-processor/main.py
   ```

3. **Verify Recovery:**
   - Check logs for "Connected to persistent job storage"
   - Submit a test job
   - Restart processor and verify job is recovered

### Migrating Between Backends

To switch from Redis to PostgreSQL (or vice versa):

1. **Drain Current Queue:**
   - Wait for all jobs to complete
   - Or manually backup current jobs if needed

2. **Update Configuration:**
   ```bash
   # Switch to PostgreSQL
   export DATABASE_URL=postgresql://user:password@localhost:5432/videohelper
   unset REDIS_URL  # Optional: keep Redis as fallback
   ```

3. **Restart Processor:**
   - Jobs in the old backend won't be automatically migrated
   - New jobs will use the new backend

## Examples

### Example 1: Complete Recovery Flow

```python
# 1. Submit jobs to processor
processor.add_job(job_id="job-1", workflow="moneyprinter", ...)
processor.add_job(job_id="job-2", workflow="brainrot", ...)
processor.add_job(job_id="job-3", workflow="moneyprinter", ...)

# 2. Processor crashes while processing job-1

# 3. Processor restarts and recovers:
# - job-1: Cancelled (was running when crashed)
# - job-2: Recovered and re-queued
# - job-3: Recovered and re-queued

# 4. Backend receives callbacks:
# - job-1: status="cancelled", error="Processor restarted while job was running"
# - job-2: status="running" (when it starts processing)
# - job-3: status="running" (when it starts processing)
```

### Example 2: Checking Recovery Status

```python
# Get queue statistics after recovery
stats = job_queue.get_stats()

print(f"Total jobs: {stats['total_jobs']}")
print(f"Queued: {stats['queued_jobs']}")
print(f"Active: {stats['active_jobs']}")
print(f"Status breakdown: {stats['status_counts']}")
```

### Example 3: Manual Cleanup

```python
# Clean up completed/failed jobs older than 12 hours
removed = job_queue.cleanup_old_jobs(max_age_hours=12)
print(f"Removed {removed} old jobs")
```

## API Reference

### Configuration Options

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `PROCESSOR_ENABLE_PERSISTENCE` | boolean | `true` | Enable persistent job storage |
| `DATABASE_URL` | string | `""` | PostgreSQL connection string |
| `REDIS_URL` | string | `redis://localhost:6379` | Redis connection string |
| `REDIS_DB` | int | `1` | Redis database number |
| `PROCESSOR_ID` | string | `processor-1` | Unique processor identifier |

### Queue Methods

#### `connect()`
Initialize queue and recover jobs from persistent storage.

#### `add_job(job_id, workflow, request_data, priority, callback_url)`
Add a job to the queue and persist it.

#### `cancel_job(job_id, reason)`
Cancel a job and update persistence.

#### `cleanup_old_jobs(max_age_hours)`
Remove old completed/failed jobs from persistence.

#### `get_stats()`
Get queue statistics including recovered jobs.

## Support

For issues or questions:
1. Check the logs for detailed error messages
2. Refer to this documentation
3. Open an issue on GitHub with:
   - Processor logs
   - Configuration (redact secrets!)
   - Steps to reproduce

## Future Enhancements

Planned improvements:

- [ ] Automatic retry of failed jobs
- [ ] Job priority adjustment during recovery
- [ ] Distributed job locking for multi-processor setups
- [ ] Job dependency tracking
- [ ] Real-time recovery progress reporting
