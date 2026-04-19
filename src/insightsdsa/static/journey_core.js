document.addEventListener('DOMContentLoaded', async () => {
    const timeline = document.getElementById('journey-timeline');
    
    try {
        const response = await fetch('/api/user-journey');
        const data = await response.json();

        if (data.length === 0) {
            timeline.innerHTML = '<div class="text-center py-5 text-muted">Begin your first session to generate a timeline.</div>';
            return;
        }

        timeline.innerHTML = data.map(item => `
            <div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="premium-card">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div class="icon-wrapper">
                            <i class="bi ${item.icon}"></i>
                        </div>
                        <span class="date-text">${new Date(item.achieved_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}</span>
                    </div>
                    <h5 class="fw-bold mb-1">${item.title}</h5>
                    <p class="text-muted small mb-3">You've successfully integrated ${item.count} core patterns from this module into your long-term memory.</p>
                    <div class="d-flex gap-2">
                        <span class="stat-badge"><i class="bi bi-check2-circle me-1"></i>Mastered</span>
                        <span class="stat-badge"><i class="bi bi-lightning-charge me-1"></i>${item.count} Solves</span>
                    </div>
                </div>
            </div>
        `).join('');

    } catch (err) {
        console.error("Timeline Load Error:", err);
    }
});