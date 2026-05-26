from collections import Counter

class RuntimeAwareValidationReport:
    """
    Lightweight validation report compatible with the generator main workflow.

    It distinguishes unresolved static calls from static calls that are
    explained by runtime evidence.
    """

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.infos = []
        self.runtime_resolved_calls = 0
        self.unresolved_call_count = 0
        self.unresolved_call_examples = []
        self.unresolved_call_prefixes = Counter()

    def add_error(self, message: str):
        self.errors.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    def add_info(self, message: str):
        self.infos.append(message)

    def has_errors(self):
        return bool(self.errors)

    def print_report(self):
        print("\n=== VALIDATION REPORT ===")
        print(f"Errors: {len(self.errors)}")

        for error in self.errors:
            print(f"[ERROR] {error}")

        print(f"\nWarnings: {len(self.warnings)}")

        for warning in self.warnings:
            print(f"[WARNING] {warning}")

        if self.runtime_resolved_calls:
            print(f"\nRuntime-resolved static calls: {self.runtime_resolved_calls}")

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


class RuntimeResolutionIndex:
    """
    Index of runtime-observed calls.

    It is used only to suppress/mark static unresolved-call warnings when the
    same call is evidenced by a dynamic runtime_calls relationship.
    """

    def __init__(self, relationships):
        self.runtime_calls = []

        for relationship in relationships or []:
            if relationship.get("type") != "runtime_calls":
                continue

            source = relationship.get("source")
            target = relationship.get("target")

            if not source or not target:
                continue

            self.runtime_calls.append(
                {
                    "source": self._normalize(source),
                    "target": self._normalize(target),
                    "raw": relationship,
                }
            )

    def resolves_static_call(self, callable_qn: str, call_name: str) -> bool:
        if not callable_qn or not call_name:
            return False

        static_source = self._normalize(callable_qn)
        static_call = self._normalize(call_name)

        for runtime_call in self.runtime_calls:
            if not self._source_matches(static_source, runtime_call["source"]):
                continue

            if self._target_matches(static_call, runtime_call["target"]):
                return True

        return False

    def _source_matches(self, static_source: str, runtime_source: str) -> bool:
        if static_source == runtime_source:
            return True

        if static_source.endswith("." + runtime_source):
            return True

        if runtime_source.endswith("." + static_source):
            return True

        static_parts = static_source.split(".")
        runtime_parts = runtime_source.split(".")

        # Methods: Class.method
        if len(static_parts) >= 2 and len(runtime_parts) >= 2:
            if static_parts[-2:] == runtime_parts[-2:]:
                return True

        # Module-level functions: function
        if static_parts and runtime_parts:
            if static_parts[-1] == runtime_parts[-1]:
                return True

        return False

    def _target_matches(self, static_call: str, runtime_target: str) -> bool:
        if static_call == runtime_target:
            return True

        if runtime_target.endswith("." + static_call):
            return True

        static_parts = static_call.split(".")
        runtime_parts = runtime_target.split(".")

        # car.gas, self.brake, logger.info -> compare final callable name.
        if static_parts and runtime_parts:
            if static_parts[-1] == runtime_parts[-1]:
                return True

        # Class.method suffix.
        if len(static_parts) >= 2 and len(runtime_parts) >= 2:
            if static_parts[-2:] == runtime_parts[-2:]:
                return True

        return False

    def _normalize(self, name: str) -> str:
        return (
            str(name)
            .replace("-", "_")
            .replace("/", ".")
            .replace("\\", ".")
        )


class RuntimeAwareBasicValidator:
    """
    JSON-level validator that is aware of dynamic runtime evidence.

    Static calls without target_id are still reported unless a matching
    runtime_calls relationship exists. In that case, the warning is suppressed
    and counted as runtime-resolved.
    """

    def validate_unresolved_calls(self, data: dict, id_index: dict):
        report = RuntimeAwareValidationReport()
        runtime_index = RuntimeResolutionIndex(data.get("relationships", []))

        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._validate_callable_calls(
                        callable_model=method,
                        report=report,
                        runtime_index=runtime_index,
                    )

            for func in file_model.get("functions", []):
                self._validate_callable_calls(
                    callable_model=func,
                    report=report,
                    runtime_index=runtime_index,
                )

        if report.runtime_resolved_calls:
            report.add_info(
                "Some static calls without target_id were not reported because "
                "matching runtime_calls evidence was found."
            )

        if report.unresolved_call_count:
            report.add_info(
                "Static calls without target_id are reported as an informational "
                "summary because they are common in Python due to dynamic dispatch, "
                "external libraries, aliases and attribute-based calls."
            )

        return report

    def _validate_callable_calls(
        self,
        callable_model: dict,
        report: RuntimeAwareValidationReport,
        runtime_index: RuntimeResolutionIndex,
    ):
        callable_qn = callable_model.get("qualified_name")
        callable_name = callable_qn or callable_model.get("name", "<unknown>")

        for call in callable_model.get("calls", []):
            target_id = call.get("target_id")

            if target_id:
                continue

            call_name = self._call_display_name(call)

            if runtime_index.resolves_static_call(callable_qn, call_name):
                report.runtime_resolved_calls += 1
                continue

            self._record_unresolved_call(
                report=report,
                call_name=call_name,
                callable_name=callable_name,
            )

    def _record_unresolved_call(
        self,
        report: RuntimeAwareValidationReport,
        call_name: str,
        callable_name: str,
    ):
        report.unresolved_call_count += 1

        prefix = self._call_prefix(call_name)
        report.unresolved_call_prefixes[prefix] += 1

        if len(report.unresolved_call_examples) < 15:
            report.unresolved_call_examples.append(
                f"{call_name} in {callable_name}"
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

    def _call_display_name(self, call: dict):
        for key in ("name", "function", "method", "class_name"):
            value = call.get(key)

            if value:
                return str(value)

        return "<unknown>"
