import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    """Render the home page with the calendar."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/status")
async def get_status():
    return {"status": "ACTIVE"}

@app.post("/trigger")
async def trigger():
    return {"message": "Started"}

@app.get("/calendar")
async def get_calendar():
    """Serve the generated calendar file."""
    calendar_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "toronto_screenings.ics"))
    if os.path.exists(calendar_path):
        return FileResponse(calendar_path, media_type="text/calendar", filename="toronto_screenings.ics")
    else:
        return {"error": "Calendar file not found."}