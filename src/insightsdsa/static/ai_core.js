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
        const response = await apiCall('/api/set-key', {
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
        // alert("API Key secured and saved!");

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
function triggerErrorUI(status) {
    const modalEl = document.getElementById('aiErrorModal');
    if (!modalEl) return; // Safety check

    const title = document.getElementById('error-modal-title');
    const msg = document.getElementById('error-modal-message');
    const actions = document.getElementById('error-modal-actions');
    const iconContainer = document.getElementById('error-modal-icon');
    
    const errorModal = bootstrap.Modal.getOrCreateInstance(modalEl);

    if (status === 429) {
        // --- CASE: RATE LIMIT (Soft Warning) ---
        title.innerText = "Limit Reached";
        msg.innerText = "You're sending requests faster than the AI can process. Please wait a minute before trying again.";
        iconContainer.className = "mb-4 d-inline-flex align-items-center justify-content-center bg-warning bg-opacity-10 text-warning";
        iconContainer.style.width = "60px"; iconContainer.style.height = "60px"; iconContainer.style.borderPadding = "15px";
        iconContainer.innerHTML = '<i class="bi bi-clock-history fs-3"></i>';
        
        actions.innerHTML = `
            <button type="button" class="btn btn-dark rounded-pill py-2 fw-bold" data-bs-dismiss="modal">Got it</button>
        `;
    } 
    else if (status === 402 || status === 401) {
        // --- CASE: QUOTA/AUTH (Hard Reset) ---
        const isQuota = (status === 402);
        title.innerText = isQuota ? "Quota Exhausted" : "Invalid API Key";
        msg.innerText = isQuota 
            ? "Your AI provider balance is empty. Please top up or provide a new key."
            : "Your API key is invalid or has expired. Please re-configure your engine.";
        
        iconContainer.className = "mb-4 d-inline-flex align-items-center justify-content-center bg-danger bg-opacity-10 text-danger";
        iconContainer.style.width = "60px"; iconContainer.style.height = "60px"; iconContainer.style.borderPadding = "15px";
        iconContainer.innerHTML = '<i class="bi bi-shield-lock-fill fs-3"></i>';
        
        actions.innerHTML = `
            <button type="button" class="btn btn-dark rounded-pill py-2 fw-bold" onclick="handleHardReset()">Update Configuration</button>
            <button type="button" class="btn btn-link text-muted text-decoration-none" data-bs-dismiss="modal">Cancel</button>
        `;

        // 🟢 CRITICAL: Sync with your existing locking logic
        localStorage.removeItem('ai_api_key');
        localStorage.removeItem('ai_provider');
        checkAIAccess(); // This immediately flips the 'Lock' overlay in the background
    }

    errorModal.show();
}

/**
 * Bridges the Error Modal to the Settings Modal
 */
function handleHardReset() {
    const errorModalEl = document.getElementById('aiErrorModal');
    const errorModalInstance = bootstrap.Modal.getInstance(errorModalEl);
    if (errorModalInstance) errorModalInstance.hide();
    
    // Call your existing function to open the settings
    openAIEditModal(); 
}
async function apiCall(url, options = {}) {
    // 1. Grab the token from the meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // 2. Automatically add the header to whatever options were passed
    const secureOptions = {
        ...options, // Keep existing method, body, etc.
        headers: {
            ...options.headers, // Keep existing headers
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/json'
        }
    };

    return fetch(url, secureOptions);
}