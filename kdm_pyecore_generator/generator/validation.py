from collections import Counter

class KDMValidationReport:
    def __init__(self):
        self.warnings = []
        self.errors = []
        self.infos = []
        self.unresolved_call_count = 0
        self.unresolved_call_examples = []
        self.unresolved_call_prefixes = Counter()

    def add_warning(self, message: str):
        self.warnings.append(message)

    def add_error(self, message: str):
        self.errors.append(message)

    def add_info(self, message: str):
        self.infos.append(message)

    def print_report(self):
        print("\n=== VALIDATION REPORT ===")

        print(f"Errors: {len(self.errors)}")
        for error in self.errors:
            print(f"[ERROR] {error}")

        print(f"\nWarnings: {len(self.warnings)}")
        for warning in self.warnings:
            print(f"[WARNING] {warning}")

        if self.infos:
            print(f"\nInfos: {len(self.infos)}")
            for info in self.infos:
                print(f"[INFO] {info}")

        if self.unresolved_call_count:
            print("\nUnresolved static calls summary:")
            print(f"[INFO] Calls without target_id: {self.unresolved_call_count}")
            if self.unresolved_call_prefixes:
                print("[INFO] Most frequent unresolved call prefixes:")
                for prefix, count in self.unresolved_call_prefixes.most_common(10):
                    print(f"[INFO]   - {prefix}: {count}")
            if self.unresolved_call_examples:
                print("[INFO] Sample unresolved calls:")
                for example in self.unresolved_call_examples[:15]:
                    print(f"[INFO]   - {example}")


class BasicValidator:
    def validate_unresolved_calls(self, data: dict, id_index: dict):
        report = KDMValidationReport()

        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._validate_callable_calls(method, id_index, report)

            for func in file_model.get("functions", []):
                self._validate_callable_calls(func, id_index, report)

        if report.unresolved_call_count:
            report.add_info(
                "Static calls without target_id are reported as an informational "
                "summary because they are common in Python due to dynamic dispatch, "
                "external libraries, aliases and attribute-based calls."
            )

        return report

    def _record_unresolved_call(self, report, call_name, callable_name):
        report.unresolved_call_count += 1
        display_name = str(call_name or "<unknown>")
        display_callable = str(callable_name or "<unknown>")
        report.unresolved_call_prefixes[self._call_prefix(display_name)] += 1

        if len(report.unresolved_call_examples) < 15:
            report.unresolved_call_examples.append(
                f"{display_name} in {display_callable}"
            )

    def _call_prefix(self, call_name: str) -> str:
        if not call_name:
            return "<unknown>"

        name = str(call_name)

        if name.startswith("self."):
            return "self.*"

        if name.startswith("super."):
            return "super.*"

        if "." in name:
            return name.split(".", 1)[0] + ".*"

        if name.startswith("builtin:"):
            return "builtin:*"

        if name.startswith("external:"):
            return "external:*"

        return name

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
                self._record_unresolved_call(
                    report=report,
                    call_name=call.get('name'),
                    callable_name=callable_model.get('qualified_name'),
                )
                continue

            if classification == "internal" and target_id not in id_index:
                report.add_warning(
                    f"Internal call target not found: {target_id} "
                    f"from {callable_model.get('qualified_name')}"
                )
