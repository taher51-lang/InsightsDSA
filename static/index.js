const handleLogin = async () => {
    const user_name = document.getElementById("user_name").value
    const user_pass = document.getElementById("user_pass").value
    console.log(user_name)
    console.log(user_pass)
    
    const response = await apiCall("/login", {
        method: "POST",
        headers: { "Content-Type": "application/JSON" },
        body: JSON.stringify({
            username: user_name,
            userpass: user_pass
        })
    })
    data = await response.json()
    console.log(data)
    if (response.ok) {
        sessionStorage.setItem("name", data['name'])
        setTimeout(() => {
            window.location.href = "/dashboard";
        }, 500);
    } else {
        alert(data.error)
        // document.getElementById("msg").innerText = data["message"];
        // document.getElementById("msg").style.color = "red";
    }
}
const btn = document.getElementById('loginbtn');
console.log(btn)
// console.log(document.getElementById("username").value)
// 2. Add the "Ear" (Listener)
if (btn) {
    btn.addEventListener('click', handleLogin);
}
// Registration
const handleRegistration = async () => {
    const user_name = document.getElementById("username").value
    const user_pass = document.getElementById("userpass").value
    const name = document.getElementById("name_first").value
    const email = document.getElementById("email").value
    console.log(user_name)
    console.log(user_pass)
    const response = await apiCall("/register", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            username: user_name,
            userpass: user_pass,
            email: email,
            name:name
        })
    }
    )
    data = await response.json()
    console.log(data)
    if (response.ok) {
        sessionStorage.setItem("name",name)

        // loadOverlay()
        window.location.href = "/dashboard";
    } else {
        alert(data.error);
        // document.getElementById("msg").innerText = data["message"];
        // document.getElementById("msg").style.color = "red";
    }
}
const regbtm = document.getElementById('regbtn');
// 2. Add the "Ear" (Listener)
if (regbtm) {
    regbtm.addEventListener('click', handleRegistration);
}
const loadOverlay = () => {
    document.getElementById("loading-overlay").style.display = "flex"
}
document.addEventListener("DOMContentLoaded", () => {
    const nameInput = document.getElementById('username');
    const emailInput = document.getElementById('email');
    const passInput = document.getElementById('userpass');
    const regBtn = document.getElementById('regbtn');

    // Regex Patterns
    const nameRegex = /[a-zA-Z0-9\s]{3,}/; // At least 3 letters,
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const passRegex = /^(?=.*[A-Za-z])(?=.*\d).{6,}$/;    // --- 1. NAME VALIDATION ---
    nameInput.addEventListener('input', () => {
        const err = document.getElementById('name-error');
        if (nameRegex.test(nameInput.value.trim())) {
            nameInput.classList.remove('is-invalid');
            nameInput.classList.add('is-valid');
            err.style.display = 'none';
        } else {
            nameInput.classList.add('is-invalid');
            err.style.display = 'block';
        }
    });

    // --- 2. EMAIL VALIDATION ---
    emailInput.addEventListener('input', () => {
        const err = document.getElementById('email-error');
        if (emailRegex.test(emailInput.value.trim())) {
            emailInput.classList.remove('is-invalid');
            emailInput.classList.add('is-valid');
            err.style.display = 'none';
        } else {
            emailInput.classList.add('is-invalid');
            err.style.display = 'block';
        }
    });

    // --- 3. PASSWORD STRENGTH METER ---
    passInput.addEventListener('input', () => {
        const val = passInput.value;
        const bar = document.getElementById('pass-strength-bar');
        const err = document.getElementById('pass-error');
        let strength = 0;

        if (val.length > 6) strength++; // Good length
        if (val.match(/[A-Z]/)) strength++; // Has Uppercase
        if (val.match(/[0-9]/)) strength++; // Has Number
        // if (val.match(/[@$!%*?&]/)) strength++; // Has Special Char

        // Update Bar Color
        if (strength <= 1) { bar.style.width = '33%'; bar.className = 'progress-bar bg-danger'; }
        else if (strength === 2) { bar.style.width = '66%'; bar.className = 'progress-bar bg-warning'; }
        // else if (strength === 3) { bar.style.width = '75%'; bar.className = 'progress-bar bg-info'; }
        else { bar.style.width = '100%'; bar.className = 'progress-bar bg-success'; }

        // Validate Regex for Final Submission
        if (passRegex.test(val)) {
            passInput.classList.remove('is-invalid');
            passInput.classList.add('is-valid');
            err.style.display = 'none';
        } else {
            passInput.classList.add('is-invalid');
            err.style.display = 'block';
        }
    });

    // --- 4. SUBMIT BUTTON CLICK ---
    regBtn.addEventListener('click', async () => {
        const name = nameInput.value.trim();
        const email = emailInput.value.trim();
        const password = passInput.value.trim();

        // Final Check before sending to Backend
        if (!nameRegex.test(name) || !emailRegex.test(email) || !passRegex.test(password)) {
            alert("Please fix the errors in the form before signing up!");
            return;
        }

        // Send to Python Backend
        try {
            const response = await fetch('/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `name=${encodeURIComponent(name)}&email=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`
            });

            if (response.redirected) {
                window.location.href = response.url;
            } else {
                const data = await response.json();
                if (data.error) alert(data.error);
            }
        } catch (error) {
            console.error("Signup Error:", error);
        }
    });
});
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