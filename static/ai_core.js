// static/ai_core.js

/**
 * 1. DEFINE FUNCTIONS FIRST (Hoisting Safety)
 */
// Global state for LangGraph Memory
let currentThreadId = null;
let savedHistoryData = [];
function checkAIAccess() {
    console.log("Running checkAIAccess...");
    const apiKey = localStorage.getItem('ai_api_key');
    const overlays = document.querySelectorAll('.ai-lock-overlay');
    const chatInput = document.getElementById('ai-input'); 
    const sendBtn = document.getElementById('send-btn');   

    if (!apiKey) {
        overlays.forEach(overlay => {
            overlay.classList.remove('d-none');
            overlay.classList.add('d-flex');
        });
        if (chatInput) chatInput.disabled = true;
        if (sendBtn) sendBtn.disabled = true;
    } else {
        overlays.forEach(overlay => {
            overlay.classList.remove('d-flex');
            overlay.classList.add('d-none');
        });
        if (chatInput) chatInput.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
    }
}

function muteAiModal() {
    console.log("Muting AI Modal...");
    localStorage.setItem('mute_api_modal', 'true');
    const modalElement = document.getElementById('aiSettingsModal');
    if (modalElement) {
        const modalInstance = bootstrap.Modal.getOrCreateInstance(modalElement);
        modalInstance.hide();
    }
}

async function saveAIToLocalStorage() {
    const provider = document.getElementById('ai-provider').value;
    const apiKey = document.getElementById('ai-api-key').value.trim();

    if (!apiKey) { 
        alert("Please enter a valid API key."); 
        return; 
    }

    // --- NEW: Send the real key to the Backend/Redis ---
    try {
        const response = await fetch('/api/set-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey, provider: provider })
        });

        if (!response.ok) throw new Error('Failed to save key to server');

        // --- SUCCESS: Now fool the frontend ---
        // We store a "dummy" string so checkAIAccess() still works
        localStorage.setItem('ai_provider', provider);
        localStorage.setItem('ai_api_key', "PROTECTED_ON_SERVER"); 
        localStorage.removeItem('mute_ai_modal'); 

        const modalElement = document.getElementById('aiSettingsModal');
        const modalInstance = bootstrap.Modal.getInstance(modalElement);
        if (modalInstance) modalInstance.hide();
        
        document.getElementById('ai-api-key').value = '';
        checkAIAccess(); 
        alert("API Key secured and saved!");

    } catch (error) {
        console.error(error);
        alert("Could not save key to server. Please try again.");
    }
}
/**
 * 2. RUN THE GATEKEEPER LAST
 */
document.addEventListener("DOMContentLoaded", function() {
    const hasKey = localStorage.getItem('ai_api_key');
    const isMuted = localStorage.getItem('mute_api_modal');

    // Visual Lock check
    checkAIAccess(); 

    // Auto-pop logic
    if (!hasKey && isMuted !== 'true') {
        const modalElement = document.getElementById('aiSettingsModal');
        if (modalElement) {
            const aiModal = bootstrap.Modal.getOrCreateInstance(modalElement);
            aiModal.show();
        }
    }
});

// For updateKeyUI and openAIEditModal, keep them at the bottom
function updateKeyUI() {
    const provider = document.getElementById('ai-provider').value;
    const keyInput = document.getElementById('ai-api-key');
    if (keyInput) {
        keyInput.placeholder = provider === 'gemini' ? 'AIzaSy...' : 'sk-proj-...';
    }
}

function openAIEditModal() {
    const currentProvider = localStorage.getItem('ai_provider');
    if (currentProvider) {
        document.getElementById('ai-provider').value = currentProvider;
        updateKeyUI(); 
    }
    const modalElement = document.getElementById('aiSettingsModal');
    const aiModal = bootstrap.Modal.getOrCreateInstance(modalElement);
    aiModal.show();
}