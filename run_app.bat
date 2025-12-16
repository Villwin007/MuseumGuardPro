@echo off
echo Starting BLIP-CAM Web Application...
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
pause
