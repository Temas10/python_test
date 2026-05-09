from .celery_app import celery_app
from .database import SessionLocal
from .models import DataPoint, Device
from datetime import datetime
from sqlalchemy import func
import numpy as np

def _compute_stats(values):
    if not values:
        return {"min": None, "max": None, "count": 0, "sum": None, "median": None}
    arr = np.array(values)
    return {
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "count": len(values),
        "sum": float(np.sum(arr)),
        "median": float(np.median(arr))
    }

@celery_app.task(bind=True)
def compute_device_statistics(self, device_id: int, start_time: str = None, end_time: str = None):
    db = SessionLocal()
    try:
        query = db.query(DataPoint).filter(DataPoint.device_id == device_id)
        if start_time:
            query = query.filter(DataPoint.timestamp >= datetime.fromisoformat(start_time))
        if end_time:
            query = query.filter(DataPoint.timestamp <= datetime.fromisoformat(end_time))
        points = query.order_by(DataPoint.timestamp).all()
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        zs = [p.z for p in points]
        return {
            "device_id": device_id,
            "period": {"start": start_time, "end": end_time},
            "x": _compute_stats(xs),
            "y": _compute_stats(ys),
            "z": _compute_stats(zs),
        }
    finally:
        db.close()

@celery_app.task(bind=True)
def compute_user_statistics(self, user_id: int, start_time: str = None, end_time: str = None):
    db = SessionLocal()
    try:
        devices = db.query(Device).filter(Device.user_id == user_id).all()
        result = {"user_id": user_id, "devices": {}, "aggregated": None}
        all_x, all_y, all_z = [], [], []
        for dev in devices:
            task = compute_device_statistics.delay(dev.id, start_time, end_time)
            stats = task.get(timeout=10)  
            result["devices"][dev.id] = stats
            if stats["x"]["count"] > 0:
                all_x.extend([stats["x"]["min"], stats["x"]["max"]])  # для агрегации нужны все значения

        base_query = db.query(DataPoint).filter(DataPoint.device_id.in_([d.id for d in devices]))
        if start_time:
            base_query = base_query.filter(DataPoint.timestamp >= datetime.fromisoformat(start_time))
        if end_time:
            base_query = base_query.filter(DataPoint.timestamp <= datetime.fromisoformat(end_time))
        points = base_query.all()
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        zs = [p.z for p in points]
        result["aggregated"] = {
            "x": _compute_stats(xs),
            "y": _compute_stats(ys),
            "z": _compute_stats(zs),
            "device_count": len(devices)
        }
        return result
    finally:
        db.close()