const BASE_URL = "http://18.145.174.39";
let photos = {};
let is_Deleting = false;
// Login check
window.onload = async function() {
    if (!localStorage.getItem("token")) {
        location.href = "/login.html";
    }

    const username = localStorage.getItem("username");
    if(!username) username = "User";
    var node = document.getElementById("userName")
    node.textContent = "Hello, " + username
    localStorage.removeItem("photos");
    loadPhotoList();
};

async function getPresignedUrl(s3_key) {
  try{
    const token = localStorage.getItem("token");
    const res = await fetch(`${BASE_URL}/api/utils/presigned-url`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        s3_key: s3_key
      })
    });
    const data = await res.json();
    if(data.success && data.data?.url){
      return data.data.url;
    }
  }catch (e){
    console.error("Fail to get photos", e);
  }
  return "";
}

async function loadPhotoList(){
    try{
      const res = await fetch(BASE_URL + "/api/images", {
        headers: {"Authorization": "Bearer " + localStorage.getItem("token")}
      });
      const data = await res.json();
      if(data.success){
        photos = data.data;
        console.log("Image List", data);
        await renderPhotos(photos);
      }
    }catch(e){
      console.error("Load photo error", e);
    }
}


async function renderPhotos(list) {
  const album = document.getElementById("album");
  album.innerHTML = "";
  for (const p of list) {
    const item = document.createElement("div");
    item.className = "photo-item";
    item.style.position = "relative";
    const checkbox = is_Deleting 
      ? `<input type="checkbox" class="delete-checkbox" value="${p.image_id}" 
           style="position:absolute; top:5px; right:5px; width:20px; height:20px; z-index:10;">`
      : "";
    const imgUrl = await getPresignedUrl(p.s3_key);
    console.log("Image URL", imgUrl);
    item.innerHTML = `
      ${checkbox}
      <img src="${imgUrl}" alt="photo" style="width:100%; height:100%; object-fit: cover; object-position: center; display: block;">
    `;
    item.onclick = (e) => {
      if (!is_Deleting && !e.target.classList.contains("delete-checkbox")) {
        openDetail(p.image_id);
      }
    };
    album.appendChild(item);
  }
}


// Details
function openDetail(id) {
    localStorage.setItem("currentPhotoId", id);
    window.location.href ="/detail.html";
}

// serach
async function searchPhotos() {
    const key = document.getElementById("searchInput").value.toLowerCase().trim();

    if (!key) {
        renderPhotos(photos);
        return;
    }
    let filtered = photos.filter(p => {
        const label = (p.label || "").toLowerCase();
        return label.includes(key);
    });
    const token = localStorage.getItem("token");
    const finalFiltered = [];

    for (const p of photos) {
        const label = (p.label || "").toLowerCase();
        const labelMatch = label.includes(key);
        let followupMatch = false;
        if (!labelMatch) {
            try {
                const res = await fetch(`${BASE_URL}/api/images/${p.image_id}`, {
                    headers: {
                        "Authorization": `Bearer ${token}`
                    }
                });
                const data = await res.json();
                if (data.success && data.data.followup_answers) {
                     const answers = data.data.followup_answers.map(obj => {
            if (!obj) return "";
            const firstValue = Object.values(obj)[0] || "";
            return firstValue.toString().toLowerCase();
          });
                    followupMatch = answers.some(ans => ans.includes(key));
                }
            } catch (e) {
                console.error("Failed to load detail for search", e);
            }
        }
        if (labelMatch || followupMatch) {
            finalFiltered.push(p);
        }
    }

    renderPhotos(finalFiltered);
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
    localStorage.removeItem("user_id")
    localStorage.removeItem("photos");
    location.href = "/login.html";
}


function goUpload() {
    location.href = "/upload.html";
}
function goDownload() {
    location.href = "/download.html";
}
function goMapView() {
    location.href = "/mapView.html";
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
    selectedIds.push(cb.value);
  });

  if (selectedIds.length === 0) {
    alert("Please select photos to delete!");
    return;
  }
  console.log("Deletequeue", selectedIds);

  if (!confirm("Confirm to delete selected photos?")) return;

  //replace this, uplaod delete request to backend.
  const token = localStorage.getItem("token");
  let allSuccess = true;
  try {
    for (const imageId of selectedIds) {
      const res = await fetch(`${BASE_URL}/api/images/${imageId}`, {
        method: "DELETE",
        headers: {
          "Authorization": "Bearer " + token
        }
      });

      const response = await res.json();
      if(!response.success) {
        allSuccess = false;
        console.error(`Delete failed for ${imageId}: `, response.message);
      }
    }

    if (allSuccess) {
      alert("Delete Complete");
    }else {
      alert("Some image fail!");
    }
    cancelDelete();
    location.href = "/index.html";
  } catch (e) {
    alert("Network error");
  }
}