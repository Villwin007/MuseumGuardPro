const switchSourceBtn = document.getElementById('switch-source-btn');
const uploadArea = document.getElementById('upload-area');
const videoInput = document.getElementById('video-upload');
const uploadMsg = document.getElementById('upload-msg');

const senderInput = document.getElementById('sender-email');
const passInput = document.getElementById('app-password');
const receiverInput = document.getElementById('receiver-email');
const saveConfigBtn = document.getElementById('save-config-btn');
const configMsg = document.getElementById('config-msg');

// Toggle Source
switchSourceBtn.addEventListener('click', async () => {
    try {
        const res = await fetch('/switch_source?source=webcam', { method: 'POST' });
        if (res.ok) {
            uploadMsg.innerText = "Switched to Webcam";
        }
    } catch (e) { console.error(e); }
});

// Upload Logic
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

// Email Config
saveConfigBtn.addEventListener('click', async () => {
    const sender = senderInput.value;
    const password = passInput.value;
    const receiver = receiverInput.value;

    if (!sender || !password || !receiver) {
        configMsg.innerText = "Please fill all fields";
        return;
    }

    configMsg.innerText = "Saving...";

    try {
        const res = await fetch('/configure_email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sender, password, receiver })
        });
        const data = await res.json();
        configMsg.innerText = data.message;
        configMsg.style.color = "#26a69a";
    } catch (e) {
        configMsg.innerText = "Failed";
        configMsg.style.color = "#ff4444";
    }
});
