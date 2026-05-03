let selectedFiles = [];
const BASE_URL = "http://18.145.174.39";

window.onload = function () {
    if (!localStorage.getItem("token")) {
        location.href = "/login.html";
        return;
    }
    const token = localStorage.getItem("token");
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


function getFileSuffix(filename) {
    return filename.split('.').pop().toLowerCase();
}

// Batch upload
async function startUpload() {
    if (selectedFiles.length === 0) {
        alert("Can't upload empty file");
        return;
    }

    const token = localStorage.getItem("token");
    const IMAGE_SUFFIX = ['jpg', 'jpeg', 'png'];
    const ZIP_SUFFIX = ['zip'];
    const btn = document.getElementById("uploadBtn");

    btn.disabled = true;
    btn.innerText = "Uploading ...";

    try{
        for (const file of selectedFiles){
            const suffix = getFileSuffix(file.name);
            if(IMAGE_SUFFIX.includes(suffix)){
                await uploadSingle(file, token);
            }else if (ZIP_SUFFIX.includes(suffix)){
                await uploadZip(file, token);
            }else{
                alert(`Unsupported file format: ${file.name}`);
            }
        }

        alert("Upload Complete");
        selectedFiles = [];
        renderFileList();
    } catch(err){
        console.error(err);
        alert("Upload Failed: Network error ...")
    }

    selectedFiles = [];
    btn.disabled = false;
    btn.innerText = "Upload";
    renderFileList();
}


async function uploadSingle(file, token) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(BASE_URL + "/api/images/upload", {
        method: "POST",
        headers: {
            "Authorization": `Bearer ${token}`
        },
        body: formData
    });
    const data = await res.json();
    if(!data.success) {
        throw new Error(data.message || "Upload Failed");
    }
}


async function uploadZip(file, token) {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(BASE_URL + "/api/images/upload-zip", {
        method: "POST",
        headers: {
            "Authorization": `Bearer ${token}`
        },
        body: formData
    });
    const data = await res.json();
    if (!data.success) {
        throw new Error(data.message || "Upload Failed");
    }
}

// Nvigation
function goHome() {
    location.href = "/index.html";
}
function goUpload() {
    location.href = "/upload.html";
}
function goDownload() {
    location.href = "/download.html";
}
function goMapView() {  location.href = "/mapView.html";  }
function logout() {
    localStorage.clear();
    location.href = "/login.html";
}