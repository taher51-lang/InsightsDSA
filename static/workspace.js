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
    } catch (err) {
        console.error("Error:", err);
        titleEl.innerText = "Error Loading Question";
    }
    // 2. Toggle Solve Logic
    solveBtn.onclick = async () => {
        solveBtn.disabled = true;
        try {
            const res = await fetch('/api/toggle_solve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question_id: qId })
            });
            const result = await res.json();
            updateSolveUI(result.action === 'solved');
        } catch (e) {
            console.error(e);
        } finally {
            solveBtn.disabled = false;
        }
    };

    // 3. AI Chat Logic
    async function askAI() {
        const text = aiInput.value.trim();
        if (!text) return;

        addMsg("user", text);
        aiInput.value = "";
        
        const loaderId = "loader-" + Date.now();
        addMsg("ai", '<div class="spinner-border spinner-border-sm text-primary"></div> Analyzing...', loaderId);

        try {
            const res = await fetch('/api/ask_ai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question_id: qId, query: text })
            });
            const data = await res.json();
            document.getElementById(loaderId).remove();
            addMsg("ai", data.answer);
        } catch (e) {
            document.getElementById(loaderId).innerText = "Tutor is currently offline.";
        }
    }

    // Helper functions
    function updateSolveUI(isSolved) {
        if (isSolved) {
            solveBtn.className = "btn btn-sm btn-outline-secondary rounded-pill px-4 py-2";
            solveBtn.innerHTML = '<i class="bi bi-arrow-counterclockwise me-1"></i> Reset Progress';
        } else {
            solveBtn.className = "btn btn-sm btn-success rounded-pill px-4 py-2";
            solveBtn.innerHTML = '<i class="bi bi-check2-circle me-1"></i> Mark Solved';
        }
    }

    function addMsg(role, content, id = null) {
        const div = document.createElement('div');
        div.className = `p-3 rounded-4 mb-2 shadow-sm ${role === 'user' ? 'bg-primary text-white align-self-end w-75' : 'bg-dark border border-secondary text-light w-85'}`;
        if (id) div.id = id;
        div.innerHTML = content;
        chatFlow.appendChild(div);
        chatFlow.scrollTop = chatFlow.scrollHeight;
    }

    sendBtn.onclick = askAI;
    aiInput.onkeypress = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); askAI(); } };
});