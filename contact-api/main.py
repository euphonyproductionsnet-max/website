import os
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://euphonyproductions.net"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

# Simple in-memory rate limiting: 1 request per IP per 60s
_rate_limit: dict[str, float] = {}
RATE_LIMIT_SECONDS = 60

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
RECIPIENT = "chanceoverton@gmail.com"

VALID_SUBJECTS = {"General", "Audiobook", "Collaboration", "Other"}


@app.post("/send")
async def send_contact(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
):
    # Validate fields
    if not name.strip() or not email.strip() or not message.strip():
        return JSONResponse({"error": "All fields are required."}, status_code=400)

    if subject not in VALID_SUBJECTS:
        return JSONResponse({"error": "Invalid subject."}, status_code=400)

    if "@" not in email or "." not in email:
        return JSONResponse({"error": "Invalid email address."}, status_code=400)

    # Rate limit by IP
    client_ip = request.headers.get("X-Real-IP", request.client.host)
    now = time.time()
    last_sent = _rate_limit.get(client_ip, 0)
    if now - last_sent < RATE_LIMIT_SECONDS:
        remaining = int(RATE_LIMIT_SECONDS - (now - last_sent))
        return JSONResponse(
            {"error": f"Please wait {remaining}s before sending another message."},
            status_code=429,
        )

    # Build email
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT
    msg["Subject"] = f"[euphonyproductions.net] {subject} — from {name}"
    msg["Reply-To"] = email

    body = (
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Subject: {subject}\n\n"
        f"{message}"
    )
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
    except Exception:
        return JSONResponse(
            {"error": "Failed to send message. Please try again later."},
            status_code=500,
        )

    _rate_limit[client_ip] = now
    return {"ok": True, "message": "Message sent successfully."}
