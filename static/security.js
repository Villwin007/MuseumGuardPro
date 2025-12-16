const switchSourceBtn = document.getElementById('switch-source-btn');
const uploadArea = document.getElementById('upload-area');
const videoInput = document.getElementById('video-upload');
const uploadMsg = document.getElementById('upload-msg');

const statusDisplay = document.getElementById('status-display');
const statusText = document.getElementById('status-text');
const statusIcon = document.getElementById('status-icon');
const securityFeed = document.getElementById('security-feed');
const autopilotToggle = document.getElementById('autopilot-toggle');

// Toggle Source
if (switchSourceBtn) {
    switchSourceBtn.addEventListener('click', async () => {
        try {
            const res = await fetch('/switch_source?source=webcam', { method: 'POST' });
            if (res.ok) {
                uploadMsg.innerText = "Switched to Webcam";
            }
        } catch (e) { console.error(e); }
    });
}

// Upload Logic
if (uploadArea) {
    uploadArea.addEventListener('click', () => videoInput.click());

    videoInput.addEventListener('change', async (e) => {
        if (e.target.files.length === 0) return;

        const file = e.target.files[0];
        const formData = new FormData();
        formData.append('file', file);

        uploadMsg.innerText = "Uploading...";

        try {
            const res = await fetch('/upload_video', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.status === 'success') {
                uploadMsg.innerText = "Active: " + file.name;
            } else {
                uploadMsg.innerText = "Error: " + data.message;
            }
        } catch (err) {
            uploadMsg.innerText = "Upload failed";
        }
    });
}

// Toggle Auto Pilot
if (autopilotToggle) {
    autopilotToggle.addEventListener('change', async (e) => {
        const active = e.target.checked;
        console.log("Auto Pilot Toggled:", active);
        await fetch('/toggle_autopilot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active: active })
        });
    });
}

function updateStatusUI(status) {
    if (!statusDisplay) return;

    statusDisplay.className = ''; // Reset classes

    if (status === "Suspicious Activity Detected") {
        statusDisplay.classList.add('status-danger');
        statusText.innerText = "SUSPICIOUS ACTIVITY";
        statusIcon.className = "fas fa-exclamation-triangle";
        securityFeed.style.border = "4px solid red";
    } else {
        statusDisplay.classList.add('status-normal');
        statusText.innerText = "NORMAL";
        statusIcon.className = "fas fa-check-circle";
        securityFeed.style.border = "none";
    }
}

async function checkStatus() {
    try {
        const res = await fetch('/security_status');
        const data = await res.json();
        updateStatusUI(data.status);

        // Sync toggle if changed externally (or initial load)
        if (autopilotToggle && document.activeElement !== autopilotToggle) {
            autopilotToggle.checked = data.autopilot;
        }
    } catch (e) {
        console.error("Status check failed", e);
    }
}

// Poll every 1s
setInterval(checkStatus, 1000);
