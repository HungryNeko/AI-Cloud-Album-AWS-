# =========================
# Image Input -> Classification & Location -> Follow-up Name Input
# =========================

# ---------- Classification and Location Extract ----------

# Input:
classification_input = {
    "task_id": "1",# to track if task is finished
    "images": ["id1", "id2", "id3"],  # keys from database
}

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

# ---------- Name Input (User Answers to Follow-up Questions) ----------

# Input:
name_input = {
    "task_id": "2",
    "images": {
        "id1": "name1",   # image_id mapped to user-provided name or answer
        "id2": "name2",
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
# Output:
download_output = {
    "task_id": "3",
    "run_success": True,  # False if runtime error occurs like too much files to zip
    "zip_link": '<s3 link for zip file>',  # backend needs remember to delete
    "msg": "finished",  # description for debugging or status information
}

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