"""Historical stats storage using SQLite."""

import sqlite3
import time
import threading
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# Default database location
DB_PATH = Path("/var/lib/networktap/stats.db")

# Fallback for development
if not DB_PATH.parent.exists():
    DB_PATH = Path(__file__).parent.parent / "stats.db"

# Collection interval in seconds
COLLECT_INTERVAL = 10

# Retention periods (in seconds)
RETENTION = {
    'raw': 7 * 24 * 60 * 60,      # 7 days of raw 10s data
    'hourly': 90 * 24 * 60 * 60,  # 90 days of hourly aggregates
}


def init_db():
    """Initialize the database schema."""
    with get_db() as conn:
        conn.executescript('''
            -- Raw stats collected every 10 seconds
            CREATE TABLE IF NOT EXISTS stats_raw (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                cpu_percent REAL,
                memory_percent REAL,
                disk_percent REAL
            );
            
            -- Network stats per interface
            CREATE TABLE IF NOT EXISTS net_stats_raw (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                interface TEXT NOT NULL,
                bytes_rx INTEGER,
                bytes_tx INTEGER,
                rx_rate INTEGER,  -- bytes/sec
                tx_rate INTEGER   -- bytes/sec
            );
            
            -- Hourly aggregated stats (for longer time ranges)
            CREATE TABLE IF NOT EXISTS stats_hourly (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,  -- hour start
                cpu_avg REAL,
                cpu_max REAL,
                memory_avg REAL,
                memory_max REAL,
                disk_avg REAL
            );
            
            CREATE TABLE IF NOT EXISTS net_stats_hourly (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                interface TEXT NOT NULL,
                rx_rate_avg INTEGER,
                rx_rate_max INTEGER,
                tx_rate_avg INTEGER,
                tx_rate_max INTEGER
            );
            
            -- Indexes for efficient querying
            CREATE INDEX IF NOT EXISTS idx_stats_raw_ts ON stats_raw(timestamp);
            CREATE INDEX IF NOT EXISTS idx_net_stats_raw_ts ON net_stats_raw(timestamp);
            CREATE INDEX IF NOT EXISTS idx_stats_hourly_ts ON stats_hourly(timestamp);
            CREATE INDEX IF NOT EXISTS idx_net_stats_hourly_ts ON net_stats_hourly(timestamp);
        ''')
        logger.info("Stats database initialized at %s", DB_PATH)


@contextmanager
def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# Track previous network bytes for rate calculation
_prev_net_bytes = {}


def collect_stats():
    """Collect current stats and store in database."""
    from core.system_monitor import get_system_stats, get_interface_stats
    
    try:
        now = int(time.time())
        sys_stats = get_system_stats()
        iface_stats = get_interface_stats()
        
        with get_db() as conn:
            # Insert system stats
            conn.execute('''
                INSERT INTO stats_raw (timestamp, cpu_percent, memory_percent, disk_percent)
                VALUES (?, ?, ?, ?)
            ''', (now, sys_stats['cpu_percent'], sys_stats['memory_percent'], sys_stats['disk_percent']))
            
            # Insert network stats with rate calculation
            global _prev_net_bytes
            for iface in iface_stats:
                name = iface['name']
                rx = iface['bytes_recv']
                tx = iface['bytes_sent']
                
                # Calculate rate
                rx_rate = 0
                tx_rate = 0
                if name in _prev_net_bytes:
                    prev = _prev_net_bytes[name]
                    elapsed = now - prev['ts']
                    if elapsed > 0:
                        rx_rate = max(0, (rx - prev['rx'])) // elapsed
                        tx_rate = max(0, (tx - prev['tx'])) // elapsed
                
                _prev_net_bytes[name] = {'ts': now, 'rx': rx, 'tx': tx}
                
                conn.execute('''
                    INSERT INTO net_stats_raw (timestamp, interface, bytes_rx, bytes_tx, rx_rate, tx_rate)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (now, name, rx, tx, rx_rate, tx_rate))
                
    except Exception as e:
        logger.error("Failed to collect stats: %s", e)


def cleanup_old_data():
    """Remove data older than retention period."""
    try:
        now = int(time.time())
        raw_cutoff = now - RETENTION['raw']
        hourly_cutoff = now - RETENTION['hourly']
        
        with get_db() as conn:
            conn.execute('DELETE FROM stats_raw WHERE timestamp < ?', (raw_cutoff,))
            conn.execute('DELETE FROM net_stats_raw WHERE timestamp < ?', (raw_cutoff,))
            conn.execute('DELETE FROM stats_hourly WHERE timestamp < ?', (hourly_cutoff,))
            conn.execute('DELETE FROM net_stats_hourly WHERE timestamp < ?', (hourly_cutoff,))
            
        logger.debug("Cleaned up old stats data")
    except Exception as e:
        logger.error("Failed to cleanup old stats: %s", e)


def aggregate_hourly():
    """Aggregate raw data into hourly buckets."""
    try:
        now = int(time.time())
        # Aggregate the previous hour
        hour_start = (now // 3600 - 1) * 3600
        hour_end = hour_start + 3600
        
        with get_db() as conn:
            # Check if already aggregated
            existing = conn.execute(
                'SELECT 1 FROM stats_hourly WHERE timestamp = ?', (hour_start,)
            ).fetchone()
            
            if existing:
                return
            
            # Aggregate system stats
            row = conn.execute('''
                SELECT 
                    AVG(cpu_percent) as cpu_avg,
                    MAX(cpu_percent) as cpu_max,
                    AVG(memory_percent) as mem_avg,
                    MAX(memory_percent) as mem_max,
                    AVG(disk_percent) as disk_avg
                FROM stats_raw
                WHERE timestamp >= ? AND timestamp < ?
            ''', (hour_start, hour_end)).fetchone()
            
            if row and row['cpu_avg'] is not None:
                conn.execute('''
                    INSERT INTO stats_hourly (timestamp, cpu_avg, cpu_max, memory_avg, memory_max, disk_avg)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (hour_start, row['cpu_avg'], row['cpu_max'], row['mem_avg'], row['mem_max'], row['disk_avg']))
            
            # Aggregate network stats per interface
            interfaces = conn.execute('''
                SELECT DISTINCT interface FROM net_stats_raw
                WHERE timestamp >= ? AND timestamp < ?
            ''', (hour_start, hour_end)).fetchall()
            
            for iface in interfaces:
                name = iface['interface']
                net_row = conn.execute('''
                    SELECT 
                        AVG(rx_rate) as rx_avg,
                        MAX(rx_rate) as rx_max,
                        AVG(tx_rate) as tx_avg,
                        MAX(tx_rate) as tx_max
                    FROM net_stats_raw
                    WHERE timestamp >= ? AND timestamp < ? AND interface = ?
                ''', (hour_start, hour_end, name)).fetchone()
                
                if net_row and net_row['rx_avg'] is not None:
                    conn.execute('''
                        INSERT INTO net_stats_hourly (timestamp, interface, rx_rate_avg, rx_rate_max, tx_rate_avg, tx_rate_max)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (hour_start, name, int(net_row['rx_avg']), net_row['rx_max'], int(net_row['tx_avg']), net_row['tx_max']))
                    
        logger.debug("Aggregated hourly stats for %s", time.strftime('%Y-%m-%d %H:00', time.localtime(hour_start)))
    except Exception as e:
        logger.error("Failed to aggregate hourly stats: %s", e)


def get_stats_history(range_key: str = '1h') -> dict:
    """
    Get historical stats for a time range.
    
    range_key: '30m', '1h', '6h', '1d', '1w', '1M'
    """
    ranges = {
        '30m': 30 * 60,
        '1h': 60 * 60,
        '6h': 6 * 60 * 60,
        '1d': 24 * 60 * 60,
        '1w': 7 * 24 * 60 * 60,
        '1M': 30 * 24 * 60 * 60,
    }
    
    seconds = ranges.get(range_key, 3600)
    now = int(time.time())
    cutoff = now - seconds
    
    # Use raw data for shorter ranges, hourly for longer
    use_hourly = range_key in ('1w', '1M')
    
    result = {
        'range': range_key,
        'from': cutoff,
        'to': now,
        'system': [],
        'network': {},
    }
    
    try:
        with get_db() as conn:
            if use_hourly:
                # Use hourly aggregates
                rows = conn.execute('''
                    SELECT timestamp, cpu_avg as cpu, memory_avg as memory, disk_avg as disk
                    FROM stats_hourly
                    WHERE timestamp >= ?
                    ORDER BY timestamp ASC
                ''', (cutoff,)).fetchall()
                
                for row in rows:
                    result['system'].append({
                        'timestamp': row['timestamp'] * 1000,  # JS expects milliseconds
                        'cpu': round(row['cpu'], 1) if row['cpu'] else 0,
                        'memory': round(row['memory'], 1) if row['memory'] else 0,
                        'disk': round(row['disk'], 1) if row['disk'] else 0,
                    })
                
                # Network hourly
                net_rows = conn.execute('''
                    SELECT timestamp, interface, rx_rate_avg as rx, tx_rate_avg as tx
                    FROM net_stats_hourly
                    WHERE timestamp >= ?
                    ORDER BY timestamp ASC
                ''', (cutoff,)).fetchall()
                
            else:
                # Use raw data, but sample if too many points
                # Target ~120 points for the chart
                target_points = 120
                
                # Count total rows
                count = conn.execute(
                    'SELECT COUNT(*) FROM stats_raw WHERE timestamp >= ?', (cutoff,)
                ).fetchone()[0]
                
                # Calculate sampling
                sample_every = max(1, count // target_points)
                
                rows = conn.execute('''
                    SELECT timestamp, cpu_percent as cpu, memory_percent as memory, disk_percent as disk
                    FROM stats_raw
                    WHERE timestamp >= ? AND (id % ?) = 0
                    ORDER BY timestamp ASC
                ''', (cutoff, sample_every)).fetchall()
                
                for row in rows:
                    result['system'].append({
                        'timestamp': row['timestamp'] * 1000,
                        'cpu': round(row['cpu'], 1) if row['cpu'] else 0,
                        'memory': round(row['memory'], 1) if row['memory'] else 0,
                        'disk': round(row['disk'], 1) if row['disk'] else 0,
                    })
                
                # Network raw
                net_rows = conn.execute('''
                    SELECT timestamp, interface, rx_rate as rx, tx_rate as tx
                    FROM net_stats_raw
                    WHERE timestamp >= ? AND (id % ?) = 0
                    ORDER BY timestamp ASC
                ''', (cutoff, sample_every)).fetchall()
            
            # Group network data by interface
            for row in net_rows:
                iface = row['interface']
                if iface not in result['network']:
                    result['network'][iface] = []
                result['network'][iface].append({
                    'timestamp': row['timestamp'] * 1000,
                    'rx': row['rx'] or 0,
                    'tx': row['tx'] or 0,
                })
                
    except Exception as e:
        logger.error("Failed to get stats history: %s", e)
    
    return result


# Background collector
_collector_thread: Optional[threading.Thread] = None
_collector_running = False


def start_collector():
    """Start the background stats collector."""
    global _collector_thread, _collector_running
    
    if _collector_running:
        return
    
    init_db()
    _collector_running = True
    
    def collector_loop():
        last_cleanup = 0
        last_aggregate = 0
        
        while _collector_running:
            try:
                collect_stats()
                
                now = time.time()
                
                # Cleanup every hour
                if now - last_cleanup > 3600:
                    cleanup_old_data()
                    last_cleanup = now
                
                # Aggregate hourly data every hour
                if now - last_aggregate > 3600:
                    aggregate_hourly()
                    last_aggregate = now
                    
            except Exception as e:
                logger.error("Collector error: %s", e)
            
            time.sleep(COLLECT_INTERVAL)
    
    _collector_thread = threading.Thread(target=collector_loop, daemon=True, name="stats-collector")
    _collector_thread.start()
    logger.info("Stats collector started (interval=%ds)", COLLECT_INTERVAL)


def stop_collector():
    """Stop the background stats collector."""
    global _collector_running
    _collector_running = False
    logger.info("Stats collector stopped")
