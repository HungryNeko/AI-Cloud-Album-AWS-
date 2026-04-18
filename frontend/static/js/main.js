// 模拟图片数据
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

// 检查登录
window.onload = () => {
    if (!localStorage.getItem("token")) {
        location.href = "../pages/index.html";
    }
    renderPhotos(photos);
};

// 渲染相册
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

// 打开详情页
function openDetail(id) {
    localStorage.setItem("currentPhotoId", id);
    window.open("detail.html", "_blank");
}

// 搜索
function searchPhotos() {
    const key = document.getElementById("searchInput").value.toLowerCase();
    const filtered = photos.filter(p => p.name.toLowerCase().includes(key));
    renderPhotos(filtered);
}

// 回到主页
function goHome() {
    document.getElementById("searchInput").value = "";
    renderPhotos(photos);
}

// 登出
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
    alert("Download module");
}