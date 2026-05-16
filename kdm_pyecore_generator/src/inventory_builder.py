from pathlib import Path


class InventoryBuilder:
    def __init__(self, factory, segment, language="unknown"):
        self.factory = factory
        self.segment = segment
        self.language = language

        self.inventory_model = None
        self.source_files = {}

    def build_from_json(self, data: dict):
        project_name = data.get("projectName", "UnknownProject")
        self.language = data.get("language", self.language)

        self.inventory_model = self.factory.create_inventory_model(
            f"{project_name}_InventoryModel"
        )
        self.segment.model.append(self.inventory_model)

        for file_model in data.get("files", []):
            self.get_or_create_source_file(file_model)

        return self.inventory_model

    def get_or_create_source_file(self, file_model: dict):
        path = file_model.get("path")
        if not path:
            return None

        if path in self.source_files:
            return self.source_files[path]

        name = Path(path).name

        source_file = self.factory.create_source_file(
            name=name,
            path=path,
            language=self.language,
            encoding="UTF-8",
            format_="text",
        )

        self.inventory_model.inventoryElement.append(source_file)
        self.source_files[path] = source_file

        return source_file

    def get_source_file_by_path(self, path: str):
        return self.source_files.get(path)
