const captionElement = document.getElementById('live-caption');
const languageSelect = document.getElementById('language-select');
const speakBtn = document.getElementById('speak-btn');
const snapshotBtn = document.getElementById('snapshot-btn');
const snapshotStatus = document.getElementById('snapshot-status');

let currentOriginalCaption = "";
let currentDisplayCaption = "";
let isSpeaking = false;

async function updateCaption() {
    try {
        // 1. Get original caption
        const response = await fetch('/stats');
        const data = await response.json();
        const newCaption = data.caption;

        if (newCaption && newCaption !== currentOriginalCaption) {
            currentOriginalCaption = newCaption;

            // 2. Translate if needed
            const targetLang = languageSelect.value;
            if (targetLang !== 'en') {
                const transRes = await fetch('/translate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: newCaption, target_lang: targetLang })
                });
                const transData = await transRes.json();
                currentDisplayCaption = transData.translated_text;
            } else {
                currentDisplayCaption = newCaption;
            }

            // 3. Update UI with fade effect
            captionElement.style.opacity = '0.5';
            setTimeout(() => {
                captionElement.innerText = currentDisplayCaption;
                captionElement.style.opacity = '1';
            }, 200);
        }
    } catch (error) {
        console.error("Error fetching caption:", error);
    }
}

// Poll every 800ms (slightly slower to allow for translation API)
setInterval(updateCaption, 800);

// Handle Language Change immediately
languageSelect.addEventListener('change', () => {
    // Reset to force re-translation on next poll or immediate trigger
    currentOriginalCaption = "";
    updateCaption();
});

// TTS Logic
speakBtn.addEventListener('click', async () => {
    if (!currentDisplayCaption || isSpeaking) return;

    speakBtn.classList.add('active'); // Visual feedback
    isSpeaking = true;
    const originalText = speakBtn.innerHTML;
    speakBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';

    try {
        const res = await fetch('/speak', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: currentDisplayCaption,
                lang: languageSelect.value
            })
        });

        if (res.ok) {
            const blob = await res.blob();
            const audio = new Audio(URL.createObjectURL(blob));
            audio.onended = () => {
                isSpeaking = false;
                speakBtn.classList.remove('active');
                speakBtn.innerHTML = originalText;
            };
            audio.play();
        } else {
            throw new Error("TTS Failed");
        }
    } catch (e) {
        console.error(e);
        isSpeaking = false;
        speakBtn.classList.remove('active');
        speakBtn.innerHTML = originalText;
    }
});

// Snapshot Logic
snapshotBtn.addEventListener('click', async () => {
    snapshotBtn.classList.add('clicked');
    setTimeout(() => snapshotBtn.classList.remove('clicked'), 200);

    try {
        const res = await fetch('/snapshot', { method: 'POST' });
        const data = await res.json();

        if (data.status === 'success') {
            snapshotStatus.innerText = "Saved";
            setTimeout(() => { snapshotStatus.innerText = ""; }, 2000);
        }
    } catch (e) {
        console.error(e);
    }
});
