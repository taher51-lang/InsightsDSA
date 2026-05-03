document.addEventListener("DOMContentLoaded", () => {
    // 1. Set Name
    const name = sessionStorage.getItem('name');
    const nameEl = document.getElementById("name"); // Ensure this ID exists in HTML
    if (name && nameEl) {
        nameEl.innerText = `Hello ${name}!!`;
    }

    // 2. Fetch Stats
    fetch('/api/user_stats')
        .then(response => {
            if (!response.ok) throw new Error("Network response was not ok");
            return response.json();
        })
        .then(data => {
            console.log("Stats Received:", data); // Debugging

            // Update Total Solved
            const solvedEl = document.getElementById("solved-count");
            if (solvedEl) solvedEl.innerText = data.total_solved;

            // Update Streak
            const streakEl = document.getElementById("streak-count");
            if (streakEl) streakEl.innerText = data.streak;
        })
        .catch(error => console.error("Error fetching stats:", error));
});

// Helper for Roadmap
function openRoadmap(){
    window.location.href = "/journey";
}
document.addEventListener("DOMContentLoaded", function() {
    // Initialize all tooltips on the page
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});
// Function 1: Make the UI dynamic so it feels like a premium app