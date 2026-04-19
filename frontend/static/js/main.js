// Test data
const photos = [
    {
        id: 1,
        url: "https://picsum.photos/seed/cat1/600/600",
        label: "cat",
        name: "test1",
        lat: 39.9,
        lng: 116.3
    },
    {
        id: 2,
        url: "https://picsum.photos/seed/dog1/600/600",
        label: "dog",
        name: "",
        lat: 39.91,
        lng: 116.31
    }
];

// Login check
window.onload = () => {
    if (!localStorage.getItem("token")) {
        location.href = "../pages/index.html";
    }

    const username = localStorage.getItem("username");
    if(!username) username = "User";
    var node = document.getElementById("userName")
    node.textContent = "Hello, " + username
    
    renderPhotos(photos);
};

// Albums
function renderPhotos(list) {
    const album = document.getElementById("album");
    album.innerHTML = "";
    list.forEach(p => {
        const item = document.createElement("div");
        item.className = "photo-item";
        item.innerHTML = `<img src="${p.url}" alt="photo">`;
        item.onclick = () => openDetail(p.id);
        album.appendChild(item);
    });
}

// Details
function openDetail(id) {
    localStorage.setItem("currentPhotoId", id);
    window.location.href ="detail.html";
}

// serach
function searchPhotos() {
    const key = document.getElementById("searchInput").value.toLowerCase();
    // Needs to replace this! Search by location, name, or label.
    const filtered = photos.filter(p => p.name.toLowerCase().includes(key));
    renderPhotos(filtered);
}

// Main page
function goHome() {
    document.getElementById("searchInput").value = "";
    renderPhotos(photos);
}

// Logout
function logout() {
    localStorage.removeItem("token");
    location.href = "../pages/login.html";
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