import cv2
from transformers import AutoProcessor, AutoModelForImageTextToText
import torch
import logging
import time
from PIL import Image
from threading import Thread, Lock
from queue import Queue
import smtplib
from email.message import EmailMessage
from ultralytics import YOLO
import os

def setup_logging():
    """Configure logging with basic formatting"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

logger = setup_logging()

class EmailNotifier:
    def __init__(self):
        self.sender_email = None
        self.app_password = None
        self.receiver_email = None
        self.last_email_time = 0
        self.cooldown = 30  # Seconds between emails

    def configure(self, sender, password, receiver):
        self.sender_email = sender
        self.app_password = password
        self.receiver_email = receiver
        logger.info(f"Email configured: {sender} -> {receiver}")

    def send_alert(self, image_frame, detection_details):
        if not self.sender_email or not self.app_password or not self.receiver_email:
            return False, "Email not configured"

        if time.time() - self.last_email_time < self.cooldown:
            return False, "Cooldown active"

        try:
            msg = EmailMessage()
            msg['Subject'] = 'SECURITY ALERT: Suspicious Activity Detected'
            msg['From'] = self.sender_email
            msg['To'] = self.receiver_email
            msg.set_content(f"Suspicious activity detected!\n\nDetails: {detection_details}\nTime: {time.ctime()}")

            # Attach image
            success, encoded_image = cv2.imencode('.jpg', image_frame)
            if success:
                msg.add_attachment(encoded_image.tobytes(), maintype='image', subtype='jpeg', filename='intruder.jpg')

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(self.sender_email, self.app_password)
                smtp.send_message(msg)

            self.last_email_time = time.time()
            logger.info("Alert email sent successfully")
            return True, "Email sent"
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False, str(e)

class SecuritySystem:
    def __init__(self, device):
        self.device = device
        self.model = None
        # Load YOLO model
        try:
            print("Loading YOLOv8 model...")
            self.model = YOLO("yolov8n.pt")
            if device == 'cuda':
                self.model.to('cuda')
            print("YOLOv8 loaded.")
        except Exception as e:
            logger.error(f"Failed to load YOLO: {e}")

        self.email_notifier = EmailNotifier()
        self.active = False
        self.last_detection = None

    def process_frame(self, frame):
        if not self.model: # or not self.active: # logic moved to app.py for active check
            return frame, False, ""

        # Run inference
        results = self.model(frame, verbose=False)
        annotated_frame = results[0].plot()
        
        person_detected = False
        detection_info = ""

        # Check for 'person' class (id 0)
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if self.model.names[cls_id] == 'person':
                    conf = float(box.conf[0])
                    if conf > 0.5:
                        person_detected = True
                        detection_info = f"Person detected ({conf:.2f})"
                        
                        # Trigger alert logic
                        self.email_notifier.send_alert(frame, detection_info)
                        break # One person is enough
        
        return annotated_frame, person_detected, detection_info

class CaptionGenerator:
    def __init__(self, processor, model, device):
        self.processor = processor
        self.model = model
        self.device = device
        self.current_caption = f"Initializing caption... ({device.upper()})"
        self.caption_queue = Queue(maxsize=1)
        self.lock = Lock()
        self.running = True
        self.thread = Thread(target=self._caption_worker)
        self.thread.daemon = True
        self.thread.start()

    def _caption_worker(self):
        while self.running:
            try:
                if not self.caption_queue.empty():
                    frame = self.caption_queue.get()
                    caption = self._generate_caption(frame)
                    print(f"DEBUG: Generated caption: {caption}")
                    with self.lock:
                        self.current_caption = caption
            except Exception as e:
                logger.error(f"Caption worker error: {str(e)}")
            time.sleep(0.1)  # Prevent busy waiting

    def _generate_caption(self, image):
        try:
            # Resize to 640x480 (or any other size)
            image_resized = cv2.resize(image, (640, 480))

            # Convert to RGB
            rgb_image = cv2.cvtColor(image_resized, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)

            # Process the image for captioning
            inputs = self.processor(images=pil_image, return_tensors="pt")
            inputs = {name: tensor.to(self.device) for name, tensor in inputs.items()}

            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=30,
                    num_beams=5,
                    num_return_sequences=1
                )

            caption = self.processor.batch_decode(outputs, skip_special_tokens=True)[0].strip()
            return f"{caption}"
        except Exception as e:
            logger.error(f"Caption generation error: {str(e)}")
            return f"Error: Caption generation failed"

    def update_frame(self, frame):
        if self.caption_queue.empty():
            try:
                self.caption_queue.put_nowait(frame.copy())
            except:
                pass  # Queue is full, skip this frame

    def get_caption(self):
        with self.lock:
            return self.current_caption

    def stop(self):
        self.running = False
        self.thread.join()

def get_gpu_usage():
    """Get the GPU memory usage and approximate utilization"""
    if torch.cuda.is_available():
        memory_allocated = torch.cuda.memory_allocated() / (1024 ** 2)  # MB
        memory_total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 2)  # MB

        memory_used_percent = (memory_allocated / memory_total) * 100
        gpu_info = {
             "memory_used_percent": memory_used_percent,
             "allocated_mb": memory_allocated,
             "total_mb": memory_total
        }
        return gpu_info
    else:
        return None

def load_models():
    """Load BLIP model"""
    try:
        logger.info("Loading BLIP model...")
        blip_processor = AutoProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
        blip_model = AutoModelForImageTextToText.from_pretrained("Salesforce/blip-image-captioning-large")

        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        if device == 'cuda':
            # Set GPU memory usage limit to 90%
            torch.cuda.set_per_process_memory_fraction(0.9)
            blip_model = blip_model.to('cuda')

        print(f"Models loaded on {device}")
        return blip_processor, blip_model, device
    except Exception as e:
        print(f"Failed to load models: {str(e)}")
        logger.error(f"Failed to load models: {str(e)}")
        return None, None, None
