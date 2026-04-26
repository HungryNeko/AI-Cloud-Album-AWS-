# =========================
# Image Input -> Classification & Location -> Follow-up Name Input
# =========================

# ---------- Classification and Location Extract ----------

# Input:
classification_input = [
    {
        "user_id": "test_2c6c5ba6c5@example.com",
        "image_id": "229b6787-34d3-435c-bbb8-9d0c79eec148",
        "s3_key": "test_2c6c5ba6c5@example.com/229b6787-34d3-435c-bbb8-9d0c79eec148/test.jpg",
    }
]

# Multiple class tasks:
classification_input_multiple = [
    {
        "user_id": "test_2c6c5ba6c5@example.com",
        "image_id": "229b6787-34d3-435c-bbb8-9d0c79eec148",
        "s3_key": "test_2c6c5ba6c5@example.com/229b6787-34d3-435c-bbb8-9d0c79eec148/test.jpg",
    },
    {
        "user_id": "test_2c6c5ba6c5@example.com",
        "image_id": "another-image-id",
        "s3_key": "test_2c6c5ba6c5@example.com/another-image-id/test2.jpg",
    },
]

# Compatible legacy class input:
# {"task_id": "1", "images": ["id1", "id2"]} still works.

# Return:
classification_output = {
    "task_id": "1",
    "run_success": True,  # False if too many files or runtime error, may need to change input or check database
    "not_finished": ["id1"],  # if time limit is reached, these IDs need to be submitted in another task
    "questions": {
        "id2": "123?",  # follow-up question for the image; use "" if no question is needed
        "id3": ""
    },
    "msg": "not finished",  # description for debugging or status information
}

# Class status side effects:
# - Only images with status == "uploaded" are processed.
# - When an image starts processing, status becomes "processing".
# - When an image is processed successfully, status becomes "done".
# - If image loading or classification fails, status becomes "failed".
# - Images in any other status are skipped.

# ---------- Name Input (User Answers to Follow-up Questions) ----------

# Input:
name_input = {
    "task_id": "2",
    "images": {
        "id1": "name1",   # image_id mapped to user-provided name or answer
        "id2": "name2",
    },
}

# Temporary compatible input format:
name_input_s3_key = {
    "task_id": "2",
    "images": {
        "test_1776650811@example.com/7a591f70-0f89-4138-90fb-3f9ef2f8ccc2/test.jpg": "name1",
    },
}

# Output:
name_output = {
    "task_id": "2",
    "run_success": True,  # False if runtime error occurs
    "not_finished": ["id2"],  # images that were not processed due to timeout or errors
    "msg": "not finished",  # description for debugging or status information
}

# ---------- download zip ----------
#input:
download_input = {
    "task_id":"3",
    "images": ["id1", "id2"]
}

# Temporary compatible input format:
download_input_s3_key = {
    "task_id":"3",
    "images": [
        "test_1776650811@example.com/7a591f70-0f89-4138-90fb-3f9ef2f8ccc2/test.jpg"
    ],
}
# Output:
download_output = {
    "task_id": "3",
    "run_success": True,  # False if runtime error occurs like too much files to zip
    "zip_link": '<s3 link for zip file>',  # backend needs remember to delete
    "zip_s3_key": '<s3 key for zip file>',  # also written to Users.zip_download
    "msg": "finished",  # description for debugging or status information
}

# Side effect:
# Users[user_id].zip_download = download_output["zip_s3_key"]

# ---------- upload zip ----------
#input:
upload_input = {
    "task_id":"4",
    "zip_link": '<s3 link for zip file>',
    "user_id":'id1'
}
# Output:
upload_output = {
    "task_id": "4",
    "run_success": True,  # False if runtime error occurs like too much files to zip
    "images": ["id1", "id2"],
    "msg": "finished",  # description for debugging or status information
}
