// Test data
// const photos = [
//     {
//         id: 1,
//         url: "https://picsum.photos/seed/cat1/600/600",
//         label: "cat",
//         name: "test1",
//         lat: 39.9,
//         lng: 116.3
//     },
//     {
//         id: 2,
//         url: "https://picsum.photos/seed/dog1/600/600",
//         label: "dog",
//         name: "",
//         lat: 39.91,
//         lng: 116.31
//     }
// ];

let is_Deleting = false;
// Login check
window.onload = async function() {
    if (!localStorage.getItem("token")) {
        location.href = "/pages/login.html";
    }

    const username = localStorage.getItem("username");
    if(!username) username = "User";
    var node = document.getElementById("userName")
    node.textContent = "Hello, " + username
    localStorage.removeItem("photos");
    
    if (DataService && DataService.getPhotos) {
        DataService.getPhotos().then(data => {
            photos = data;
            renderPhotos(photos);
        }).catch(err => {
            console.error("Load data error:", err);
            alert("Unable to load images");
        });
    } else {
        alert("No data found");
    }
};

// Albums
// function renderPhotos(list) {
//     const album = document.getElementById("album");
//     album.innerHTML = "";
//     list.forEach(p => {
//         const item = document.createElement("div");
//         item.className = "photo-item";
//         item.innerHTML = `<img src="${p.url}" alt="photo">`;
//         item.onclick = () => openDetail(p.id);
//         album.appendChild(item);
//     });
// }
function renderPhotos(list) {
  const album = document.getElementById("album");
  album.innerHTML = "";
  list.forEach(p => {
    const item = document.createElement("div");
    item.className = "photo-item";
    item.style.position = "relative";
    const checkbox = is_Deleting 
      ? `<input type="checkbox" class="delete-checkbox" value="${p.id}" 
           style="position:absolute; top:5px; right:5px; width:20px; height:20px; z-index:10;">`
      : "";
    item.innerHTML = `
      ${checkbox}
      <img src="${p.url}" alt="photo" style="width:100%; height:auto;">
    `;
    item.onclick = (e) => {
      if (!is_Deleting && !e.target.classList.contains("delete-checkbox")) {
        openDetail(p.id);
      }
    };
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
    // const filtered = photos.filter(p => p.name.toLowerCase().includes(key));

    const filtered = window.photos.filter(p =>
        (p.name || "").toLowerCase().includes(key) ||
        (p.label || "").toLowerCase().includes(key)
    );
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
    localStorage.removeItem("username");
    localStorage.removeItem("photos");
    location.href = "/pages/login.html";
}

function goHome() {
    location.href = "/pages/index.html";
}
function goUpload() {
    location.href = "/pages/upload.html";
}
function goDownload() {
    location.href = "/pages/download.html"
}

function enterDeleteMode() {
    is_Deleting = true;
    document.getElementById("deleteBar").style.display = "block";
    document.getElementById("deletemode_btn").style.display = "none"
    renderPhotos(photos);
}

function cancelDelete() {
    is_Deleting = false;
    document.getElementById("deleteBar").style.display = "none"
    document.getElementById("deletemode_btn").style.display = "block"
    renderPhotos(photos)
}

async function confirmDelete() {
  const selectedIds = [];
  document.querySelectorAll(".delete-checkbox:checked").forEach(cb => {
    selectedIds.push(Number(cb.value));
  });

  if (selectedIds.length === 0) {
    alert("Please select photos to delete!");
    return;
  }

  if (!confirm("Confirm to delete selected photos?")) return;

  //replace this, uplaod delete request to backend.
  const token = localStorage.getItem("token");
  try {
    const res = await fetch("/api/photos/batch-delete", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token
      },
      body: JSON.stringify({ ids: selectedIds })
    });

    if (res.ok) {
      alert("Delete success!");
      photos = await DataService.getPhotos();
      cancelDelete();
      renderPhotos(photos);
    } else {
      alert("Delete failed");
    }
  } catch (e) {
    alert("Network error");
  }
}