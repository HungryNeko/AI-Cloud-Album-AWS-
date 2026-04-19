def success(data=None, message="ok", code=200):
    return {"success": True, "message": message, "data": data}, code

def error(message="error", code=400):
    return {"success": False, "message": message}, code