document.addEventListener("DOMContentLoaded", () => {
    // 1. Extract Concept ID from URL
    const urlParts = window.location.pathname.split('/');
    const conceptId = urlParts[urlParts.length - 1];

    // 2. Fetch Questions from API
    fetch(`/api/get_questions/${conceptId}`)
        .then(res => res.json())
        .then(questions => {
            const tableBody = document.getElementById("questions-table-body");
            if (!tableBody) return;

            tableBody.innerHTML = ""; // Clear loading state

            questions.forEach(q => {
                const row = document.createElement("tr");
                row.className = "align-middle mb-2";

                // New Row HTML: The 'Solve' button is now a direct link!
                row.innerHTML = `
                    <td class="ps-4" style="width: 60px;">
                        ${q.is_solved
                        ? '<div class="bg-success-subtle p-2 rounded-circle text-center" style="width:35px; height:35px;"><i class="bi bi-check2 text-success fw-bold"></i></div>'
                        : '<div class="bg-light p-2 rounded-circle text-center" style="width:35px; height:35px;"><i class="bi bi-circle text-secondary"></i></div>'}
                    </td>
                    <td>
                        <div class="fw-bold text-dark mb-0">${q.title}</div>
                        <a href="${q.link}" target="_blank" class="text-primary small text-decoration-none" style="font-size: 0.8rem;">
                            View on LeetCode <i class="bi bi-box-arrow-up-right ms-1"></i>
                        </a>
                    </td>
                    <td>
                        <span class="badge rounded-pill ${getBadgeClass(q.difficulty)} px-3 py-2">
                            ${q.difficulty}
                        </span>
                    </td>
                    
                    <td class="text-end pe-4">
                        <a href="/question/${q.id}" class="btn btn-sm btn-dark rounded-pill px-4 py-2 fw-medium shadow-sm transition-hover">
                            Solve Problem <i class="bi bi-arrow-right-short ms-1 fs-5 align-middle"></i>
                        </a>
                    </td>
                `;
                tableBody.appendChild(row);
            });
        })
        .catch(err => {
            console.error("Error fetching questions:", err);
            const tableBody = document.getElementById("questions-table-body");
            if (tableBody) {
                tableBody.innerHTML = `<tr><td colspan="4" class="text-center py-5 text-danger">Failed to load questions. Please try again.</td></tr>`;
            }
        });
});

// Helper function for styling difficulty badges
function getBadgeClass(diff) {
    if (diff === 'Easy') return 'bg-success-subtle text-success border border-success';
    if (diff === 'Medium') return 'bg-warning-subtle text-warning-emphasis border border-warning';
    if (diff === 'Hard') return 'bg-danger-subtle text-danger border border-danger';
    return 'bg-secondary-subtle border border-secondary';
}