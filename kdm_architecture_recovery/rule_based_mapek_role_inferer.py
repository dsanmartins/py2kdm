class RuleBasedMAPEKRoleInferer:
    """
    Infers candidate MAPE-K roles using deterministic visible rules.

    The inferer combines:
    - explicit names/decorators/registration calls;
    - static responsibility evidence from calls, imports, fields and methods;
    - technology patterns such as Android sensors, broadcasts, AudioManager and
      SQLite.

    A class may receive more than one role. This is intentional: real systems
    often fuse Analyzer, Planner and Executor responsibilities in one class.
    """

    ROLE_RULES = [
        {"role": "Monitor", "name_terms": ["monitor"], "method_terms": ["collect", "observe", "measure", "read", "get_status"], "decorator_terms": ["monitor"]},
        {"role": "Analyzer", "name_terms": ["analyzer", "analyser"], "method_terms": ["analyze", "analyse", "detect", "evaluate", "diagnose", "check"], "decorator_terms": ["analyze", "analyse", "analyzer", "analyser"]},
        {"role": "Planner", "name_terms": ["planner"], "method_terms": ["plan", "select", "decide", "choose", "strategy", "priority"], "decorator_terms": ["plan", "planner"]},
        {"role": "Executor", "name_terms": ["executor"], "method_terms": ["execute", "apply", "reconfigure", "adapt", "restart", "set"], "decorator_terms": ["execute", "executor"]},
        {"role": "Knowledge", "name_terms": ["knowledge"], "method_terms": ["store", "update", "query", "remember", "record", "fetch", "insert", "delete"], "decorator_terms": ["knowledge"]},
        {"role": "Sensor", "name_terms": ["sensor", "probe"], "method_terms": ["read", "sense", "collect", "measure"], "decorator_terms": ["sensor", "probe"]},
        {"role": "Effector", "name_terms": ["effector", "actuator"], "method_terms": ["actuate", "apply", "change", "execute", "set"], "decorator_terms": ["effector", "actuator"]},
        {"role": "ReferenceInput", "name_terms": ["reference", "goal", "threshold", "target"], "method_terms": ["threshold", "target", "goal"], "decorator_terms": ["reference", "goal", "threshold", "target"]},
        {"role": "Alternative", "name_terms": ["alternative", "strategy", "plan"], "method_terms": ["strategy", "alternative", "plan"], "decorator_terms": ["alternative", "strategy"]},
        {"role": "LoopManager", "name_terms": ["loop", "coordinator", "manager"], "method_terms": ["run_loop", "coordinate", "orchestrate", "adapt"], "decorator_terms": ["loop"]},
    ]

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

    RESPONSIBILITY_SIGNALS = {
        "Monitor": {
            "contextmanager", "locationmanager", "locationlistener",
            "bluetoothadapter", "bluetoothdevice", "broadcastreceiver",
            "intentservice", "getsystemservice", "requestlocationupdates",
            "getlastknownlocation", "registerreceiver", "putextra",
            "gps_available", "gps_location", "gps_speed", "bt_device_list",
        },
        "Sensor": {
            "locationmanager", "locationlistener", "bluetoothadapter",
            "bluetoothdevice", "broadcastreceiver", "sensor", "gps", "bt_",
        },
        "Analyzer": {
            "adaptationmanager", "checkrules", "check", "evaluate", "validate",
            "filter", "contextoperator", "getbooleanextra", "getstringextra",
            "getdoubleextra", "getstringarrayextra", "rule", "condition",
            "operator", "satisfiedrulelist",
        },
        "Planner": {
            "priority", "candidate", "satisfiedrulelist", "choice", "choose",
            "select", "random", "nextint", "conflict", "strategy", "rulelist",
        },
        "Executor": {
            "audiomanager", "settings", "settings_system", "setstreamvolume",
            "setringermode", "setvibratesetting", "putint", "sendbroadcast",
            "airplane_mode", "action_airplane_mode_changed", "ringer_mode",
        },
        "Effector": {
            "audiomanager", "settings_system", "setstreamvolume",
            "setringermode", "setvibratesetting", "putint", "sendbroadcast",
            "airplane_mode", "ringer_mode",
        },
        "Knowledge": {
            "mydbadapter", "mydbhelper", "sqlitedatabase", "sqliteopenhelper",
            "cursor", "contentvalues", "table_rule", "table_filter",
            "table_profile", "table_constant", "fetch", "insert", "update",
            "delete", "rule", "filter", "profile", "contextconstant",
        },
        "LoopManager": {
            "contextmanager", "adaptationmanager", "intentservice", "onreceive",
            "sendbroadcast", "registerreceiver", "startservice", "newcontext",
        },
    }

    def infer_roles(self, project_model: dict):
        suggestions = []

        for file_model in project_model.get("files", []):
            for cls in file_model.get("classes", []) or []:
                suggestions.extend(self._infer_class_roles(cls, file_model))
                for method in cls.get("methods", []) or []:
                    suggestions.extend(self._infer_callable_roles(method, file_model, cls))

            for func in file_model.get("functions", []) or []:
                suggestions.extend(self._infer_callable_roles(func, file_model, None))

        # Java extractor stores classes in top-level elements.
        file_by_path = {f.get("path"): f for f in project_model.get("files", [])}
        for element in project_model.get("elements", []) or []:
            if element.get("kind") != "class":
                continue
            file_model = file_by_path.get(element.get("filePath"), {})
            suggestions.extend(self._infer_class_roles(element, file_model))
            for method in element.get("methods", []) or []:
                suggestions.extend(self._infer_callable_roles(method, file_model, element))

        return self._deduplicate_suggestions(suggestions)

    # ------------------------------------------------------------
    # Class-level role inference
    # ------------------------------------------------------------

    def _infer_class_roles(self, cls: dict, file_model: dict):
        if not self._is_architecturally_eligible_class(cls, file_model):
            return []

        suggestions = []
        suggestions.extend(self._infer_class_roles_from_general_rules(cls, file_model))
        suggestions.extend(self._infer_class_roles_from_responsibilities(cls, file_model))
        return suggestions

    def _infer_class_roles_from_general_rules(self, cls: dict, file_model: dict):
        class_name = cls.get("name", "")
        qualified_name = self._qualified_name(cls)
        path = file_model.get("path", "") or cls.get("filePath", "")
        methods = cls.get("methods", []) or []
        suggestions = []

        for rule in self.ROLE_RULES:
            score = 0.0
            evidence = []

            if self._contains_any(class_name, rule["name_terms"]):
                score += 0.45
                evidence.append(f"Class name matches role term for {rule['role']}: {class_name}")

            if self._contains_any(path, rule["name_terms"]):
                score += 0.20
                evidence.append(f"Module path contains role term for {rule['role']}: {path}")

            method_matches = self._matching_methods(methods, rule["method_terms"])
            if method_matches:
                score += min(0.25, 0.10 * len(method_matches))
                evidence.append("Methods match semantic indicators: " + ", ".join(method_matches[:5]))

            relationship_matches = self._relationship_hints(methods, rule["role"])
            if relationship_matches:
                score += 0.10
                evidence.append("Call relationships support role: " + ", ".join(relationship_matches[:5]))

            score = round(min(score, 1.0), 2)
            if score < 0.20:
                continue

            suggestions.append(self._build_class_suggestion(cls, qualified_name, rule["role"], score, evidence, "rule_based_class"))

        return suggestions

    def _infer_class_roles_from_responsibilities(self, cls: dict, file_model: dict):
        tokens = self._class_tokens(cls, file_model)
        qualified_name = self._qualified_name(cls)
        suggestions = []

        for role, signals in self.RESPONSIBILITY_SIGNALS.items():
            matches = sorted(signal for signal in signals if self._token_match(tokens, signal))
            if not matches:
                continue

            score = self._responsibility_score(role, matches, cls)
            if score < 0.45:
                continue

            evidence = [
                "Static responsibility evidence for " + role + ": " + ", ".join(matches[:8])
            ]

            # Add explicit class-level explanation for known fused roles.
            class_name = str(cls.get("name", "")).lower()
            if class_name == "adaptationmanager" and role in {"Analyzer", "Planner", "Executor", "Effector", "LoopManager"}:
                evidence.append("AdaptationManager fuses rule evaluation, planning/selection and execution responsibilities.")
            if class_name == "contextmanager" and role in {"Monitor", "Sensor", "LoopManager"}:
                evidence.append("ContextManager observes runtime context and emits context-change events.")
            if class_name in {"mydbadapter", "mydbhelper"} and role == "Knowledge":
                evidence.append("Database adapter/helper manages rules, filters, profiles and context constants.")

            suggestions.append(self._build_class_suggestion(cls, qualified_name, role, score, evidence, "rule_based_responsibility"))

        return suggestions

    def _responsibility_score(self, role: str, matches: list, cls: dict):
        base = min(0.85, 0.40 + 0.07 * len(matches))
        class_name = str(cls.get("name", "")).lower()

        if class_name == "adaptationmanager" and role in {"Analyzer", "Planner", "Executor", "Effector", "LoopManager"}:
            base = max(base, 0.82)
        if class_name == "contextmanager" and role in {"Monitor", "Sensor", "LoopManager"}:
            base = max(base, 0.82)
        if class_name in {"mydbadapter", "mydbhelper"} and role == "Knowledge":
            base = max(base, 0.85)

        return round(min(base, 0.95), 2)

    def _build_class_suggestion(self, cls, qualified_name, role, confidence, evidence, source):
        return {
            "code_element_id": cls.get("id"),
            "code_element_qualified_name": qualified_name,
            "code_element_type": "class",
            "suggested_role": role,
            "confidence": confidence,
            "evidence": evidence,
            "source": source,
            "status": self._status_from_confidence(confidence),
        }

    # ------------------------------------------------------------
    # Callable-level role inference
    # ------------------------------------------------------------

    def _infer_callable_roles(self, callable_model: dict, file_model: dict, owner_class: dict = None):
        suggestions = []

        decorator_suggestion = self._infer_role_from_decorators(callable_model, file_model, owner_class)
        if decorator_suggestion is not None:
            suggestions.append(decorator_suggestion)

        registration_suggestion = self._infer_role_from_registration_calls(callable_model, file_model, owner_class)
        if registration_suggestion is not None:
            suggestions.append(registration_suggestion)

        return suggestions

    def _infer_role_from_decorators(self, callable_model: dict, file_model: dict, owner_class: dict = None):
        decorators = callable_model.get("decorators", [])
        if not decorators:
            return None

        for decorator in decorators:
            decorator_text = str(decorator).lower()
            for term, role in self.DECORATOR_ROLE_TERMS.items():
                if self._decorator_matches_role(decorator_text, term):
                    loop_hint = self._extract_loop_hint_from_decorator(decorator)
                    evidence = [f"Decorator '{decorator}' maps to MAPE-K role {role}"]
                    if loop_hint:
                        evidence.append(f"Loop hint inferred from decorator: {loop_hint}")
                    return {
                        "code_element_id": callable_model.get("id"),
                        "code_element_qualified_name": self._callable_qualified_name(callable_model),
                        "code_element_type": callable_model.get("type", "callable"),
                        "owner_class_id": owner_class.get("id") if owner_class else None,
                        "owner_class_qualified_name": self._qualified_name(owner_class) if owner_class else None,
                        "suggested_role": role,
                        "confidence": 0.95,
                        "evidence": evidence,
                        "source": "rule_based_decorator",
                        "status": "auto_accepted",
                        "loop_hint": loop_hint,
                    }
        return None

    def _infer_role_from_registration_calls(self, callable_model: dict, file_model: dict, owner_class: dict = None):
        for call in callable_model.get("calls", []) or []:
            call_name = self._call_display_name(call).lower()
            for term, role in self.REGISTRATION_ROLE_TERMS.items():
                if term in call_name:
                    return {
                        "code_element_id": callable_model.get("id"),
                        "code_element_qualified_name": self._callable_qualified_name(callable_model),
                        "code_element_type": callable_model.get("type", "callable"),
                        "owner_class_id": owner_class.get("id") if owner_class else None,
                        "owner_class_qualified_name": self._qualified_name(owner_class) if owner_class else None,
                        "suggested_role": role,
                        "confidence": 0.85,
                        "evidence": [f"Registration call '{call_name}' maps to MAPE-K role {role}"],
                        "source": "rule_based_registration_call",
                        "status": "auto_accepted",
                        "loop_hint": self._extract_loop_hint_from_call(call),
                    }
        return None

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _class_tokens(self, cls: dict, file_model: dict):
        tokens = []
        self._append_terms(tokens, cls.get("name"))
        self._append_terms(tokens, cls.get("qualifiedName"))
        self._append_terms(tokens, cls.get("qualified_name"))
        self._append_terms(tokens, cls.get("packageName"))
        self._append_terms(tokens, cls.get("filePath"))
        self._append_terms(tokens, file_model.get("packageName"))
        self._append_terms(tokens, file_model.get("path"))

        for import_model in file_model.get("imports", []) or []:
            if isinstance(import_model, dict):
                self._append_terms(tokens, import_model.get("module"))
                self._append_terms(tokens, import_model.get("name"))
            else:
                self._append_terms(tokens, import_model)

        for base in cls.get("bases", []) + cls.get("extendsTypes", []) + cls.get("implementsTypes", []):
            self._append_terms(tokens, base)

        for field in cls.get("fields", []) + cls.get("attributes", []) + cls.get("instance_attributes", []):
            if isinstance(field, dict):
                self._append_terms(tokens, field.get("name"))
                self._append_terms(tokens, field.get("type"))
                self._append_terms(tokens, field.get("resolvedType"))
            else:
                self._append_terms(tokens, field)

        for method in cls.get("methods", []) or []:
            self._append_terms(tokens, method.get("name"))
            self._append_terms(tokens, method.get("signature"))
            self._append_terms(tokens, method.get("qualifiedSignature"))
            self._append_callable_terms(tokens, method)

        return tokens

    def _append_callable_terms(self, tokens: list, callable_model: dict):
        for call in callable_model.get("calls", []) or []:
            self._append_call_terms(tokens, call)

        for local in callable_model.get("localVariables", []) + callable_model.get("local_variables", []):
            if isinstance(local, dict):
                for key in ["name", "type", "resolvedType", "assignedType", "assignedValue", "valueKind"]:
                    self._append_terms(tokens, local.get(key))

        for statement in callable_model.get("body", []) or []:
            self._append_statement_terms(tokens, statement)

    def _append_statement_terms(self, tokens: list, statement: dict):
        if not isinstance(statement, dict):
            return
        for key in ["type", "statementType", "controlType", "condition", "value", "valueKind", "className"]:
            self._append_terms(tokens, statement.get(key))
        for target in statement.get("targets", []) or []:
            self._append_terms(tokens, target)
        for key in ["valueCall", "conditionCalls", "valueCalls", "exceptionCalls"]:
            value = statement.get(key)
            if isinstance(value, dict):
                self._append_call_terms(tokens, value)
            elif isinstance(value, list):
                for call in value:
                    self._append_call_terms(tokens, call)
        for nested_key in ["body", "elseBody", "finallyBody"]:
            for nested in statement.get(nested_key, []) or []:
                self._append_statement_terms(tokens, nested)
        for catch_clause in statement.get("catchClauses", []) or []:
            self._append_statement_terms(tokens, catch_clause)

    def _append_call_terms(self, tokens: list, call: dict):
        if not isinstance(call, dict):
            return
        for key in ["name", "methodName", "method", "function", "scope", "receiver", "resolvedTarget", "targetId", "classification", "kind"]:
            self._append_terms(tokens, call.get(key))
        for argument in call.get("arguments", []) or []:
            self._append_terms(tokens, argument)

    def _append_terms(self, tokens: list, value):
        if value is None:
            return
        text = str(value).replace("-", "_").replace(".", "_").replace("/", "_")
        tokens.append(text.lower())

    def _token_match(self, tokens: list, signal: str):
        normalized = str(signal or "").lower().replace(".", "_").replace("-", "_")
        return any(normalized in token for token in tokens)

    def _is_architecturally_eligible_class(self, cls: dict, file_model: dict):
        name = str(cls.get("name") or "")
        path = str(cls.get("filePath") or file_model.get("path") or "").lower().replace("\\", "/")
        qn = str(self._qualified_name(cls) or name).lower()

        if not name:
            return False
        if name in {"R", "BuildConfig"} or name.endswith("R"):
            return False
        if "/build/generated/" in path or "/androidtest/" in path or "/test/" in path:
            return False
        if qn.startswith("android.") or qn.startswith("java.") or qn.startswith("junit.") or qn.startswith("org.junit"):
            return False
        if name.endswith("Activity"):
            return False

        lowered_name = name.lower()
        eligible_terms = ["manager", "adapter", "helper", "rule", "filter", "profile", "context", "sensor", "effector", "service", "knowledge"]
        if any(term in lowered_name for term in eligible_terms):
            return True
        if "/context/" in path or "/database/" in path:
            return True
        return False

    def _contains_any(self, text: str, terms: list):
        lowered = str(text or "").lower()
        return any(term.lower() in lowered for term in terms)

    def _matching_methods(self, methods: list, terms: list):
        matches = []
        for method in methods:
            method_name = str(method.get("name", "")).lower()
            for term in terms:
                if term.lower() in method_name:
                    matches.append(method.get("name"))
                    break
        return matches

    def _relationship_hints(self, methods: list, role: str):
        role_terms = {
            "Monitor": ["analyze", "analyser", "analyzer", "knowledge", "sensor", "context"],
            "Analyzer": ["plan", "planner", "knowledge", "symptom", "rule", "filter"],
            "Planner": ["execute", "executor", "alternative", "strategy", "priority"],
            "Executor": ["effector", "actuator", "apply", "reconfigure", "audiomanager", "settings"],
            "Knowledge": ["monitor", "analyzer", "planner", "executor", "rule", "profile", "filter"],
            "Sensor": ["monitor", "location", "bluetooth"],
            "Effector": ["executor", "audio", "settings"],
            "LoopManager": ["monitor", "analyzer", "planner", "executor", "intent", "broadcast"],
        }.get(role, [])
        matches = []
        for method in methods:
            for call in method.get("calls", []) or []:
                call_name = self._call_display_name(call).lower()
                for term in role_terms:
                    if term in call_name:
                        matches.append(call.get("name") or call.get("methodName") or call_name)
                        break
        return matches

    def _decorator_matches_role(self, decorator_text: str, term: str):
        normalized = decorator_text.replace("()", "")
        return normalized == term or normalized.endswith(f".{term}") or f".{term}(" in decorator_text or normalized.endswith(f".{term}()")

    def _extract_loop_hint_from_decorator(self, decorator):
        decorator_text = str(decorator)
        if "." in decorator_text:
            return decorator_text.split(".")[0]
        return None

    def _extract_loop_hint_from_call(self, call: dict):
        receiver = call.get("receiver") or call.get("scope")
        if receiver:
            return str(receiver).split(".")[0]
        name = call.get("name") or call.get("methodName")
        if name and "." in str(name):
            return str(name).split(".")[0]
        return None

    def _call_display_name(self, call: dict):
        for key in ["name", "methodName", "qualified_name", "function", "method", "resolvedTarget", "targetId"]:
            if call.get(key):
                return str(call.get(key))
        receiver = call.get("receiver") or call.get("scope")
        method = call.get("method") or call.get("methodName")
        if receiver and method:
            return f"{receiver}.{method}"
        return ""

    def _qualified_name(self, cls: dict):
        if not cls:
            return None
        return cls.get("qualifiedName") or cls.get("qualified_name") or cls.get("name")

    def _callable_qualified_name(self, callable_model: dict):
        return callable_model.get("qualifiedName") or callable_model.get("qualified_name") or callable_model.get("qualifiedSignature") or callable_model.get("name")

    def _status_from_confidence(self, confidence: float):
        if confidence >= 0.85:
            return "auto_accepted"
        if confidence >= 0.60:
            return "needs_review"
        return "weak_suggestion"

    def _deduplicate_suggestions(self, suggestions: list):
        by_key = {}
        for suggestion in suggestions:
            key = (suggestion.get("code_element_id"), suggestion.get("suggested_role"))
            current = by_key.get(key)
            if current is None or suggestion.get("confidence", 0.0) > current.get("confidence", 0.0):
                by_key[key] = suggestion
        return list(by_key.values())
