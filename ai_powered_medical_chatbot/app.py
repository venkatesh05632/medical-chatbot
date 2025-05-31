import os
import shutil
import requests
import threading
import pyttsx3
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "default_secret")

# Initialize FastAPI app
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Set up templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
os.makedirs("static/uploads", exist_ok=True)

# Hardcoded username and password for login
USER = {"username": "admin", "password": "admin123"}

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "message": ""})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == USER["username"] and password == USER["password"]:
        request.session["user"] = username
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "message": "Invalid credentials"})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)

@app.get("/", response_class=HTMLResponse)
async def get_form(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "response": None,
        "image_url": None
    })

@app.post("/", response_class=HTMLResponse)
async def analyze_with_image(
    request: Request,
    symptoms: str = Form(...),
    image: UploadFile = File(None),
    speak_enabled: str = Form("off")
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=302)

    image_url = None
    try:
        if image:
            file_location = f"static/uploads/{image.filename}"
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            image_url = f"/static/uploads/{image.filename}"

        response = ask_groq(symptoms)

        if speak_enabled == "on":
            threading.Thread(target=speak, args=(response,)).start()

        return templates.TemplateResponse("index.html", {
            "request": request,
            "response": response,
            "image_url": image_url
        })
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "response": f"Error: {str(e)}",
            "image_url": image_url
        })

def ask_groq(message: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": "You are a helpful medical assistant."},
            {"role": "user", "content": message}
        ],
        "temperature": 0.7
    }

    response = requests.post(url, headers=headers, json=payload, timeout=15)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"Groq API Error {response.status_code}: {response.text}")

def speak(text: str):
    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"Text-to-speech error: {e}")