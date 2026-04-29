const BASE_URL = "http://18.145.174.39";

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
    const useremail = document.getElementById("reg_useremail").value;
    const password = document.getElementById("reg_userpassword").value;

    try {
        const res = await fetch(BASE_URL + "/api/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({"email": useremail,"password": password })
        });

        const data = await res.json();
        if (data.success) {
            alert("Register success!");
            window.location.href = '/login.html';
        } else {
            alert("Register failed: " + data.message);
            return;
        }
    } catch (err) {
        console.error(err);
        alert("Network error, please try again later")
    }
}

// login
async function login() {
    const email = document.getElementById("useremail").value;
    const password = document.getElementById("userpassword").value;

    try {
        const res = await fetch(BASE_URL + "/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();
        if (data.success) {
            localStorage.setItem("token", data.data.token);
            localStorage.setItem("user_id", data.data.user_id);
            localStorage.setItem("username", email);
            alert("Login Success!");
            window.location.herf = '/index.html';
        }
        else {
            alert("Login Failed: " + data.message);
            return;
        }

        // save JWT
        // saveToken(data.token);
        // localStorage.setItem("username", email)
        // showMsg("Login success!");
        setTimeout(() => location.href = "index.html", 1000);
    } catch (err) {
        console.error(err);
        alert("Network error, please try again later");
    }
}