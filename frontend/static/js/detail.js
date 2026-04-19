const photos = [
    { id:1, url:"https://picsum.photos/seed/cat1/600/600", label:"cat", name:"", lat:37.7749, lng:-122.4194 },
    { id:2, url:"https://picsum.photos/seed/dog1/600/600", label:"berry", name:"", lat:37.7749, lng:-122.4194 }
];

async function getLocation(lat, lng) {
  try {
    const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=10&accept-language=en`);
    const data = await res.json();
    const addr = data.address || {};

    const country = addr.country || "";
    const state = addr.state || addr.province || "";
    const city = addr.city || addr.town || addr.county || "";
    const district = addr.suburb || addr.village || addr.neighbourhood || "";

    return { country, state, city, district };
  } catch (e) {
    return { country: "", state: "", city: "", district: "" };
  }
}

window.onload = () => {
    if (!localStorage.getItem("token")) {
        location.href = "pages/login.html";
    }
    const username = localStorage.getItem("username") || "User";
    document.getElementById("userName").innerText = `Hello, ${username}`;
    const id = Number(localStorage.getItem("currentPhotoId"));
    const photo = photos.find(p => p.id === id);
    if (!photo) {
        alert("Image don't exist");
        location.href = "index.html";
        return;
    }
    document.getElementById("bigImg").src = photo.url;

    const have_names = ['dog', 'cat', 'man', 'women'];
    const needs_follow_up = have_names.includes(photo.label.toLocaleLowerCase());
    const prompt = document.getElementById("promptText");
    const text_input = document.getElementById("nameInput");
    const btn_save = document.querySelector(".save-btn")
    if(needs_follow_up) {
        prompt.innerText = `Do you know this ${photo.label}?`;
        prompt.style.display = "block";
        text_input.style.display = "block";
        btn_save.style.display = "block";
    } else {
        prompt.style.display = "none";
        text_input.style.display = "none";
        btn_save.style.display = "none";
    }

    load_Map_Location(photo)
};

function saveName() {
    const name = document.getElementById("nameInput").value.trim();
    if (!name) {
        alert("Please Enter name");
        return;
    }
    // Needs to replace this, save back to database. Save to image's name attribute.
    alert(`Image named as: ${name}`);
}

function goHome() {
    location.href = "index.html";
}
function goUpload() {
    location.href = "upload.html";
}
function goDownload() {
    location.href = "download.html"
}
function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    location.href = "pages/login.html";
}

async function load_Map_Location(photo) {
    const loc = await getLocation(photo.lat, photo.lng);
    const locationStr = `${loc.district} ${loc.city} ${loc.state} ${loc.country}`;
    document.getElementById("locationText").innerText = locationStr;

    
    const map = L.map('map').setView([photo.lat, photo.lng], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    L.marker([photo.lat, photo.lng]).addTo(map);
}