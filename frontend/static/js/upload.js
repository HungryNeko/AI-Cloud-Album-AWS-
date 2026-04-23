let selectedFiles = [];

window.onload = function () {
    if (!localStorage.getItem("token")) {
        location.href = "/pages/login.html";
        return;
    }
    const username = localStorage.getItem("username") || "User";
    document.getElementById("userName").innerText = "Hello, " + username;
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("fileInput");

    dropzone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
        addFilesToList(e.target.files);
    });
};

// Add file to queue
function addFilesToList(files) {
    for (let file of files) {
        if (!selectedFiles.find(f => f.name === file.name)) {
            selectedFiles.push(file);
        }
    }
    renderFileList();
}

function renderFileList() {
    const listEl = document.getElementById("fileQueue");
    listEl.innerHTML = "";
    selectedFiles.forEach((file, index) => {
        const item = document.createElement("div");
        item.className = "file-item";
        item.innerHTML = `
            <span>${file.name}</span>
            <button onclick="removeFile(${index})">Delete</button>
        `;
        listEl.appendChild(item);
    });
}

// Remove file from queue
function removeFile(index) {
    selectedFiles.splice(index, 1);
    renderFileList();
}

// Batch upload
async function startUpload() {
    if (selectedFiles.length === 0) {
        alert("Can't upload empty file");
        return;
    }
    // Need replacement, call backend upload
    for (let file of selectedFiles) {
    let url = URL.createObjectURL(file);
    await DataService.addPhoto({
      url: url,
      label: "unknown",
      lat: 39.9,
      lng: 116.3,
      name: ""
    });
  }

    alert(`Uploading ${selectedFiles.length} File`);
    selectedFiles = [];
    renderFileList();
}

// Nvigation
function goHome() {
    location.href = "/pages/index.html";
}
function goUpload() {
    location.href = "/pages/upload.html";
}
function goDownload() {
    location.href = "/pages/download.html"
}
function logout() {
    localStorage.clear();
    location.href = "/pages/login.html";
}