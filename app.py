import cv2
import time
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from core_logic import load_models, CaptionGenerator
from gtts import gTTS
import io
from deep_translator import GoogleTranslator
from pydantic import BaseModel

# Global variables
processor = None
model = None
device = None
caption_generator = None
camera = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global processor, model, device, caption_generator, camera
    # Startup
    print("Lifespan: Loading models...")
    processor, model, device = load_models()
    if processor and model:
        print("Lifespan: Models loaded. Initializing CaptionGenerator...")
        caption_generator = CaptionGenerator(processor, model, device)
        camera = cv2.VideoCapture(0) # Try default camera
        if not camera.isOpened():
             print("Warning: Could not open default camera 0. Trying 1...")
             camera = cv2.VideoCapture(1)
        
        if not camera.isOpened():
             print("Error: Could not open any camera.")
    else:
        print("Lifespan: Failed to load models.")

    yield
    # Shutdown
    if caption_generator:
        caption_generator.stop()
    if camera:
        camera.release()

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class TranslationRequest(BaseModel):
    text: str
    target_lang: str

class SpeakRequest(BaseModel):
    text: str
    lang: str

def gen_frames():
    """Generates JPEG frames for the video stream."""
    global camera, caption_generator
    
    while True:
        if not camera or not camera.isOpened():
            time.sleep(1)
            continue
            
        success, frame = camera.read()
        if not success:
            continue
            
        # Send frame to caption generator (it handles its own threading/skipping)
        if caption_generator:
            caption_generator.update_frame(frame)
        
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/stats")
def get_stats():
    """Returns current caption only."""
    global caption_generator
    
    caption = "Initializing..."
    if caption_generator:
        caption = caption_generator.get_caption()
        
    return JSONResponse({
        "caption": caption
    })

@app.post("/translate")
async def translate_text(request: TranslationRequest):
    try:
        translated = GoogleTranslator(source='auto', target=request.target_lang).translate(request.text)
        return {"translated_text": translated}
    except Exception as e:
        return {"translated_text": f"Error: {str(e)}"}

@app.post("/speak")
async def speak_text(request: SpeakRequest):
    try:
        # Create in-memory MP3
        mp3_fp = io.BytesIO()
        tts = gTTS(text=request.text, lang=request.lang)
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return StreamingResponse(mp3_fp, media_type="audio/mpeg")
    except Exception as e:
        print(f"TTS Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/snapshot")
def save_snapshot():
    global camera
    if camera and camera.isOpened():
        success, frame = camera.read()
        if success:
            filename = f"snapshot_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)
            return {"status": "success", "filename": filename}
    return {"status": "error", "message": "Could not take snapshot"}
