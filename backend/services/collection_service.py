from collections import defaultdict
from services.db_service import list_images_by_user

def get_collections(user_id):
    items = list_images_by_user(user_id)

    label_groups = defaultdict(list)
    location_groups = defaultdict(list)

    for item in items:
        image = {
            "image_id": item.get("image_id"),
            "s3_key": item.get("s3_key")
        }

        label = item.get("label")
        if label:
            label_groups[label].append(image)

        loc = item.get("location")
        if loc:
            lat = loc.get("lat")
            lng = loc.get("lng")

            if lat and lng:
                location_key = f"{round(lat, 2)}, {round(lng, 2)}"
                location_groups[location_key].append(image)

    by_label = [
        {
            "label": label,
            "count": len(images),
            "images": images
        }
        for label, images in label_groups.items()
    ]

    by_location = [
        {
            "location": loc,
            "count": len(images),
            "images": images
        }
        for loc, images in location_groups.items()
    ]

    return {
        "by_label": by_label,
        "by_location": by_location
    }