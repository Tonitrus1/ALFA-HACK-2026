import contextlib
import importlib.metadata
import io
import os

import numpy as np

from .models import Block


class Engine:
    def __init__(self, name: str, threads: int = 4, mkldnn: bool = True):
        self.name = name
        self.threads = threads
        self.mkldnn = mkldnn
        self.model = None

    def load(self):
        if self.name == "paddle":
            os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
            from paddleocr import PaddleOCR

            self.model = PaddleOCR(
                device="cpu",
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="cyrillic_PP-OCRv5_mobile_rec",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=self.mkldnn,
                cpu_threads=self.threads,
            )
        else:
            import pytesseract

            if not {"rus", "eng"}.issubset(pytesseract.get_languages()):
                raise RuntimeError("TESSERACT_LANGUAGE_MISSING")
            self.model = pytesseract

    def recognize(self, image):
        if self.model is None:
            self.load()
        blocks = []
        if self.name == "paddle":
            # Some native backends print recognized text; suppress Python stdout/stderr.
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                result = list(self.model.predict(np.array(image)))[0].json["res"]
            for text, score, polygon in zip(
                result["rec_texts"], result["rec_scores"], result["rec_polys"], strict=True
            ):
                points = np.array(polygon)
                blocks.append(
                    Block(
                        block_id=f"b{len(blocks) + 1}",
                        text=text,
                        confidence=float(score),
                        bbox=[
                            float(points[:, 0].min()),
                            float(points[:, 1].min()),
                            float(points[:, 0].max()),
                            float(points[:, 1].max()),
                        ],
                    )
                )
        else:
            data = self.model.image_to_data(
                image,
                lang="rus+eng",
                config="--psm 6",
                output_type=self.model.Output.DICT,
                timeout=90,
            )
            lines = {}
            for i, text in enumerate(data["text"]):
                if not text.strip() or float(data["conf"][i]) < 0:
                    continue
                x, y, w, h = (data[k][i] for k in ("left", "top", "width", "height"))
                key = tuple(data[k][i] for k in ("block_num", "par_num", "line_num"))
                line = lines.setdefault(
                    key, {"words": [], "scores": [], "bbox": [x, y, x + w, y + h]}
                )
                line["words"].append(text)
                line["scores"].append(min(1, float(data["conf"][i]) / 100))
                box = line["bbox"]
                line["bbox"] = [
                    min(box[0], x),
                    min(box[1], y),
                    max(box[2], x + w),
                    max(box[3], y + h),
                ]
            for line in lines.values():
                blocks.append(
                    Block(
                        block_id=f"b{len(blocks) + 1}",
                        text=" ".join(line["words"]),
                        confidence=min(line["scores"]),
                        bbox=line["bbox"],
                    )
                )
        return blocks

    def version(self):
        return (
            importlib.metadata.version("paddleocr")
            if self.name == "paddle"
            else str(self.model.get_tesseract_version())
        )
