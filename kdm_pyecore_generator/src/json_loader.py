import json


class JSONModelLoader:
    def __init__(self, json_path: str):
        self.json_path = json_path

    def load(self):
        with open(self.json_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        self._validate(data)
        return data

    def _validate(self, data: dict):
        required_fields = ["projectName", "language", "files"]

        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field in JSON model: {field}")

        if not isinstance(data["files"], list):
            raise ValueError("The field 'files' must be a list.")
