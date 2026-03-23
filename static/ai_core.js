// static/ai_core.js

document.addEventListener("DOMContentLoaded", function() {
    checkAIAccess(); // Run gatekeeper on page load
});

function checkAIAccess() {
    const apiKey = localStorage.getItem('ai_api_key');
    
    // Find EVERY locked section on the current page
    const overlays = document.querySelectorAll('.ai-lock-overlay');
    
    // Fallbacks for the workspace chat (will safely be null on profile)
    const chatInput = document.getElementById('ai-input'); 
    const sendBtn = document.getElementById('send-btn');   

    if (!apiKey) {
        // 1. LOCK ALL RESTRICTED UI ZONES
        overlays.forEach(overlay => {
            overlay.classList.remove('d-none');
            overlay.classList.add('d-flex');
        });
        
        if (chatInput) chatInput.disabled = true;
        if (sendBtn) sendBtn.disabled = true;

        // 2. AUTO-POP THE MODAL
        const modalElement = document.getElementById('aiSettingsModal');
        if (modalElement) {
            const aiModal = bootstrap.Modal.getOrCreateInstance(modalElement);
            aiModal.show();
        }
    } else {
        // UNLOCK EVERYTHING
        overlays.forEach(overlay => {
            overlay.classList.remove('d-flex');
            overlay.classList.add('d-none');
        });
        
        if (chatInput) chatInput.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
    }
}
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
    const aiModal = new bootstrap.Modal(document.getElementById('aiSettingsModal'));
    aiModal.show();
}

function saveAIToLocalStorage() {
    const provider = document.getElementById('ai-provider').value;
    const apiKey = document.getElementById('ai-api-key').value.trim();

    if (!apiKey) { alert("Please enter a valid API key."); return; }

    localStorage.setItem('ai_provider', provider);
    localStorage.setItem('ai_api_key', apiKey);

    const modalElement = document.getElementById('aiSettingsModal');
    const modalInstance = bootstrap.Modal.getInstance(modalElement);
    if (modalInstance) modalInstance.hide();
    
    document.getElementById('ai-api-key').value = '';
    
    checkAIAccess(); // Instantly update locks across the page
}