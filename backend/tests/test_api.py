import os
import time
import uuid
import requests
import pytest

# BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
BASE_URL = os.getenv("BASE_URL", "http://18.145.174.39")
TEST_PASSWORD = "123456"

# images

@pytest.fixture(scope="session")
def test_email():
    return f"test_{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture(scope="session")
def ensure_user(test_email):
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": test_email,
        "password": TEST_PASSWORD
    })

    assert r.status_code in [201, 409], r.text
    return test_email


@pytest.fixture(scope="session")
def token(ensure_user):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ensure_user,
        "password": TEST_PASSWORD
    })
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


@pytest.fixture(scope="session")
def image_id(token):
    file_path = "tests/test.jpg"
    assert os.path.exists(file_path), "Please put a test.jpg in the /tests/"

    with open(file_path, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/api/images/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": f}
        )

    assert r.status_code in [200, 201], r.text
    data = r.json()
    assert "data" in data and "image_id" in data["data"]
    return data["data"]["image_id"]


def test_health():
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_success(ensure_user):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ensure_user,
        "password": TEST_PASSWORD
    })
    assert r.status_code == 200, r.text

def test_login_fail(test_email):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": test_email,
        "password": "wrong_password"
    })
    assert r.status_code == 401, r.text


def test_register_duplicate(test_email):
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": test_email,
        "password": TEST_PASSWORD
    })
    assert r.status_code in [400, 409], r.text


def test_upload_image(image_id):
    assert image_id is not None


def test_get_image(token, image_id):
    r = requests.get(
        f"{BASE_URL}/api/images/{image_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text

    data = r.json()["data"]
    assert data["image_id"] == image_id
    assert "status" in data


def test_list_images(token):
    r = requests.get(
        f"{BASE_URL}/api/images",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["data"], list)


def test_followup(token, image_id):
    r = requests.post(
        f"{BASE_URL}/api/images/{image_id}/followup",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={"pet_name": "Tom"}
    )
    assert r.status_code == 200, r.text


def test_unauthorized():
    r = requests.get(f"{BASE_URL}/api/images")
    assert r.status_code == 401


def test_not_found(token):
    r = requests.get(
        f"{BASE_URL}/api/images/does-not-exist",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 404, r.text

# upload zip

@pytest.fixture(scope="session")
def zip_job_id(token):
    zip_path = "tests/test.zip"
    assert os.path.exists(zip_path), "Please put a test.zip in the /tests/"

    with open(zip_path, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/api/images/upload-zip",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": f}
        )

    assert r.status_code in [200, 201], r.text

    res = r.json()
    assert "data" in res
    assert "job_id" in res["data"]

    return res["data"]["job_id"]


def test_upload_zip(zip_job_id):
    assert zip_job_id is not None

def test_upload_zip_invalid_file(token):
    file_path = "tests/test.jpg"

    with open(file_path, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/api/images/upload-zip",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("test.jpg", f, "image/jpeg")}
        )

    assert r.status_code == 400, r.text

# download

@pytest.fixture(scope="session")
def download_job_id(token, image_id):
    r = requests.post(
        f"{BASE_URL}/api/images/download",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={"image_ids": [image_id]}
    )

    assert r.status_code in [200, 201], r.text

    data = r.json()
    assert data["success"] is True
    assert "job_id" in data["data"]

    return data["data"]["job_id"]


def test_download(token, image_id):
    r = requests.post(
        f"{BASE_URL}/api/images/download",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={"image_ids": [image_id]}
    )

    assert r.status_code in [200, 201], r.text

    data = r.json()
    assert data["success"] is True
    assert "data" in data
    assert "job_id" in data["data"]
    assert data["data"]["status"] in ["uploaded", "processing"]


def test_download_no_image_ids(token):
    r = requests.post(
        f"{BASE_URL}/api/images/download",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={}
    )

    assert r.status_code == 400


def test_download_invalid_image_ids(token):
    r = requests.post(
        f"{BASE_URL}/api/images/download",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={"image_ids": "not-a-list"}
    )

    assert r.status_code == 400


def test_download_unauthorized():
    r = requests.post(
        f"{BASE_URL}/api/images/download",
        json={"image_ids": ["fake"]}
    )

    assert r.status_code == 401

# job

def test_get_job(token, download_job_id):
    r = requests.get(
        f"{BASE_URL}/api/jobs/{download_job_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert r.status_code == 200, r.text

    data = r.json()
    assert data["success"] is True
    assert data["data"]["job_id"] == download_job_id
    assert "status" in data["data"]


def test_get_job_not_found(token):
    r = requests.get(
        f"{BASE_URL}/api/jobs/not-exist",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert r.status_code == 404, r.text


def test_list_jobs(token):
    r = requests.get(
        f"{BASE_URL}/api/jobs",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert r.status_code == 200, r.text

    data = r.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


def test_list_jobs_contains_created(token, download_job_id):
    r = requests.get(
        f"{BASE_URL}/api/jobs",
        headers={"Authorization": f"Bearer {token}"}
    )

    jobs = r.json()["data"]
    job_ids = [j["job_id"] for j in jobs]

    assert download_job_id in job_ids


def test_get_job_unauthorized(download_job_id):
    r = requests.get(f"{BASE_URL}/api/jobs/{download_job_id}")
    assert r.status_code == 401


def test_list_jobs_unauthorized():
    r = requests.get(f"{BASE_URL}/api/jobs")
    assert r.status_code == 401

# url

def test_presigned_url(token, image_id):
    r = requests.get(
        f"{BASE_URL}/api/images/{image_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text

    s3_key = r.json()["data"]["s3_key"]

    r2 = requests.post(
        f"{BASE_URL}/api/utils/presigned-url",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={"s3_key": s3_key}
    )

    assert r2.status_code == 200, r2.text

    data = r2.json()
    assert data["success"] is True
    assert "url" in data["data"]

    url = data["data"]["url"]

    assert url.startswith("https://")

def test_presigned_url_missing_key(token):
    r = requests.post(
        f"{BASE_URL}/api/utils/presigned-url",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={}
    )

    assert r.status_code == 400

def test_presigned_url_invalid_key(token):
    r = requests.post(
        f"{BASE_URL}/api/utils/presigned-url",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={"s3_key": "not/exist/file.jpg"}
    )

    assert r.status_code == 200

    data = r.json()
    assert data["success"] is True
    assert "url" in data["data"]

# map

def test_map_points(token):
    r = requests.get(
        f"{BASE_URL}/api/map/points",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert r.status_code == 200, r.text

    data = r.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)

def test_map_points_structure(token):
    r = requests.get(
        f"{BASE_URL}/api/map/points",
        headers={"Authorization": f"Bearer {token}"}
    )

    points = r.json()["data"]

    for p in points:
        assert "image_id" in p
        assert "lat" in p
        assert "lng" in p

        assert isinstance(p["lat"], float)
        assert isinstance(p["lng"], float)

def test_map_points_unauthorized():
    r = requests.get(f"{BASE_URL}/api/map/points")
    assert r.status_code == 401

# collections

def test_collections(token):
    r = requests.get(
        f"{BASE_URL}/api/collections",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert r.status_code == 200

    data = r.json()
    assert data["success"] is True

    assert "by_label" in data["data"]
    assert "by_location" in data["data"]

# search

def test_search_match(token):
    r = requests.get(
        f"{BASE_URL}/api/images/search?q=yawl",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert r.status_code == 200

    data = r.json()
    assert data["success"] is True

    for item in data["data"]:
        assert "image_id" in item
        assert "s3_key" in item

def test_search_empty_query(token):
    r = requests.get(
        f"{BASE_URL}/api/images/search",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert r.status_code == 200

    data = r.json()
    assert data["success"] is True
    assert data["data"] == []

def test_search_multiple_keywords(token):
    r = requests.get(
        f"{BASE_URL}/api/images/search?q=solar_dish solar_dish",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert r.status_code == 200

    data = r.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)

def test_search_no_match(token):
    r = requests.get(
        f"{BASE_URL}/api/images/search?q=zzzzzz",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert r.status_code == 200

    data = r.json()
    assert data["success"] is True
    assert data["data"] == []

# delete 

def test_soft_delete_image(token, image_id):
    r = requests.delete(
        f"{BASE_URL}/api/images/{image_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert r.status_code == 200

    data = r.json()
    assert data["success"] is True

def test_deleted_not_in_list(token, image_id):
    requests.delete(
        f"{BASE_URL}/api/images/{image_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    r = requests.get(
        f"{BASE_URL}/api/images",
        headers={"Authorization": f"Bearer {token}"}
    )

    images = r.json()["data"]

    ids = [img["image_id"] for img in images]

    assert image_id not in ids