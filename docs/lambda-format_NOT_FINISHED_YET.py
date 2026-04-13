# =========================
# Image Input -> Classification & Location -> Follow-up Name Input
# =========================

# ---------- Classification and Location Extract ----------

# Input:
classification_input = {
    "task_id": "1",
    "images": ["id1", "id2", "id3"],  # keys from database
}

# Return:
classification_output = {
    "task_id": "1",
    "run_success": True,  # False if too many files or runtime error, may need to change input or check database
    "not_finished": ["id1", "id2", "id3"],  # if time limit is reached, these IDs need to be submitted in another task
    "questions": {
        "id4": "123?",  # follow-up question for the image; use "" if no question is needed
        "id5": "123?",
    },
    "msg": "not finished",  # description for debugging or status information
}

# ---------- Name Input (User Answers to Follow-up Questions) ----------

# Input:
name_input = {
    "task_id": "1",
    "images": {
        "image_id1": "abc",   # image_id mapped to user-provided name or answer
        "image_id2": "abc2",
    },
}

# Output:
name_output = {
    "task_id": "1",
    "run_success": True,  # False if runtime error occurs
    "not_finished": ["id1", "id2"],  # images that were not processed due to timeout or errors
    "msg": "not finished",  # description for debugging or status information
}