let photos = [];
const BASE_URL = "http://18.145.174.39";

window.onload = async function () {
    if (!localStorage.getItem("token")) {
        location.href = "/login.html";
        return;
    }

    const username = localStorage.getItem("username") || "User";
    document.getElementById("userName").innerText = "Hello, " + username;
    localStorage.removeItem("photos");

    await loadImageList();
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

async function loadImageList() {
    try {
        const res = await fetch(BASE_URL + "/api/images", {
            headers: {
                "Authorization": "Bearer " + localStorage.getItem("token")
            }
        });
        const data = await res.json();
        if (data.success) {
            photos = data.data;
            renderImageGrid(photos);
        }
    } catch(err) {
        console.error("Load images error", err);
        alert("Failed to load image");
    }
}

async function renderImageGrid(photos) {
    const grid = document.getElementById("imageGrid");
    grid.innerHTML = "";

    for (const photo of photos) {
        const card = document.createElement("div");
        const imgUrl = await getPresignedUrl(photo.s3_key);
        card.className = "image-card";
        card.innerHTML = `
        <input 
        type="checkbox" 
        class="download-checkbox"
        value="${photo.image_id}"
        style="position:absolute; top:8px; right:8px; width:22px; height:22px; z-index:10;">
        <img src="${imgUrl}" alt="photo" style="width:100%; height:100%; object-fit:cover;">
        `;

        grid.appendChild(card);
    }
}


async function searchPhotos() {
    const key = document.getElementById("searchInput").value.toLowerCase().trim();

    if (!key) {
        renderImageGrid(photos);
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

    renderImageGrid(finalFiltered);
}


function getSelectedPhotos() {
    const selected = [];

    document.querySelectorAll(".download-checkbox:checked").forEach(cb => {
        selected.push(cb.value);
    });
    return selected;
}


async function createDownloadJob(imageIds) {
  const token = localStorage.getItem("token");
  const res = await fetch(`${BASE_URL}/api/images/download`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ image_ids: imageIds })
  });
  const data = await res.json();
  if (!data.success) throw new Error(data.message);
  return data.data.job_id;
}


async function pollDownloadStatus(jobId) {
  const token = localStorage.getItem("token");
  const pollInterval = 1000;
  const maxRetries = 30;

  for (let i = 0; i < maxRetries; i++) {
    const res = await fetch(`${BASE_URL}/api/jobs/${jobId}`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    const data = await res.json();

    if (data.success && data.data.status === "complete") {
      const res_s3_key = data.data.result_s3_key;
      const zipUrl = await getPresignedUrl(res_s3_key);
      return zipUrl;
    }
    if (data.data.status === "failed") {
      throw new Error("Fail to download");
    }

    await new Promise(resolve => setTimeout(resolve, pollInterval));
  }
  throw new Error("Download over time limit");
}

function triggerDownload(zipUrl) {  
  const a = document.createElement("a");
  a.href = zipUrl;
  a.download = 'album_images.zip';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}


async function BatchDownload() {
    const selected = getSelectedPhotos();

    if (selected.length === 0) {
        alert("No photo selected!");
        return;
    }
    const btn = document.getElementById("downloadBtn");
    btn.disabled = true;
    btn.innerText = "Downloading ...";

    console.log("selected", selected);

    const token = localStorage.getItem("token");
    try {
        const jobId = await createDownloadJob(selected);
        const zipUrl = await pollDownloadStatus(jobId);
        triggerDownload(zipUrl)

    } catch (err) {
        console.error(err);
        alert("Download failed, please try again.");
    }
    btn.disabled = false;
    btn.innerText = "Download";
}

// Navigation
function goHome() { location.href = "index.html"; }
function goUpload() { location.href = "upload.html"; }
function goDownload() { location.href = "download.html"; }
function goMapView() {  location.href = "/mapView.html";  }
function logout() {
    localStorage.clear();
    location.href = "pages/login.html";
}