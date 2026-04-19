// test image
const mockPhotos = [
    { id: 1, url: "https://picsum.photos/seed/photo1/400/400", name: "photo1.jpg" },
    { id: 2, url: "https://picsum.photos/seed/photo2/400/400", name: "photo2.jpg" },
    { id: 3, url: "https://picsum.photos/seed/photo3/400/400", name: "photo3.jpg" },
    { id: 4, url: "https://picsum.photos/seed/photo4/400/400", name: "photo4.jpg" },
    { id: 5, url: "https://picsum.photos/seed/photo5/400/400", name: "photo5.jpg" },
    { id: 6, url: "https://picsum.photos/seed/photo6/400/400", name: "photo6.jpg" },
];

window.onload = function () {
    if (!localStorage.getItem("token")) {
        location.href = "pages/login.html";
        return;
    }

    const username = localStorage.getItem("username") || "User";
    document.getElementById("userName").innerText = "Hello, " + username;

    renderImageGrid();
};

function renderImageGrid() {
    const grid = document.getElementById("imageGrid");
    grid.innerHTML = "";

    mockPhotos.forEach(photo => {
        const card = document.createElement("div");
        card.className = "image-card";
        card.dataset.id = photo.id;
        card.dataset.url = photo.url;
        card.dataset.name = photo.name;

        card.innerHTML = `
            <div class="checkbox-wrapper">
                <input type="checkbox" class="photo-checkbox">
                <span class="checkmark">✓</span>
            </div>
            <img src="${photo.url}" alt="${photo.name}">
        `;

        card.addEventListener("click", (e) => {
            const checkbox = card.querySelector(".photo-checkbox");
            checkbox.checked = !checkbox.checked;
            card.classList.toggle("selected", checkbox.checked);
        });

        grid.appendChild(card);
    });
}

function getSelectedPhotos() {
    const selected = [];
    document.querySelectorAll(".image-card.selected").forEach(card => {
        selected.push({
            id: card.dataset.id,
            url: card.dataset.url,
            name: card.dataset.name
        });
    });
    return selected;
}

function BatchDownload() {
    const selected = getSelectedPhotos();

    if (selected.length === 0) {
        alert("Empty !");
        return;
    }

    // Replace here. Call download function
    /*
    fetch("/your-backend-api/download/batch", {
        method: "POST",
        body: JSON.stringify({ ids: selected.map(p => p.id) })
    })
    .then(res => res.blob())
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "album_files.zip";
        a.click();
        window.URL.revokeObjectURL(url);
    });
    */

    // Replace here, simulate download(open the file directly)
    selected.forEach(photo => {
        const link = document.createElement("a");
        link.href = photo.url;
        link.download = photo.name;
        link.target = "_blank";
        link.click();
    });
}

// Navigation
function goHome() { location.href = "index.html"; }
function goUpload() { location.href = "upload.html"; }
function goDownload() { location.href = "download.html"; }
function logout() {
    localStorage.clear();
    location.href = "pages/login.html";
}