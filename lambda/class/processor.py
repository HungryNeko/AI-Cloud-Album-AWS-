from pathlib import Path

import numpy as np
from PIL import Image
import onnxruntime as ort
from labels import ANIMAL_LABELS, LABELS

class processor:
    # load model in init
    # call predict for class
    def __init__(self):
        # Use the exported ONNX classification model.
        model_path = Path(__file__).resolve().parent / "yolov8n-cls-miniimagenet-best.onnx"

        self.session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )

        self.input_name = self.session.get_inputs()[0].name

        self.class_names = {i: label for i, label in enumerate(LABELS)}

    def predict(self, image: Image.Image) -> str:
        if not isinstance(image, Image.Image):
            raise TypeError("predict expects a PIL.Image.Image")

        img = image.convert("RGB").resize((224, 224))
        img = np.array(img).astype(np.float32) / 255.0
        img = img.transpose(2, 0, 1)  # HWC -> CHW
        img = np.expand_dims(img, axis=0)

        outputs = self.session.run(None, {self.input_name: img})[0]

        top1 = int(np.argmax(outputs, axis=1)[0])
        return self.class_names[top1]

    def numpyreader(self, image: Image.Image) -> np.ndarray:
        if not isinstance(image, Image.Image):
            raise TypeError("numpyreader expects a PIL.Image.Image")
        return np.array(image.convert("RGB"))

    def getlocation(self, image: Image.Image) -> tuple[float, float]:
        if not isinstance(image, Image.Image):
            raise TypeError("getlocation expects a PIL.Image.Image")

        # First try standard EXIF GPS tags.
        exif = image.getexif()
        gps_ifd = exif.get_ifd(0x8825) if 0x8825 in exif else None
        if gps_ifd:
            lat_ref = gps_ifd.get(1)
            lat_dms = gps_ifd.get(2)
            lon_ref = gps_ifd.get(3)
            lon_dms = gps_ifd.get(4)

            if lat_ref and lat_dms and lon_ref and lon_dms:
                lat = (
                    float(lat_dms[0])
                    + float(lat_dms[1]) / 60.0
                    + float(lat_dms[2]) / 3600.0
                )
                lon = (
                    float(lon_dms[0])
                    + float(lon_dms[1]) / 60.0
                    + float(lon_dms[2]) / 3600.0
                )

                if str(lat_ref).upper() == "S":
                    lat = -lat
                if str(lon_ref).upper() == "W":
                    lon = -lon
                return (lat, lon)

        # Fallback to custom text metadata keys.
        lat_text = image.info.get("coord_latitude")
        lon_text = image.info.get("coord_longitude")
        if lat_text is not None and lon_text is not None:
            return (float(lat_text), float(lon_text))

        raise ValueError("No location metadata found in image")

    def if_need_question(self, label: str) -> str:
        if not isinstance(label, str):
            return ""
        if label in ANIMAL_LABELS:
            label_text = label.replace("_", " ")
            return "Do you know this " + label_text + "'s name?"
        return ""


if __name__ == "__main__":
    # demo
    processor = processor()
    image_path = "data/mini-imagenet-test/n02099601/1480.png"
    with Image.open(image_path) as pil_image:
        image_np = processor.numpyreader(pil_image)
        print("numpy shape:", image_np.shape)

        pred_label = processor.predict(pil_image)
        print(pred_label)

        location = processor.getlocation(pil_image)
        print(location)
        print("if need question: " + processor.if_need_question(pred_label))
