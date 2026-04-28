const BASE_URL = "http://18.145.174.39";

window.onload = async function() {
    if (!localStorage.getItem("token")) {
        location.href = "/login.html";
        return;
    }
    const username = localStorage.getItem("username") || "User";
    document.getElementById("userName").innerText = `Hello, ${username}`;
    // const id = Number(localStorage.getItem("currentPhotoId"));
    // const photo = photos.find(p => p.id === id);
    let photoId = localStorage.getItem("currentPhotoId");
    if (!photoId) {
        alert("Image don't exist");
        location.href = "index.html";
        return;
    }
    const photo = await loadImageDetail(photoId);
    if (!photo) return;

    const bigImg = document.getElementById("bigImg");
    const imgUrl = await getPresignedUrl(photo.s3_key);
    if (bigImg) {
        bigImg.src = imgUrl;
    }
    load_Map_Location(photo);
    setupFollowupSection(photo, photoId);
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

async function loadImageDetail(imageId) {
    try{
        const res = await fetch(BASE_URL + "/api/images/" + imageId, {
            headers: {
                "Authorization": "Bearer " + localStorage.getItem("token")
            }
        });
        const data = await res.json();
        if (!data.success) {
            alert(data.message || "Failed to load image detail");
            location.href = "/index.html";
            return null;
        }
        const img = data.data;
        const followupInput = document.getElementById("nameInput");
        let savedAnswer = "";
        if (img.followup_answers && img.followup_answers.length > 0) {
            const firstObj = img.followup_answers[0];
            if(firstObj){
                savedAnswer = Object.values(firstObj)[0] || "";
            }
        }
        followupInput.value = savedAnswer;
        return data.data;
    }catch (err){
        console.error(err);
        alert("Network error when loading photo");
        location.href = "/index.html";
        return null;
    }
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
function goMapView() {  location.href = "/mapView.html";  }
function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    localStorage.removeItem("photos");
    location.href = "pages/login.html";
}

async function load_Map_Location(photo) {
    let final_lat = 34.05;
    let final_lng = -118.24;
    let loc = await getLocation(final_lat, final_lng);
    if (photo.location && photo.location.lat && photo.location.lng){
        loc = await getLocation(photo.location.lat, photo.location.lng);
        final_lat = photo.location.lat;
        final_lng = photo.location.lng;
    }
    const locationStr = `${loc.district} ${loc.city} ${loc.state} ${loc.country}`;
    document.getElementById("locationText").innerText = locationStr;
    const map = L.map('map').setView([final_lat, final_lng], 14);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
    L.marker([final_lat, final_lng]).addTo(map);
}


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


function setupFollowupSection(photo, imageId){
    const promptEl = document.getElementById("promptText");
    const inputEl = document.getElementById("nameInput");
    const saveBtn = document.querySelector(".save-btn");

    promptEl.style.display = "none";
    inputEl.style.display = "none";
    saveBtn.style.display = "none";
    
    if (photo.followup_questions && photo.followup_questions.length > 0) {
        const question = photo.followup_questions[0];
        promptEl.innerText = question;
        promptEl.style.display = "block";
        inputEl.style.display = "block";
        saveBtn.style.display = "block";

        saveBtn.onclick = async () => {
            const answer = inputEl.value.trim();
            if(! answer) {
                alert("Please enter answer");
                return;
            }
            await submitFollowup(imageId, answer);
        };
    }
}


async function submitFollowup(imageId, answer) {
    try {
        const res = await fetch(BASE_URL + "/api/images/" + imageId + "/followup", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + localStorage.getItem("token")
            },
            body: JSON.stringify({
                pet_name: answer
            })
        });

        const data = await res.json();
        if (data.success) {
            alert("Saved successfully!");
        }else {
            alert("Failed to save:" + data.message);
        }
    }catch (err){
        console.error(err);
        alert("Network error");
    }
}


// function saveName() {
//     const name = document.getElementById("nameInput").value.trim();
//     if (!name) {
//         alert("Please Enter name");
//         return;
//     }
//     // Needs to replace this, save back to database. Save to image's name attribute.
//     alert(`Image named as: ${name}`);
// }