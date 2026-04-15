"""
input:
{
    "task_id": "3",
    "images": ["id1", "id2"]
}

output:
{
    "task_id": "3",
    "run_success": True,
    "zip_link": "<s3 link for zip file>",
    "msg": "finished"
}
"""
import json


class handler:

    def __init__(self, event, context):
        self.task_id = ""
        self.tasks = []
        self.context = context
        self.files = []
        self.zip_link = ""
        self.msg = ""
        self.run_success = True
        self.read_msg(event)

    def read_msg(self, event: str) -> None:
        # handel json msg
        try:
            payload = event
            if isinstance(payload, str):
                payload = json.loads(payload)
            if not isinstance(payload, dict):
                self.msg = "Error when loading msg: event should be dict"
                self.run_success = False
                return
            self.task_id = str(payload.get("task_id", ""))
            images = payload.get("images", [])
            if not self.task_id:
                self.msg = "Error when loading msg: task_id is required"
                self.run_success = False
                return
            if not isinstance(images, list):
                self.msg = "Error when loading msg: images should be list"
                self.run_success = False
                return
            self.tasks = [str(image_id) for image_id in images]
        except Exception as e:
            self.msg = "Error when loading msg: " + str(e)
            self.run_success = False

    def has_enough_time(self, threshold_seconds=60) -> bool:
        if self.context is None or not hasattr(self.context, "get_remaining_time_in_millis"):
            self.msg = "Error when loading lambda context: get_remaining_time_in_millis not found"
            self.run_success = False
            return False
        remaining_time_ms = self.context.get_remaining_time_in_millis()
        threshold_ms = threshold_seconds * 1000
        return remaining_time_ms >= threshold_ms

    def load_images(self, image_list: list) -> list:
        try:
            pass
            # TODO: use the final database/S3 helper to load images by id.
            return []
        except Exception as e:
            self.msg = "Error when loading images: " + str(e)
            self.run_success = False
            return []

    def make_zip(self, files: list):
        try:
            pass
            # TODO: compress files and return a zip file object or temp path.
            return None
        except Exception as e:
            self.msg = "Error when making zip: " + str(e)
            self.run_success = False
            return None

    def write_s3(self, zip_file) -> str:
        try:
            pass
            # TODO: upload zip_file to S3 with the final helper.
            return ""
        except Exception as e:
            self.msg = "Error when writing to s3: " + str(e)
            self.run_success = False
            return ""

    def process(self) -> None:
        if not self.has_enough_time():
            self.msg = "not finished"
            self.run_success = False
            return

        self.files = self.load_images(self.tasks)
        if not self.run_success:
            return

        zip_file = self.make_zip(self.files)
        if not self.run_success:
            return

        self.zip_link = self.write_s3(zip_file)
        if not self.run_success:
            return

    def run(self):
        if self.run_success == False:
            return
        if len(self.tasks) > 10000:
            self.run_success = False
            self.msg = "Error for too much Files"
            return
        self.process()
        if self.run_success == False:
            return
        self.msg = "finished"

    def reply(self):
        msg = {
            "task_id": self.task_id,
            "run_success": self.run_success,
            "zip_link": self.zip_link,
            "msg": self.msg,
        }
        return msg


def lambda_handler(event, context):
    pro = handler(event, context)
    pro.run()
    return pro.reply()
