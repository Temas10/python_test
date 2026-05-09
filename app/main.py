from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from .database import SessionLocal, engine
from . import models, schemas, tasks
from .celery_app import celery_app

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Device Data Analytics Service")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/devices/{device_id}/data", status_code=201)
def add_data(device_id: int, payload: schemas.DataPayload, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        db.add(models.Device(id=device_id))
        db.commit()
    dp = models.DataPoint(
        device_id=device_id,
        timestamp=datetime.utcnow(),
        x=payload.x,
        y=payload.y,
        z=payload.z
    )
    db.add(dp)
    db.commit()
    return {"status": "ok"}

@app.post("/users", status_code=201)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = models.User(name=user.name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/users/{user_id}/devices", status_code=201)
def add_device_to_user(user_id: int, device: schemas.DeviceCreate, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    dev = db.query(models.Device).filter(models.Device.id == device.id).first()
    if not dev:
        dev = models.Device(id=device.id, user_id=user_id)
        db.add(dev)
    else:
        dev.user_id = user_id
    db.commit()
    return {"status": "ok"}

@app.get("/users/{user_id}/devices")
def list_user_devices(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    devices = db.query(models.Device).filter(models.Device.user_id == user_id).all()
    return [{"id": d.id} for d in devices]

@app.post("/devices/{device_id}/analytics")
def request_device_analytics(
    device_id: int,
    params: schemas.AnalyticsParams,
    db: Session = Depends(get_db)
):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    task = tasks.compute_device_statistics.delay(
        device_id,
        params.start_time.isoformat() if params.start_time else None,
        params.end_time.isoformat() if params.end_time else None
    )
    return {"task_id": task.id}

@app.post("/users/{user_id}/analytics")
def request_user_analytics(
    user_id: int,
    params: schemas.AnalyticsParams,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    task = tasks.compute_user_statistics.delay(
        user_id,
        params.start_time.isoformat() if params.start_time else None,
        params.end_time.isoformat() if params.end_time else None
    )
    return {"task_id": task.id}

@app.get("/tasks/{task_id}")
def get_task_result(task_id: str):
    result = celery_app.AsyncResult(task_id)
    if result.state == 'PENDING':
        return {"status": "pending"}
    elif result.state == 'SUCCESS':
        return {"status": "success", "result": result.result}
    else:
        return {"status": result.state, "info": str(result.info)}
    
@app.get("/")
def root():
    return {"message": "Добро пожаловать в сервис аналитики. Документация доступна по /docs"}