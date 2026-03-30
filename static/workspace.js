document.addEventListener("DOMContentLoaded", async () => {
    const qId = window.location.pathname.split('/').pop();
    // UI Elements
    const titleEl = document.getElementById('q-title');
    const diffEl = document.getElementById('q-diff');
    const descEl = document.getElementById('q-desc');
    const solveBtn = document.getElementById('solve-btn');
    const chatFlow = document.getElementById('chat-flow');
    const aiInput = document.getElementById('ai-input');
    const sendBtn = document.getElementById('send-btn');
    // Memory State Variables
    let currentThreadId = null;
    let savedHistoryData = [];
    const solveModalEl = document.getElementById('solveModal');
    const solveModal = new bootstrap.Modal(solveModalEl);
    const modalSubmitBtn = document.getElementById('modal-submit-btn');
    const timeInput = document.getElementById('modal-time-input');
    let selectedConf = null;
    const lcLink = document.getElementById('leetcode-link');
    // 1. Initial Load
    try {
        const res = await fetch(`/api/get_question_details/${qId}`);
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        titleEl.innerText = data.title;
        diffEl.innerText = data.difficulty;
        console.log(data.description)
        const desc = data.description;

// 1. Handle the empty state properly first
if (!desc) {
    descEl.innerHTML = "<span class='text-muted'>No description provided.</span>";
} else {
    // 2. Split right BEFORE the word "Example" (case-insensitive)
    // The (?=...) is a "Positive Lookahead". It splits the string but KEEPS the word "Example".
    const parts = desc.split(/(?=Example)/i);

    // 3. Rebuild the HTML. 
    // parts[0] is the main description. parts[1], parts[2] etc. are the examples.
    descEl.innerHTML = parts.map((part, index) => {
        if (index === 0) return part; // Return main description as-is
        
        // Wrap every example in a nice indented Bootstrap block
        return `<div class="mt-4 p-3 bg-light border-start border-primary border-4 rounded">
                    ${part}
                </div>`;
    }).join('');
}
        descEl.style.fontWeight="bold"
        lcLink.href = data.link;
        updateSolveUI(data.is_solved);
        // addMsg("ai", `I'm analyzing **${data.title}**. Need a strategy or a hint?`);
        // Remove Loader
        document.getElementById('loading-screen').style.display = 'none';
        document.getElementById('loading-screen').style.display = 'none';
        
        // --- ADD THIS LINE ---
        loadChatHistory();
    } catch (err) {
        console.error("Error:", err);
        titleEl.innerText = "Error Loading Question";
    }
    // 2. Toggle Solve Logic
   // --- Updated: High-Contrast Selection for White Theme ---
    document.querySelectorAll('.conf-option').forEach(btn => {
        btn.onclick = () => {
            // 1. Reset all buttons to the "Outline" state
            document.querySelectorAll('.conf-option').forEach(b => {
                b.classList.remove('active', 'btn-danger', 'btn-warning', 'btn-primary', 'btn-success', 'text-white');
            });

            // 2. Fill the clicked button with its specific semantic color
            const val = btn.dataset.val;
            if (val == 0) btn.classList.add('active', 'btn-danger', 'text-white');
            if (val == 3) btn.classList.add('active', 'btn-warning', 'text-white');
            if (val == 4) btn.classList.add('active', 'btn-primary', 'text-white');
            if (val == 5) btn.classList.add('active', 'btn-success', 'text-white');

            selectedConf = val; // Store 0, 3, 4, or 5
            validateModal();    // Enable the submit button
        };
    });
    function validateModal() {
        const timeVal = parseInt(timeInput.value);
        if (selectedConf !== null && timeVal > 0) {
            modalSubmitBtn.classList.remove('disabled');
            modalSubmitBtn.classList.replace('btn-light', 'btn-success');
        } else {
            modalSubmitBtn.classList.add('disabled');
        }
    }
    timeInput.oninput = validateModal;
    solveBtn.onclick = async () => {
        // BRANCHING LOGIC:
        // Only trigger modal if the button is Green (btn-success)
        if (solveBtn.classList.contains('btn-success')) {
            solveModal.show();
        } 
        // Trigger Reset confirmation if the button is Grey
        else {
            if (confirm("Resetting will wipe your SRS streak. History stays safe. Continue?")) {
                await runToggleSolve({ action: 'reset' });
            }
        }
    };
    // New modal submit
    modalSubmitBtn.onclick = async () => {
        if (modalSubmitBtn.classList.contains('disabled')) return;

        const minutes = timeInput.value
        console.log(minutes)
        const success = await runToggleSolve({
            action: 'solve',
            confidence: selectedConf,
            time_spent: minutes * 60 // Converting minutes to seconds for the DB
        });

        if (success) {
            // Simply hide the modal and stay on the current question page
            solveModal.hide();
        }
    };
    // New toggle solve api
    async function runToggleSolve(payload) {
        solveBtn.disabled = true;
        try {
            const res = await fetch('/api/toggle_solve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    question_id: qId,
                    ...payload 
                })
            });
            const result = await res.json();
            updateSolveUI(result.action === 'solved');
            return true;
        } catch (e) {
            console.error("Sync Error:", e);
            alert("Database sync failed. Check your connection.");
            return false;
        } finally {
            solveBtn.disabled = false;
        }
    }
    // --- NEW: Chat History Loader ---
    async function loadChatHistory() {
        try {
            const res = await fetch(`/api/chat_history/${qId}`);
            if (!res.ok) return; // No history found, do nothing

            const data = await res.json();
            savedHistoryData = data.history;

            if (savedHistoryData && savedHistoryData.length > 0) {
                // 1. Inject the Resume/Start Fresh Banner at the top of the chat
                const bannerHTML = `
                    <div id="history-banner" class="alert alert-secondary text-center shadow-sm mb-3" style="font-size: 0.9rem;">
                        <p class="mb-2 text-dark fw-bold">Past tutoring session found.</p>
                        <button id="btn-resume" class="btn btn-success btn-sm me-2">Resume Chat</button>
                        <button id="btn-fresh" class="btn btn-danger btn-sm">Start Fresh</button>
                    </div>
                `;
                chatFlow.insertAdjacentHTML('afterbegin', bannerHTML);

                // 2. Logic for "Resume Chat"
                document.getElementById('btn-resume').onclick = () => {
                    document.getElementById('history-banner').remove();
                    
                    // Grab the exact thread ID from the database
                    currentThreadId = savedHistoryData[0].thread_id;
                    
                    // Loop through and paint the old messages using YOUR addMsg function!
                    savedHistoryData.forEach(msg => {
                        // LangGraph saves it as 'assistant', but your UI expects 'ai'
                        const uiRole = msg.role === 'assistant' ? 'ai' : 'user';
                        
                        // Only parse Markdown if it's the AI speaking
                        const content = uiRole === 'ai' ? marked.parse(msg.content) : msg.content;
                        
                        addMsg(uiRole, content);
                    });
                };

                // 3. Logic for "Start Fresh"
                document.getElementById('btn-fresh').onclick = () => {
                    document.getElementById('history-banner').remove();
                    currentThreadId = crypto.randomUUID(); // Brand new timeline
                    console.log("Started fresh chat:", currentThreadId);
                };
            }
        } catch (err) {
            console.error("Failed to load history:", err);
        }
    }
    // 3. AI Chat Logic
    // 3. AI Chat Logic (Inside static/workspace.js)
    async function askAI() {
        const text = aiInput.value.trim();
        if (!text) return;

        // GRAB THE KEYS FROM THE CENTRAL VAULT
        const apiKey = localStorage.getItem('ai_api_key');
        const provider = localStorage.getItem('ai_provider');

        addMsg("user", text);
        aiInput.value = "";
        
        const loaderId = "loader-" + Date.now();
        addMsg("ai", '<div class="spinner-border spinner-border-sm text-primary"></div> Analyzing...', loaderId);
        if (!currentThreadId) {
            currentThreadId = crypto.randomUUID();
        }
        try {
            const res = await fetch('/api/ask_ai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    question_id: qId, 
                    query: text,
                    api_key: apiKey,     // Send to Flask
                    provider: provider, 
                    thread_id: currentThreadId  // Send to Flask
                })
            });
            const data = await res.json();
            
            // If the key is bad/exhausted, LangGraph will fail
            if (res.status === 401 || res.status === 403) {
                document.getElementById(loaderId).innerText = "Error: Invalid API Key. Please configure your engine.";
                localStorage.removeItem('ai_api_key'); // Delete the bad key
                checkAIAccess(); // Re-lock the UI
                openAIEditModal(); // Pop the settings open automatically
                return;
            }

            document.getElementById(loaderId).remove();
            addMsg("ai", marked.parse(data.answer));
        } catch (e) {
            document.getElementById(loaderId).innerText = "Tutor is currently offline.";
        }
    }
    // Helper functions
    function updateSolveUI(isSolved) {
        if (isSolved) {
            // Grey State (Already Solved)
            solveBtn.className = "btn btn-sm btn-outline-secondary rounded-pill px-4 py-2";
            solveBtn.innerHTML = '<i class="bi bi-arrow-counterclockwise me-1"></i> Reset Progress';
        } else {
            // Green State (Fresh Solve)
            solveBtn.className = "btn btn-sm btn-success rounded-pill px-4 py-2";
            solveBtn.innerHTML = '<i class="bi bi-check2-circle me-1"></i> Mark Solved';
        }
    }

    function addMsg(role, content, id = null) {
        const div = document.createElement('div');
        div.className = `p-3 rounded-4 mb-2 shadow-sm bg-white ${role === 'user' ? 'text-dark align-self-end w-75' : 'border border-secondary text-dark  w-85'}`;
        if (id) div.id = id;
        div.innerHTML = content;
        chatFlow.appendChild(div);
        chatFlow.scrollTop = chatFlow.scrollHeight;
    }

    sendBtn.onclick = askAI;
    aiInput.onkeypress = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); askAI(); } };
});
