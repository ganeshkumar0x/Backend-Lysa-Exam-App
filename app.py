import os
import json
import sqlite3
import base64
import bcrypt
import cv2
import numpy as np
import face_recognition

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ----------------------------------
# FastAPI App
# ----------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------
# Database Initialization
# ----------------------------------
DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            face_encoding TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ----------------------------------
# Utility Functions
# ----------------------------------
def get_face_encoding_from_base64(base64_image: str):
    try:
        image_data = base64.b64decode(base64_image.split(',')[-1])
        np_arr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            return None
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb)
        return encodings[0] if encodings else None
    except Exception:
        return None

# ----------------------------------
# Pydantic Models
# ----------------------------------
class RegisterUserRequest(BaseModel):
    userId: str
    password: str
    faceImage: str

class VerifyPasswordRequest(BaseModel):
    userId: str
    password: str

class VerifyFaceRequest(BaseModel):
    userId: str
    faceImage: str

class CheckUserRequest(BaseModel):
    userId: str

# ----------------------------------
# Routes
# ----------------------------------

@app.post("/register-user")
def register_user(data: RegisterUserRequest):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM users WHERE user_id = ?", (data.userId,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="User already exists")

    face_encoding = get_face_encoding_from_base64(data.faceImage)
    if face_encoding is None:
        raise HTTPException(status_code=400, detail="Face not detected")

    password_hash = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    face_json = json.dumps(face_encoding.tolist())

    cur.execute("INSERT INTO users (user_id, password_hash, face_encoding) VALUES (?, ?, ?)",
                (data.userId, password_hash, face_json))
    conn.commit()
    conn.close()

    return {"success": True, "message": "User registered"}

@app.post("/verify-password")
def verify_password(data: VerifyPasswordRequest):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE user_id = ?", (data.userId,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    is_valid = bcrypt.checkpw(data.password.encode(), row[0].encode())
    return {"valid": bool(is_valid)}

@app.post("/verify-face")
def verify_face(data: VerifyFaceRequest):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT face_encoding FROM users WHERE user_id = ?", (data.userId,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    stored_encoding = np.array(json.loads(row[0]))
    incoming_encoding = get_face_encoding_from_base64(data.faceImage)

    if incoming_encoding is None:
        raise HTTPException(status_code=400, detail="Face not detected")

    is_match = face_recognition.compare_faces([stored_encoding], incoming_encoding, tolerance=0.5)[0]
    distance = face_recognition.face_distance([stored_encoding], incoming_encoding)[0]

    return {
        "verified": bool(is_match),
        "distance": float(distance)
    }

@app.post("/check-user")
def check_user(data: CheckUserRequest):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id = ?", (data.userId,))
    exists = cur.fetchone() is not None
    conn.close()
    return {"exists": exists}

