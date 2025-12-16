import cv2
import time
import asyncio
from fastapi import FastAPI, Request, File, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
from core_logic import load_models, CaptionGenerator, SecuritySystem
from gtts import gTTS
import io
from deep_translator import GoogleTranslator
from pydantic import BaseModel
import shutil
import os

# Global variables
processor = None
model = None
device = None
caption_generator = None
security_system = None
camera = None

# Security Mode State
security_mode = "webcam" # 'webcam' or 'video'
uploaded_video_path = None
security_video_capture = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global processor, model, device, caption_generator, security_system, camera
    # Startup
    print("Lifespan: Loading models...")
    processor, model, device = load_models()
    
    # Initialize Security System
    print("Lifespan: Initializing Security System...")
    security_system = SecuritySystem(device)

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
    if security_video_capture:
        security_video_capture.release()

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class TranslationRequest(BaseModel):
    text: str
    target_lang: str

class SpeakRequest(BaseModel):
    text: str
    lang: str

class EmailConfig(BaseModel):
    sender: str
    password: str
    receiver: str

def gen_frames_caption():
    """Generates JPEG frames for the Captioning page (Webcam Only)."""
    global camera, caption_generator
    
    while True:
        if not camera or not camera.isOpened():
            time.sleep(1)
            continue
            
        success, frame = camera.read()
        if not success:
            continue
            
        if caption_generator:
            caption_generator.update_frame(frame)
        
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

def gen_frames_security():
    """Generates Annotated JPEG frames for the Security page (Webcam or Video)."""
    global camera, security_system, security_mode, security_video_capture, uploaded_video_path
    
    while True:
        frame = None
        
        if security_mode == "webcam":
             if not camera or not camera.isOpened():
                time.sleep(1)
                continue
             success, frame = camera.read()
             if not success:
                 continue
        
        elif security_mode == "video":
            if not security_video_capture:
                 if uploaded_video_path and os.path.exists(uploaded_video_path):
                     security_video_capture = cv2.VideoCapture(uploaded_video_path)
                 else:
                     time.sleep(1)
                     continue
            
            success, frame = security_video_capture.read()
            if not success:
                # Loop video
                security_video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
        
        if frame is not None and security_system:
             # Run Inference
             annotated_frame, detected, info = security_system.process_frame(frame)
             
             # Encode
             ret, buffer = cv2.imencode('.jpg', annotated_frame)
             frame_bytes = buffer.tobytes()
             yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            time.sleep(0.1)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("caption.html", {"request": request})

@app.get("/captioning")
def caption_page(request: Request):
    return templates.TemplateResponse("caption.html", {"request": request})

@app.get("/security")
def security_page(request: Request):
    return templates.TemplateResponse("security.html", {"request": request})

@app.get("/video_feed_caption")
def video_feed_caption():
    return StreamingResponse(gen_frames_caption(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/video_feed_security")
def video_feed_security():
    return StreamingResponse(gen_frames_security(), media_type="multipart/x-mixed-replace; boundary=frame")

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

@app.post("/configure_email")
async def configure_email(config: EmailConfig):
    global security_system
    if security_system:
        security_system.email_notifier.configure(config.sender, config.password, config.receiver)
        return {"status": "success", "message": "Email configured"}
    return {"status": "error", "message": "System not ready"}

@app.post("/upload_video")
async def upload_video(file: UploadFile = File(...)):
    global security_mode, uploaded_video_path, security_video_capture
    try:
        temp_dir = "temp"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            
        uploaded_video_path = os.path.join(temp_dir, file.filename)
        with open(uploaded_video_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        security_mode = "video"
        if security_video_capture:
            security_video_capture.release()
        security_video_capture = None # Will be re-init in loop
        
        return {"status": "success", "message": "Video uploaded and mode switched"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/switch_source")
async def switch_source(source: str): # 'webcam' or 'video'
    global security_mode
    if source in ["webcam", "video"]:
        security_mode = source
        return {"status": "success", "mode": source}
    return {"status": "error"}

@app.post("/snapshot")
def save_snapshot():
    # Only for webcam snapshot
    global camera
    if camera and camera.isOpened():
        success, frame = camera.read()
        if success:
            filename = f"snapshot_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)
            return {"status": "success", "filename": filename}
    return {"status": "error", "message": "Could not take snapshot"}
