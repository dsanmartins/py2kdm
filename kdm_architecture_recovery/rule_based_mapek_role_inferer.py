class RuleBasedMAPEKRoleInferer:
    """
    Infers candidate MAPE-K roles using visible conservative rules.

    Version 2 adds support for Python framework-style MAPE-K declarations,
    especially PyMAPE decorators and registration calls. This is important
    because application-level MAPE-K roles may be represented by decorated
    functions rather than by classes named Monitor, Analyzer, Planner or
    Executor.

    Main sources of evidence:
    - explicit decorators such as @loop.monitor, @loop.plan, @loop.execute;
    - registration calls such as loop.register(...);
    - class names and module paths;
    - method/function names;
    - weak relationship hints.

    Weak suggestions are still reported, but the ArchitectureRecoveryEngine
    decides whether they should become components.
    """

    ROLE_RULES = [
        {
            "role": "Monitor",
            "name_terms": ["monitor"],
            "method_terms": ["collect", "observe", "measure", "read", "get_status"],
            "decorator_terms": ["monitor"],
        },
        {
            "role": "Analyzer",
            "name_terms": ["analyzer", "analyser"],
            "method_terms": ["analyze", "analyse", "detect", "evaluate", "diagnose"],
            "decorator_terms": ["analyze", "analyse", "analyzer", "analyser"],
        },
        {
            "role": "Planner",
            "name_terms": ["planner"],
            "method_terms": ["plan", "select", "decide", "choose", "strategy"],
            "decorator_terms": ["plan", "planner"],
        },
        {
            "role": "Executor",
            "name_terms": ["executor"],
            "method_terms": ["execute", "apply", "reconfigure", "adapt", "restart"],
            "decorator_terms": ["execute", "executor"],
        },
        {
            "role": "Knowledge",
            "name_terms": ["knowledge"],
            "method_terms": ["store", "update", "query", "remember", "record"],
            "decorator_terms": ["knowledge"],
        },
        {
            "role": "Sensor",
            "name_terms": ["sensor", "probe"],
            "method_terms": ["read", "sense", "collect", "measure"],
            "decorator_terms": ["sensor", "probe"],
        },
        {
            "role": "Effector",
            "name_terms": ["effector", "actuator"],
            "method_terms": ["actuate", "apply", "change", "execute"],
            "decorator_terms": ["effector", "actuator"],
        },
        {
            "role": "ReferenceInput",
            "name_terms": ["reference", "goal", "threshold", "target"],
            "method_terms": ["threshold", "target", "goal"],
            "decorator_terms": ["reference", "goal", "threshold", "target"],
        },
        {
            "role": "Alternative",
            "name_terms": ["alternative", "strategy", "plan"],
            "method_terms": ["strategy", "alternative", "plan"],
            "decorator_terms": ["alternative", "strategy"],
        },
        {
            "role": "LoopManager",
            "name_terms": ["loop", "coordinator", "manager"],
            "method_terms": ["run_loop", "coordinate", "orchestrate", "adapt"],
            "decorator_terms": ["loop"],
        },
    ]

    # PyMAPE-specific decorator terms. They are still visible rules, not
    # hidden AI inference.
    DECORATOR_ROLE_TERMS = {
        "monitor": "Monitor",
        "analyze": "Analyzer",
        "analyse": "Analyzer",
        "plan": "Planner",
        "execute": "Executor",
    }

    REGISTRATION_ROLE_TERMS = {
        "loop.monitor": "Monitor",
        "loop.analyze": "Analyzer",
        "loop.analyse": "Analyzer",
        "loop.plan": "Planner",
        "loop.execute": "Executor",
    }

    def infer_roles(self, project_model: dict):
        """
        Returns role suggestions for classes, methods and functions.

        Supports both the Python extractor shape, where classes/functions live
        inside files[], and the Java extractor shape, where classes/interfaces
        are commonly stored at top-level under elements[].
        """

        suggestions = []

        for file_model in project_model.get("files", []):
            for cls in self._iter_file_classes(file_model):
                suggestion = self._infer_class_role(cls, file_model)

                if suggestion is not None:
                    suggestions.append(suggestion)

                for method in cls.get("methods", []):
                    suggestions.extend(
                        self._infer_callable_roles(
                            callable_model=method,
                            file_model=file_model,
                            owner_class=cls,
                        )
                    )

            for func in file_model.get("functions", []):
                suggestions.extend(
                    self._infer_callable_roles(
                        callable_model=func,
                        file_model=file_model,
                        owner_class=None,
                    )
                )

        for element in project_model.get("elements", []):
            kind = str(self._value(element, "kind", "type") or "").lower()

            if kind not in {"class", "interface", "enum"}:
                continue

            synthetic_file = {
                "path": self._value(element, "sourcePath", "path") or "",
                "name": self._value(element, "sourceFile", "name") or "",
            }

            suggestion = self._infer_class_role(element, synthetic_file)

            if suggestion is not None:
                suggestions.append(suggestion)

            for method in element.get("methods", []):
                suggestions.extend(
                    self._infer_callable_roles(
                        callable_model=method,
                        file_model=synthetic_file,
                        owner_class=element,
                    )
                )

        return self._deduplicate_suggestions(suggestions)

    def _iter_file_classes(self, file_model: dict):
        for cls in file_model.get("classes", []):
            yield cls

        for element in file_model.get("elements", []):
            kind = str(self._value(element, "kind", "type") or "").lower()
            if kind in {"class", "interface", "enum"}:
                yield element

    # ------------------------------------------------------------
    # Class-level role inference
    # ------------------------------------------------------------

    def _infer_class_role(self, cls: dict, file_model: dict):
        class_name = self._value(cls, "name") or ""
        qualified_name = self._value(cls, "qualified_name", "qualifiedName", "name") or ""
        path = self._value(file_model, "path", "sourcePath") or ""
        methods = cls.get("methods", [])

        best = None

        for rule in self.ROLE_RULES:
            score = 0.0
            evidence = []

            if self._contains_any(class_name, rule["name_terms"]):
                score += 0.45
                evidence.append(
                    f"Class name matches role term for {rule['role']}: {class_name}"
                )

            if self._contains_any(path, rule["name_terms"]):
                score += 0.20
                evidence.append(
                    f"Module path contains role term for {rule['role']}: {path}"
                )

            method_matches = self._matching_methods(methods, rule["method_terms"])

            if method_matches:
                score += min(0.25, 0.10 * len(method_matches))
                evidence.append(
                    "Methods match semantic indicators: "
                    + ", ".join(method_matches[:5])
                )

            relationship_matches = self._relationship_hints(methods, rule["role"])

            if relationship_matches:
                score += 0.10
                evidence.append(
                    "Call relationships support role: "
                    + ", ".join(relationship_matches[:5])
                )

            score = round(min(score, 1.0), 2)

            if score == 0:
                continue

            candidate = {
                "code_element_id": self._value(cls, "id"),
                "code_element_qualified_name": qualified_name,
                "code_element_type": "class",
                "suggested_role": rule["role"],
                "confidence": score,
                "evidence": evidence,
                "source": "rule_based_class",
                "status": self._status_from_confidence(score),
            }

            if best is None or candidate["confidence"] > best["confidence"]:
                best = candidate

        return best

    # ------------------------------------------------------------
    # Callable-level role inference
    # ------------------------------------------------------------

    def _infer_callable_roles(
        self,
        callable_model: dict,
        file_model: dict,
        owner_class: dict = None,
    ):
        suggestions = []

        decorator_suggestion = self._infer_role_from_decorators(
            callable_model=callable_model,
            file_model=file_model,
            owner_class=owner_class,
        )

        if decorator_suggestion is not None:
            suggestions.append(decorator_suggestion)

        registration_suggestion = self._infer_role_from_registration_calls(
            callable_model=callable_model,
            file_model=file_model,
            owner_class=owner_class,
        )

        if registration_suggestion is not None:
            suggestions.append(registration_suggestion)

        return suggestions

    def _infer_role_from_decorators(
        self,
        callable_model: dict,
        file_model: dict,
        owner_class: dict = None,
    ):
        decorators = list(callable_model.get("decorators", []))
        decorators.extend(callable_model.get("annotations", []))

        if not decorators:
            return None

        for decorator in decorators:
            decorator_text = str(decorator).lower()

            for term, role in self.DECORATOR_ROLE_TERMS.items():
                if self._decorator_matches_role(decorator_text, term):
                    loop_hint = self._extract_loop_hint_from_decorator(decorator)
                    evidence = [
                        f"Decorator '{decorator}' maps to MAPE-K role {role}"
                    ]

                    if loop_hint:
                        evidence.append(f"Loop hint inferred from decorator: {loop_hint}")

                    return {
                        "code_element_id": self._value(callable_model, "id"),
                        "code_element_qualified_name": self._value(
                            callable_model, "qualified_name", "qualifiedName", "qualifiedSignature", "name"
                        ),
                        "code_element_type": self._value(callable_model, "type", "kind") or "callable",
                        "owner_class_id": self._value(owner_class, "id") if owner_class else None,
                        "owner_class_qualified_name": (
                            self._value(owner_class, "qualified_name", "qualifiedName", "name") if owner_class else None
                        ),
                        "suggested_role": role,
                        "confidence": 0.95,
                        "evidence": evidence,
                        "source": "rule_based_decorator",
                        "status": "auto_accepted",
                        "loop_hint": loop_hint,
                    }

        return None

    def _infer_role_from_registration_calls(
        self,
        callable_model: dict,
        file_model: dict,
        owner_class: dict = None,
    ):
        """
        Detects patterns such as:

            loop.monitor(func)
            loop.plan(func)
            loop.execute(func)

        This is complementary to decorator detection.
        """

        for call in callable_model.get("calls", []):
            call_name = self._call_display_name(call).lower()

            for term, role in self.REGISTRATION_ROLE_TERMS.items():
                if term in call_name:
                    return {
                        "code_element_id": self._value(callable_model, "id"),
                        "code_element_qualified_name": self._value(
                            callable_model, "qualified_name", "qualifiedName", "qualifiedSignature", "name"
                        ),
                        "code_element_type": self._value(callable_model, "type", "kind") or "callable",
                        "owner_class_id": self._value(owner_class, "id") if owner_class else None,
                        "owner_class_qualified_name": (
                            self._value(owner_class, "qualified_name", "qualifiedName", "name") if owner_class else None
                        ),
                        "suggested_role": role,
                        "confidence": 0.85,
                        "evidence": [
                            f"Registration call '{call_name}' maps to MAPE-K role {role}"
                        ],
                        "source": "rule_based_registration_call",
                        "status": "auto_accepted",
                        "loop_hint": self._extract_loop_hint_from_call(call),
                    }

        return None

    # ------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------

    def _contains_any(self, text: str, terms: list):
        lowered = str(text or "").lower()

        return any(term.lower() in lowered for term in terms)

    def _matching_methods(self, methods: list, terms: list):
        matches = []

        for method in methods:
            method_name = str(self._value(method, "name", "qualifiedName", "qualified_name", "qualifiedSignature") or "").lower()

            for term in terms:
                if term.lower() in method_name:
                    matches.append(self._value(method, "name", "qualifiedName", "qualifiedSignature"))
                    break

        return matches

    def _relationship_hints(self, methods: list, role: str):
        role_terms = {
            "Monitor": ["analyze", "analyser", "analyzer", "knowledge", "sensor"],
            "Analyzer": ["plan", "planner", "knowledge", "symptom"],
            "Planner": ["execute", "executor", "alternative", "strategy"],
            "Executor": ["effector", "actuator", "apply", "reconfigure"],
            "Knowledge": ["monitor", "analyzer", "planner", "executor"],
            "Sensor": ["monitor"],
            "Effector": ["executor"],
            "LoopManager": ["monitor", "analyzer", "planner", "executor"],
        }.get(role, [])

        matches = []

        for method in methods:
            for call in method.get("calls", []):
                call_name = self._call_display_name(call).lower()

                for term in role_terms:
                    if term in call_name:
                        matches.append(call.get("name"))
                        break

        return matches

    def _decorator_matches_role(self, decorator_text: str, term: str):
        """
        Checks role decorators conservatively.

        Accepted examples:
        - loop.monitor
        - loop.plan
        - loop.plan()
        - mape.loop.monitor

        Avoids matching arbitrary words unless they appear as a dotted or final
        decorator segment.
        """

        normalized = decorator_text.replace("()", "")

        return (
            normalized == term
            or normalized.endswith(f".{term}")
            or f".{term}(" in decorator_text
            or normalized.endswith(f".{term}()")
        )

    def _extract_loop_hint_from_decorator(self, decorator):
        decorator_text = str(decorator)

        if "." in decorator_text:
            return decorator_text.split(".")[0]

        return None

    def _extract_loop_hint_from_call(self, call: dict):
        receiver = call.get("receiver")

        if receiver:
            return str(receiver).split(".")[0]

        name = call.get("name")

        if name and "." in str(name):
            return str(name).split(".")[0]

        return None

    def _call_display_name(self, call):
        if not isinstance(call, dict):
            return str(call or "")

        for key in [
            "name",
            "qualified_name",
            "qualifiedName",
            "function",
            "method",
            "target",
            "targetName",
            "targetQualifiedName",
        ]:
            if call.get(key):
                return str(call.get(key))

        receiver = call.get("receiver")
        method = call.get("method")

        if receiver and method:
            return f"{receiver}.{method}"

        return ""

    def _value(self, data: dict, *keys):
        if not isinstance(data, dict):
            return None

        for key in keys:
            if key in data and data.get(key) is not None:
                return data.get(key)

        return None

    def _status_from_confidence(self, confidence: float):
        if confidence >= 0.85:
            return "auto_accepted"

        if confidence >= 0.60:
            return "needs_review"

        return "weak_suggestion"

    def _deduplicate_suggestions(self, suggestions: list):
        """
        Keeps the strongest suggestion for each code element and role.
        """

        by_key = {}

        for suggestion in suggestions:
            key = (
                suggestion.get("code_element_id"),
                suggestion.get("suggested_role"),
            )

            current = by_key.get(key)

            if current is None:
                by_key[key] = suggestion
                continue

            if suggestion.get("confidence", 0.0) > current.get("confidence", 0.0):
                by_key[key] = suggestion

        return list(by_key.values())
