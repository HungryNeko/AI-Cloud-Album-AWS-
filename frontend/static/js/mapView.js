const BASE_URL = "http://18.145.174.39";
let map;

window.onload = async function () {
  if (!localStorage.getItem("token")) {
    location.href = "/login.html";
    return;
  }
  const username = localStorage.getItem("username") || "User";
  document.getElementById("userName").innerText = "Hello, " + username;

  initMap();
  await loadMapPoints();
};


function initMap() {
  const DEFAULT_LAT = 34.0522;
  const DEFAULT_LNG = -118.2437;

  map = L.map('map').setView([DEFAULT_LAT, DEFAULT_LNG], 10);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  window.customMarkerIcon = L.divIcon({
    className: 'custom-map-marker',
    html: `<div style="
      background: #ff4444;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      border: 2px solid white;
      box-shadow: 0 0 4px rgba(0,0,0,0.4);
    "></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  });
}


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


async function getImageDetail(imageId) {
  const token = localStorage.getItem("token");
  try {
    const res = await fetch(`${BASE_URL}/api/images/${imageId}`, {
      headers: { "Authorization": `Bearer ${token}` }
    });
    const data = await res.json();
    if (data.success) return data.data;
  } catch (e) {
    console.error("get image detail error", e);
  }
  return null;
}


async function loadMapPoints() {
  const token = localStorage.getItem("token");
  try {
    const res = await fetch(`${BASE_URL}/api/map/points`, {
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });
    const data = await res.json();

    if (!data.success) return;

    const points = data.data;

    for (const point of points) {
        const imageId = point.image_id;
      const marker = L.marker([point.lat, point.lng], {
        icon: customMarkerIcon
      }).addTo(map);
    const img_Detail = await getImageDetail(point.image_id);
    if(!img_Detail || !img_Detail.s3_key) continue;
    const imgUrl = await getPresignedUrl(img_Detail.s3_key);
    const tooltipContent = `
        <div style="width:120px; text-align:center;">
          <img src="${imgUrl}" style="width:100%; height:70px; object-fit:cover; border-radius:4px;">
          <div style="margin-top:4px; font-size:12px;">ID: ${point.image_id}</div>
        </div>
      `;
      console.log("iamgeId", imageId);

    marker.bindTooltip(tooltipContent, {
        permanent: false,
        direction: "top",
        className: "image-tooltip"
      });

      marker.on('click', function(){
        localStorage.setItem("currentPhotoId", imageId);
        location.href = `/detail.html`;
      });

      marker.bindPopup(`Photo ID: ${point.image_id}<br>Click to view detail`);
    }

  } catch (err) {
    console.error("Failed to load map points", err);
  }
}

function goHome() { location.href = "/index.html"; }
function goUpload() { location.href = "/upload.html"; }
function goDownload() { location.href = "/download.html"; }
function goMapView() {location.href = "/mapView.html"; }
function logout() {
  localStorage.clear();
  location.href = "/login.html";
}