const BASE_URL = "http://localhost:5000/api/auth";

// swith between sheets
function switchToRegister() {
    document.getElementById("loginBox").classList.add("hidden");
    document.getElementById("registerBox").classList.remove("hidden");
    showMsg("");
}

function switchToLogin() {
    document.getElementById("registerBox").classList.add("hidden");
    document.getElementById("loginBox").classList.remove("hidden");
    showMsg("");
}

// hints
function showMsg(text) {
    document.getElementById("msg").innerText = text;
}

// save token
function saveToken(token) {
    localStorage.setItem("token", token);
}

// register
async function register() {
    const username = document.getElementById("reg_username").value;
    const password = document.getElementById("reg_userpassword").value;

    try {
        const res = await fetch(`${BASE_URL}/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.msg || "Register failed");

        showMsg("Register success! Please login.");
        switchToLogin();
    } catch (err) {
        showMsg(err.message);
    }
}

// login
async function login() {
    const username = document.getElementById("username").value;
    const password = document.getElementById("userpassword").value;

    try {
        const res = await fetch(`${BASE_URL}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.msg || "Login failed");

        // save JWT
        saveToken(data.token);
        showMsg("Login success!");
        setTimeout(() => location.href = "index.html", 1000);
    } catch (err) {
        showMsg(err.message);
    }
}