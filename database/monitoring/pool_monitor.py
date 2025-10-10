"""
Database connection pool monitoring.

Tracks pool health, usage patterns, and performance metrics.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque

from sqlalchemy.pool import Pool
from sqlalchemy.ext.asyncio import AsyncEngine

from utils.monitoring import get_logger

logger = get_logger(__name__)


@dataclass
class PoolMetric:
    """Single pool metric snapshot."""
    timestamp: datetime
    size: int
    checked_out: int
    overflow: int
    queue_size: int = 0


@dataclass
class PoolStats:
    """Aggregated pool statistics."""
    avg_size: float = 0.0
    avg_checked_out: float = 0.0
    max_checked_out: int = 0
    avg_overflow: float = 0.0
    max_overflow: int = 0
    total_checkouts: int = 0
    total_checkins: int = 0
    total_connects: int = 0
    health_checks_passed: int = 0
    health_checks_failed: int = 0
    metrics_history: List[PoolMetric] = field(default_factory=list)


class DatabasePoolMonitor:
    """
    Monitor database connection pool health and performance.
    
    Features:
    - Real-time pool metrics
    - Historical tracking
    - Health checks
    - Alerting on thresholds
    - Performance analysis
    """
    
    def __init__(
        self,
        engine: AsyncEngine,
        history_size: int = 100,
        alert_threshold: float = 0.8  # 80% utilization
    ):
        """
        Initialize pool monitor.
        
        Args:
            engine: SQLAlchemy async engine
            history_size: Number of historical metrics to keep
            alert_threshold: Utilization threshold for alerts (0-1)
        """
        self.engine = engine
        self.pool: Pool = engine.pool
        self.history_size = history_size
        self.alert_threshold = alert_threshold
        
        # Metrics history (circular buffer)
        self.metrics_history: deque = deque(maxlen=history_size)
        
        # Statistics
        self.stats = PoolStats()
        
        # Monitoring task
        self.monitoring_task: Optional[asyncio.Task] = None
        self.monitoring_interval = 60  # seconds
    
    def capture_snapshot(self) -> PoolMetric:
        """Capture current pool state snapshot."""
        pool = self.pool
        
        metric = PoolMetric(
            timestamp=datetime.utcnow(),
            size=pool.size(),
            checked_out=pool.checkedout(),
            overflow=pool.overflow(),
        )
        
        # Add to history
        self.metrics_history.append(metric)
        
        # Update stats
        self._update_stats(metric)
        
        return metric
    
    def _update_stats(self, metric: PoolMetric):
        """Update aggregated statistics."""
        # Add to metrics history
        self.stats.metrics_history.append(metric)
        
        # Keep only recent history
        if len(self.stats.metrics_history) > self.history_size:
            self.stats.metrics_history.pop(0)
        
        # Calculate averages
        if self.stats.metrics_history:
            self.stats.avg_size = sum(
                m.size for m in self.stats.metrics_history
            ) / len(self.stats.metrics_history)
            
            self.stats.avg_checked_out = sum(
                m.checked_out for m in self.stats.metrics_history
            ) / len(self.stats.metrics_history)
            
            self.stats.avg_overflow = sum(
                m.overflow for m in self.stats.metrics_history
            ) / len(self.stats.metrics_history)
            
            # Track maximums
            self.stats.max_checked_out = max(
                m.checked_out for m in self.stats.metrics_history
            )
            
            self.stats.max_overflow = max(
                m.overflow for m in self.stats.metrics_history
            )
    
    def get_current_utilization(self) -> float:
        """
        Get current pool utilization (0-1).
        
        Returns:
            Utilization ratio
        """
        pool = self.pool
        size = pool.size()
        
        if size == 0:
            return 0.0
        
        checked_out = pool.checkedout()
        return checked_out / size
    
    def is_healthy(self) -> bool:
        """
        Check if pool is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        utilization = self.get_current_utilization()
        
        # Check utilization threshold
        if utilization > self.alert_threshold:
            logger.warning(
                f"Pool utilization high: {utilization*100:.1f}%"
            )
            return False
        
        # Check for overflow
        if self.pool.overflow() > 0:
            logger.warning(f"Pool overflow: {self.pool.overflow()}")
        
        return True
    
    async def health_check(self) -> bool:
        """
        Perform database health check.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            from sqlalchemy import text
            
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            
            self.stats.health_checks_passed += 1
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.stats.health_checks_failed += 1
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive pool statistics.
        
        Returns:
            Statistics dictionary
        """
        pool = self.pool
        current_util = self.get_current_utilization()
        
        return {
            "current": {
                "size": pool.size(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "utilization_percent": round(current_util * 100, 2),
            },
            "configuration": {
                "pool_size": getattr(pool, '_pool_size', 'N/A'),
                "max_overflow": getattr(pool, '_max_overflow', 'N/A'),
                "timeout": getattr(pool, '_timeout', 'N/A'),
            },
            "statistics": {
                "avg_size": round(self.stats.avg_size, 2),
                "avg_checked_out": round(self.stats.avg_checked_out, 2),
                "max_checked_out": self.stats.max_checked_out,
                "avg_overflow": round(self.stats.avg_overflow, 2),
                "max_overflow": self.stats.max_overflow,
                "health_checks_passed": self.stats.health_checks_passed,
                "health_checks_failed": self.stats.health_checks_failed,
            },
            "health": {
                "is_healthy": self.is_healthy(),
                "alert_threshold_percent": self.alert_threshold * 100,
            },
            "history_size": len(self.metrics_history),
        }
    
    def get_utilization_trend(
        self,
        minutes: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get utilization trend over time.
        
        Args:
            minutes: Time window in minutes
            
        Returns:
            List of utilization snapshots
        """
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        recent_metrics = [
            m for m in self.metrics_history
            if m.timestamp > cutoff
        ]
        
        return [
            {
                "timestamp": m.timestamp.isoformat(),
                "utilization_percent": (
                    m.checked_out / m.size * 100 if m.size > 0 else 0
                ),
                "checked_out": m.checked_out,
                "size": m.size,
            }
            for m in recent_metrics
        ]
    
    async def start_monitoring(self):
        """Start background pool monitoring."""
        if self.monitoring_task and not self.monitoring_task.done():
            logger.warning("Pool monitoring already running")
            return
        
        async def monitoring_loop():
            while True:
                try:
                    # Capture snapshot
                    self.capture_snapshot()
                    
                    # Health check
                    is_healthy = await self.health_check()
                    
                    # Check thresholds
                    if not self.is_healthy():
                        logger.warning("Pool health check failed")
                    
                    await asyncio.sleep(self.monitoring_interval)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")
        
        self.monitoring_task = asyncio.create_task(monitoring_loop())
        logger.info("Started database pool monitoring")
    
    async def stop_monitoring(self):
        """Stop background pool monitoring."""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped database pool monitoring")
    
    def reset_stats(self):
        """Reset all statistics."""
        self.metrics_history.clear()
        self.stats = PoolStats()
        logger.info("Pool statistics reset")


# Global pool monitor
_global_monitor: Optional[DatabasePoolMonitor] = None


def get_pool_monitor(
    engine: Optional[AsyncEngine] = None
) -> DatabasePoolMonitor:
    """Get or create global pool monitor."""
    global _global_monitor
    
    if _global_monitor is None:
        if engine is None:
            from database.core.async_engine import async_db_engine
            engine = async_db_engine.engine
        
        _global_monitor = DatabasePoolMonitor(engine)
    
    return _global_monitor


async def monitor_pool_health(engine: AsyncEngine) -> Dict[str, Any]:
    """
    Quick pool health check.
    
    Args:
        engine: SQLAlchemy async engine
        
    Returns:
        Health status dictionary
    """
    monitor = DatabasePoolMonitor(engine)
    
    # Capture snapshot
    metric = monitor.capture_snapshot()
    
    # Health check
    is_healthy = await monitor.health_check()
    
    return {
        "healthy": is_healthy,
        "utilization_percent": monitor.get_current_utilization() * 100,
        "current_connections": metric.checked_out,
        "pool_size": metric.size,
        "overflow": metric.overflow,
        "timestamp": metric.timestamp.isoformat(),
    }

