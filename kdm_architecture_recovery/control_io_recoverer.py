from kdm_architecture_recovery.adaptive_stereotype_catalog import (
    stereotype_for_component_role,
)


class ControlIORecoverer:
    """
    Conservative recoverer for control-oriented abstractions.

    It infers only a small number of high-value candidates:

    - ReferenceInput:
        desired values, setpoints, targets, thresholds, goals.

    - MeasuredOutput:
        runtime values measured from the managed subsystem.

    - Sensor:
        methods/classes/variables that read or measure the managed subsystem.

    - Effector:
        methods/classes/variables that actuate or modify the managed subsystem.

    Important design decision:
    this recoverer intentionally avoids promoting generic framework/lifecycle
    methods such as __init__, subscribe, contains, start, stop, getattr, etc.
    Otherwise almost the whole framework is incorrectly promoted as
    ReferenceInput/MeasuredOutput.
    """

    # Strong reference-input evidence. These must appear in the actual element
    # name, not merely somewhere in a long string representation.
    REFERENCE_NAME_TERMS = {
        "reference",
        "setpoint",
        "set_point",
        "target",
        "goal",
        "desired",
        "threshold",
    }

    # Names that often denote concrete measured values.
    MEASURED_NAME_TERMS = {
        "measured",
        "measurement",
        "current",
        "actual",
        "observed",
        "distance",
        "speed",
        "position",
        "temperature",
        "pressure",
        "level",
        "angular",
        "rpm",
    }

    SENSOR_NAME_TERMS = {
        "sensor",
        "read",
        "measure",
        "capture",
        "observe",
        "sample",
        "tachometer",
        "proximity",
        "camera",
        "gps",
    }

    EFFECTOR_NAME_TERMS = {
        "effector",
        "actuator",
        "actuate",
        "apply",
        "execute",
        "brake",
        "gas",
        "accelerate",
        "steer",
        "wheel",
        "motor",
        "servo",
        "siren",
        "hazard",
        "light",
    }

    # Generic framework/lifecycle names that should not be promoted as control
    # abstractions even if they contain weak words such as set or get.
    EXCLUDED_EXACT_NAMES = {
        "__init__",
        "__del__",
        "__getattr__",
        "__getitem__",
        "__iter__",
        "__call__",
        "__setattr__",
        "init",
        "del",
        "getattr",
        "getitem",
        "iter",
        "call",
        "repr",
        "create",
        "setup",
        "load",
        "get",
        "set",
        "start",
        "stop",
        "dispose",
        "subscribe",
        "unsubscribe",
        "on_next",
        "on_error",
        "on_completed",
        "handler",
        "decorator",
        "wrapped",
        "contains",
        "register",
        "add_loop",
        "has_loop",
        "add_element",
        "has_element",
        "add_to_loop",
        "add_to_app",
        "add_to_level",
    }

    # Framework/internal modules that should not generate Sensor/Effector/
    # ReferenceInput candidates. The example target is the application, not the
    # PyMAPE framework internals.
    EXCLUDED_PATH_FRAGMENTS = {
        ".mape.",
        "_mape_",
        "mape/",
        ".utils.",
        "_utils_",
        "utils/",
        ".remote.",
        "_remote_",
        "remote/",
        ".typing.",
        "_typing_",
        "typing/",
        ".base_elements.",
        "_base_elements_",
        "base_elements/",
        ".config.",
        "_config_",
        "config/",
    }

    # Limit accidental explosion. If a real case needs more, this can be made
    # configurable later.
    MAX_COMPONENTS_PER_ROLE = {
        "ReferenceInput": 8,
        "MeasuredOutput": 10,
        "Sensor": 10,
        "Effector": 10,
    }

    def recover(self, data: dict, existing_components: list[dict]):
        existing_names = {
            self._normalize_name(component.get("name", ""))
            for component in existing_components
        }
        existing_impl = {
            impl
            for component in existing_components
            for impl in component.get("implemented_by", [])
        }

        candidates = []

        for element in self._iter_code_like_elements(data):
            if self._should_skip_element(element):
                continue

            role, confidence, evidence = self._classify(element)

            if role is None:
                continue

            name = element.get("name") or element.get("qualified_name") or ""
            qualified_name = element.get("qualified_name") or element.get("id") or name
            normalized_name = self._normalize_name(name)

            if normalized_name in existing_names:
                continue

            implementation_id = element.get("id")
            if implementation_id in existing_impl:
                continue

            component = {
                "id": self._component_id(
                    role=role,
                    qualified_name=qualified_name,
                    name=name,
                ),
                "name": name or qualified_name.split(".")[-1],
                "role": role,
                "implemented_by": [implementation_id] if implementation_id else [],
                "confidence": confidence,
                "evidence": evidence,
                "source": "rule_based_control_io",
                "status": "auto_accepted" if confidence >= 0.85 else "needs_review",
                "code_element_type": element.get("type"),
            }

            stereotype_info = stereotype_for_component_role(role)
            if stereotype_info:
                component.update(stereotype_info)

            candidates.append(component)

        candidates = self._deduplicate(candidates)
        candidates = self._cap_by_role(candidates)

        return candidates

    # ------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------

    def _classify(self, element: dict):
        name = element.get("name") or ""
        element_type = element.get("type")
        tokens = self._tokens(name)

        decorator_tokens = self._tokens(" ".join(
            str(decorator)
            for decorator in element.get("decorators", [])
        ))

        full_tokens = tokens | decorator_tokens

        # ReferenceInput should normally be a variable, attribute, constant or
        # parameter-like element. Avoid promoting methods/functions just because
        # they have generic names.
        if element_type in {"variable", "attribute", "parameter"}:
            matched = full_tokens.intersection(self.REFERENCE_NAME_TERMS)
            if matched:
                return (
                    "ReferenceInput",
                    0.9,
                    [
                        "Reference input name evidence: "
                        + ", ".join(sorted(matched))
                    ],
                )

        # MeasuredOutput is data, not the reader itself.
        if element_type in {"variable", "attribute", "parameter"}:
            matched = full_tokens.intersection(self.MEASURED_NAME_TERMS)
            if matched:
                return (
                    "MeasuredOutput",
                    0.8,
                    [
                        "Measured output name evidence: "
                        + ", ".join(sorted(matched))
                    ],
                )

        # Sensor may be a method/function/class if the name strongly indicates
        # reading or measuring.
        if element_type in {"class", "method", "function", "variable", "attribute"}:
            matched = full_tokens.intersection(self.SENSOR_NAME_TERMS)
            if matched:
                return (
                    "Sensor",
                    0.85,
                    [
                        "Sensor name/decorator evidence: "
                        + ", ".join(sorted(matched))
                    ],
                )

        # Effector may be a method/function/class/variable if it strongly
        # indicates actuation.
        if element_type in {"class", "method", "function", "variable", "attribute"}:
            matched = full_tokens.intersection(self.EFFECTOR_NAME_TERMS)
            if matched:
                return (
                    "Effector",
                    0.85,
                    [
                        "Effector name/decorator evidence: "
                        + ", ".join(sorted(matched))
                    ],
                )

        return None, 0.0, []

    def _should_skip_element(self, element: dict):
        name = self._normalize_name(element.get("name", ""))
        qualified_name = str(
            element.get("qualified_name") or element.get("id") or ""
        )

        if name in self.EXCLUDED_EXACT_NAMES:
            return True

        lowered_qn = qualified_name.lower()

        for fragment in self.EXCLUDED_PATH_FRAGMENTS:
            if fragment in lowered_qn:
                return True

        # Skip private/dunder-like names unless they explicitly contain strong
        # sensor/effector terms.
        if name.startswith("_") and not (
            self._tokens(name).intersection(self.SENSOR_NAME_TERMS)
            or self._tokens(name).intersection(self.EFFECTOR_NAME_TERMS)
        ):
            return True

        return False

    # ------------------------------------------------------------
    # Data traversal
    # ------------------------------------------------------------

    def _iter_code_like_elements(self, data: dict):
        for file_model in data.get("files", []):
            yield from self._iter_file_elements(file_model)

        for module_model in data.get("modules", []):
            yield from self._iter_file_elements(module_model)

    def _iter_file_elements(self, file_model: dict):
        for class_model in file_model.get("classes", []):
            yield self._as_element(class_model, "class")

            for attribute in class_model.get("attributes", []):
                yield self._as_element(attribute, "attribute", parent=class_model)

            # Variables are safer than arbitrary methods for ReferenceInput and
            # MeasuredOutput.
            for variable in class_model.get("variables", []):
                yield self._as_element(variable, "variable", parent=class_model)

            for method in class_model.get("methods", []):
                yield self._as_element(method, "method", parent=class_model)

        for variable in file_model.get("global_variables", []):
            yield self._as_element(variable, "variable")

        for variable in file_model.get("variables", []):
            yield self._as_element(variable, "variable")

        for function in file_model.get("functions", []):
            yield self._as_element(function, "function")

    def _as_element(self, element: dict, element_type: str, parent: dict | None = None):
        result = dict(element)
        result.setdefault("type", element_type)

        if parent is not None:
            result.setdefault("parent_name", parent.get("name"))
            result.setdefault(
                "qualified_name",
                f"{parent.get('qualified_name', parent.get('name'))}.{element.get('name')}",
            )

        return result

    # ------------------------------------------------------------
    # Text utilities
    # ------------------------------------------------------------

    def _tokens(self, text: str):
        normalized = self._normalize_name(text)
        return set(normalized.split())

    def _normalize_name(self, text: str):
        text = str(text).replace("-", "_").replace(".", "_").replace("/", "_")
        normalized = []

        for char in text:
            if char.isalnum() or char == "_":
                normalized.append(char.lower())
            else:
                normalized.append(" ")

        text = "".join(normalized)
        return " ".join(text.replace("_", " ").split())

    def _component_id(self, role: str, qualified_name: str, name: str):
        raw = f"{name}_{role}_{qualified_name}"
        normalized = self._normalize_name(raw).replace(" ", "_")
        return f"component:{normalized}"

    def _deduplicate(self, components: list[dict]):
        seen = set()
        result = []

        for component in components:
            key = (
                component.get("role"),
                component.get("name"),
                tuple(component.get("implemented_by", [])),
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(component)

        return result

    def _cap_by_role(self, components: list[dict]):
        grouped = {}

        for component in sorted(
            components,
            key=lambda item: item.get("confidence", 0.0),
            reverse=True,
        ):
            role = component.get("role")
            grouped.setdefault(role, [])

            if len(grouped[role]) < self.MAX_COMPONENTS_PER_ROLE.get(role, 10):
                grouped[role].append(component)

        result = []
        for role_components in grouped.values():
            result.extend(role_components)

        return result
