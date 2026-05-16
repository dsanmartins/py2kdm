class KDMValidationReport:
    def __init__(self):
        self.warnings = []
        self.errors = []

    def add_warning(self, message: str):
        self.warnings.append(message)

    def add_error(self, message: str):
        self.errors.append(message)

    def print_report(self):
        print("\n=== VALIDATION REPORT ===")

        print(f"Errors: {len(self.errors)}")
        for error in self.errors:
            print(f"[ERROR] {error}")

        print(f"\nWarnings: {len(self.warnings)}")
        for warning in self.warnings:
            print(f"[WARNING] {warning}")


class BasicValidator:
    def validate_unresolved_calls(self, data: dict, id_index: dict):
        report = KDMValidationReport()

        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._validate_callable_calls(method, id_index, report)

            for func in file_model.get("functions", []):
                self._validate_callable_calls(func, id_index, report)

        return report

    def _validate_callable_calls(self, callable_model: dict, id_index: dict, report):
        for call in callable_model.get("calls", []):
            classification = call.get("classification")
            target_id = call.get("target_id")

            # External and builtin calls are handled by ExternalModelBuilder.
            if classification in {
                "external",
                "external_type_method",
                "builtin",
                "builtin_type_method",
            }:
                continue

            if target_id is None:
                report.add_warning(
                    f"Call without target_id: {call.get('name')} "
                    f"in {callable_model.get('qualified_name')}"
                )
                continue

            if classification == "internal" and target_id not in id_index:
                report.add_warning(
                    f"Internal call target not found: {target_id} "
                    f"from {callable_model.get('qualified_name')}"
                )
