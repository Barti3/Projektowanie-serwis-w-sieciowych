
import os
import json
import threading
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
LOCK = threading.Lock()

def _ensure_db():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"items": [], "next_id": 1}, f, ensure_ascii=False, indent=2)

def load_db():
    _ensure_db()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(db):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

class ItemIn(BaseModel):
    name: str
    price: float
    tags: List[str] = []

class ItemOut(ItemIn):
    id: int

app = FastAPI(
    title="LAB02 - FastAPI (prosty middleware + CRUD)",
    description="CORS + X-Process-Time + CRUD /items na data.json. Admin endpoint z X-API-Key.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.middleware("http")
async def timing_header(request: Request, call_next):
    import time
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000.0
    response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
    return response

#!!!
API_KEY = os.getenv("API_KEY", "lab2-simple")

@app.middleware("http")
async def admin_guard(request: Request, call_next):
    if request.url.path.startswith("/admin/"):
        provided = request.headers.get("X-API-Key")
        if provided != API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized (missing/invalid X-API-Key)"}
            )
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/admin/secret")
def admin_secret():
    return {"ok": True, "msg": "Welcome, admin."}

@app.get("/items", response_model=List[ItemOut])
def list_items():
    db = load_db()
    return db["items"]

@app.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int):
    db = load_db()
    for it in db["items"]:
        if it["id"] == item_id:
            return it
    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/items", response_model=ItemOut, status_code=201)
def create_item(item: ItemIn):
    with LOCK:
        db = load_db()
        new_id = int(db.get("next_id", 1))
        rec = {"id": new_id, **item.dict()}
        db["items"].append(rec)
        db["next_id"] = new_id + 1
        save_db(db)
        return rec

@app.put("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: int, item: ItemIn):
    with LOCK:
        db = load_db()
        for i, it in enumerate(db["items"]):
            if it["id"] == item_id:
                updated = {"id": item_id, **item.dict()}
                db["items"][i] = updated
                save_db(db)
                return updated
    raise HTTPException(status_code=404, detail="Item not found")

@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    with LOCK:
        db = load_db()
        for i, it in enumerate(db["items"]):
            if it["id"] == item_id:
                db["items"].pop(i)
                save_db(db)
                return
    raise HTTPException(status_code=404, detail="Item not found")
