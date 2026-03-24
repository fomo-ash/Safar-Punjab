# backend/main.py
import asyncio
import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Literal

from fastapi import (Depends, FastAPI, File, Form, HTTPException, Request,
                     UploadFile, WebSocket, WebSocketDisconnect, status)
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
# --- NEW: Import CORSMiddleware ---
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from celery import Celery

from config import settings
from auth import (ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, create_access_token,
                  get_password_hash, oauth2_scheme, verify_password)
from jose import JWTError, jwt

# --- Configuration ---
UPLOAD_DIRECTORY = "./driver_uploads"
SECRET_KEY = settings.SECRET_KEY

# --- Celery & Database ---
celery_app = Celery("tasks", broker="redis://redis:6379/0", backend="redis://redis:6379/0")
client = AsyncIOMotorClient(settings.MONGO_URI)
db = client[settings.DATABASE_NAME]
driver_collection = db["drivers"]
bus_location_collection = db["bus_locations"]
route_collection = db["routes"]
stop_collection = db["stops"]

# --- FastAPI App ---
app = FastAPI()

# --- NEW: Add CORS Middleware ---
# This is the bouncer that allows your app to talk to the server.
origins = ["*"] # Allow all origins for development

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allow all methods (GET, POST, etc.)
    allow_headers=["*"], # Allow all headers
)


# --- WebSocket Connection Manager, Pydantic Models, etc. (No changes below this line) ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    async def connect(self, websocket: WebSocket, bus_id: str):
        await websocket.accept()
        if bus_id not in self.active_connections: self.active_connections[bus_id] = []
        self.active_connections[bus_id].append(websocket)
    def disconnect(self, websocket: WebSocket, bus_id: str):
        if bus_id in self.active_connections: self.active_connections[bus_id].remove(websocket)
    async def broadcast(self, message: dict, bus_id: str):
        if bus_id in self.active_connections:
            for connection in self.active_connections[bus_id]: await connection.send_json(message)
manager = ConnectionManager()

class LocationUpdate(BaseModel): lat: float; lon: float
class VerificationDocument(BaseModel): document_type: str; file_path: str; uploaded_at: datetime = Field(default_factory=datetime.utcnow)
class VehicleInfo(BaseModel): registration_number: str; bus_type: Optional[Literal['PUBLIC', 'PRIVATE']] = None; operator_name: Optional[str] = None
class Driver(BaseModel): driver_id: str; username: str; verification_status: str = "NOT_VERIFIED"; rejection_reason: Optional[str] = None; vehicle_info: Optional[VehicleInfo] = None; verification_documents: Optional[List[VerificationDocument]] = []
class StatusUpdate(BaseModel): new_status: str; bus_type: Optional[Literal['PUBLIC', 'PRIVATE']] = None
class Token(BaseModel): access_token: str; token_type: str
class DriverCreate(BaseModel): username: str; password: str
class Stop(BaseModel): stop_id: str = Field(..., description="Unique identifier for the stop"); name: str; latitude: float; longitude: float
class Route(BaseModel): route_id: str = Field(..., description="Unique identifier for the route, e.g., '10A'"); name: str; stops: List[Stop] = []
class TripStart(BaseModel): route_id: str

async def get_current_driver(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise credentials_exception
    except JWTError:
        raise credentials_exception
    driver = await driver_collection.find_one({"username": username})
    if driver is None: raise credentials_exception
    return driver

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIRECTORY), name="uploads")
templates = Jinja2Templates(directory="templates")
@app.on_event("startup")
async def startup_db_client():
    if not os.path.exists(UPLOAD_DIRECTORY): os.makedirs(UPLOAD_DIRECTORY)
@app.on_event("shutdown")
async def shutdown_db_client(): client.close()


@app.post("/auth/register", response_model=Driver)
async def register_driver(driver: DriverCreate):
    existing_driver = await driver_collection.find_one({"username": driver.username})
    if existing_driver:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(driver.password)
    new_driver_data = {
        "driver_id": driver.username,
        "username": driver.username,
        "hashed_password": hashed_password,
        "verification_status": "NOT_VERIFIED"
    }
    await driver_collection.insert_one(new_driver_data)
    return {key: val for key, val in new_driver_data.items() if key != "hashed_password"}

@app.post("/auth/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    driver = await driver_collection.find_one({"username": form_data.username})
    if not driver or not verify_password(form_data.password, driver.get("hashed_password", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    access_token = create_access_token(data={"sub": driver["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/routes", response_model=Route)
async def create_route(route: Route):
    existing_route = await route_collection.find_one({"route_id": route.route_id})
    if existing_route:
        raise HTTPException(status_code=400, detail="Route with this ID already exists.")
    route_dict = route.model_dump()
    await route_collection.insert_one(route_dict)
    return route

@app.get("/routes", response_model=List[Route])
async def get_all_routes():
    routes = []
    cursor = route_collection.find({})
    async for document in cursor:
        routes.append(Route(**document))
    return routes

@app.get("/routes/{route_id}", response_model=Route)
async def get_route_by_id(route_id: str):
    route = await route_collection.find_one({"route_id": route_id})
    if route:
        return Route(**route)
    raise HTTPException(status_code=404, detail="Route not found")

@app.post("/trips/start")
async def start_trip(trip_info: TripStart, current_driver: dict = Depends(get_current_driver)):
    driver_id = current_driver["driver_id"]
    route_id = trip_info.route_id
    route = await route_collection.find_one({"route_id": route_id})
    if not route:
        raise HTTPException(status_code=404, detail=f"Route '{route_id}' not found.")
    existing_trip = await db["active_trips"].find_one({"route_id": route_id})
    if existing_trip and existing_trip.get("driver_id") != driver_id:
        raise HTTPException(status_code=409, detail=f"Route '{route_id}' is already being driven by another driver.")
    trip_data = {"route_id": route_id, "driver_id": driver_id, "start_time": datetime.utcnow()}
    await db["active_trips"].update_one({"route_id": route_id}, {"$set": trip_data}, upsert=True)
    return {"message": f"Driver {driver_id} successfully started trip on route {route_id}."}


@app.post("/location/update")
async def update_location(location: LocationUpdate, current_driver: dict = Depends(get_current_driver)):
    driver_id = current_driver["driver_id"]
    active_trip = await db["active_trips"].find_one({"driver_id": driver_id})
    if not active_trip:
        raise HTTPException(status_code=400, detail="Driver is not on an active trip. Cannot update location.")
    route_id = active_trip["route_id"]
    db_update_data = {"lat": location.lat, "lon": location.lon, "last_updated": datetime.utcnow()}
    broadcast_data = {"lat": location.lat, "lon": location.lon, "last_updated": db_update_data["last_updated"].isoformat()}
    await bus_location_collection.update_one({"_id": route_id}, {"$set": db_update_data}, upsert=True)
    await manager.broadcast(broadcast_data, bus_id=route_id)
    return {"status": "success"}

@app.websocket("/ws/track/{route_id}")
async def websocket_endpoint(websocket: WebSocket, route_id: str):
    await manager.connect(websocket, route_id)
    try:
        last_location = await bus_location_collection.find_one({"_id": route_id})
        if last_location:
            last_location["last_updated"] = last_location["last_updated"].isoformat()
            await websocket.send_json(last_location)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, route_id)

@app.post("/drivers/upload-verification")
async def upload_verification_documents(
    registration_number: str = Form(...),
    files: List[UploadFile] = File(...),
    current_driver: dict = Depends(get_current_driver)
):
    driver_id = current_driver["driver_id"]
    if len(files) != 4: raise HTTPException(status_code=400, detail="Please upload exactly 4 files.")
    driver_upload_path = os.path.join(UPLOAD_DIRECTORY, driver_id)
    os.makedirs(driver_upload_path, exist_ok=True)
    document_payloads = []
    doc_map = {'id': 'GOVERNMENT_ID', 'license': 'LICENSE', 'selfie': 'SELFIE', 'rc': 'VEHICLE_RC'}
    for file in files:
        file_base_name = os.path.splitext(file.filename)[0].lower()
        doc_type = doc_map.get(file_base_name, "UNKNOWN")
        file_path = os.path.join(driver_upload_path, file.filename)
        with open(file_path, "wb+") as file_object: shutil.copyfileobj(file.file, file_object)
        doc_data = VerificationDocument(document_type=doc_type, file_path=file_path)
        document_payloads.append(doc_data.model_dump(mode='json'))
    vehicle_info = VehicleInfo(registration_number=registration_number)
    await driver_collection.find_one_and_update(
        {"driver_id": driver_id},
        {"$set": {"verification_status": "PENDING_REVIEW", "verification_documents": document_payloads, "vehicle_info": vehicle_info.model_dump(mode='json')}}
    )
    celery_app.send_task("celery_worker.process_verification", args=[driver_id])
    return {"message": f"Documents for driver '{driver_id}' submitted.", "status": "PENDING_REVIEW"}

@app.get("/drivers/status/{driver_id}", response_model=Driver)
async def get_driver_status(driver_id: str):
    driver = await driver_collection.find_one({"driver_id": driver_id})
    if driver: return Driver(**driver)
    raise HTTPException(status_code=404, detail="Driver not found")

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/admin/pending-drivers", response_model=List[Driver])
async def get_pending_drivers():
    cursor = driver_collection.find({"verification_status": "NEEDS_REVIEW"})
    documents = await cursor.to_list(length=100)
    pending_drivers = [Driver(**doc) for doc in documents]
    return pending_drivers

@app.post("/admin/update-status/{driver_id}")
async def update_driver_status(driver_id: str, status_update: StatusUpdate):
    new_status = status_update.new_status
    if new_status not in ["VERIFIED", "REJECTED"]: raise HTTPException(status_code=400, detail="Invalid status.")
    update_payload = {"$set": {"verification_status": new_status}}
    if new_status == "VERIFIED":
        if not status_update.bus_type: raise HTTPException(status_code=400, detail="Bus type ('PUBLIC' or 'PRIVATE') is required for verification.")
        update_payload["$set"]["vehicle_info.bus_type"] = status_update.bus_type
    update_result = await driver_collection.find_one_and_update({"driver_id": driver_id}, update_payload)
    if update_result is None: raise HTTPException(status_code=404, detail=f"Driver '{driver_id}' not found.")
    return {"driver_id": driver_id, "new_status": new_status}