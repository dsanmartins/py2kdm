class AutonomicApplicabilityGate:
    """
    Decides whether MAPE-K recovery should be activated.

    The gate combines explicit vocabulary with static responsibility evidence.
    It does not depend on expert comments. The strongest rule is based on
    syntactic-semantic evidence extracted from the JSON/KDM model: sensors,
    event flow, rule evaluation, planning/selection, effectors and knowledge.
    """

    RULES = [
        {
            "id": "SAS-GATE-01",
            "name": "Explicit self-adaptation vocabulary",
            "weight": 0.20,
            "description": (
                "Detects explicit vocabulary related to adaptation, autonomic "
                "computing, feedback loops or MAPE-K."
            ),
        },
        {
            "id": "SAS-GATE-02",
            "name": "MAPE-K role vocabulary",
            "weight": 0.20,
            "description": (
                "Detects several distinct MAPE-K role terms in classes, "
                "methods or modules."
            ),
        },
        {
            "id": "SAS-GATE-03",
            "name": "Sensor or runtime observation evidence",
            "weight": 0.12,
            "description": (
                "Detects components or methods that collect measurements, "
                "status, metrics or runtime data."
            ),
        },
        {
            "id": "SAS-GATE-04",
            "name": "Effector or adaptation action evidence",
            "weight": 0.12,
            "description": (
                "Detects components or methods that apply changes, execute "
                "plans, reconfigure or adapt the managed system."
            ),
        },
        {
            "id": "SAS-GATE-05",
            "name": "Shared knowledge evidence",
            "weight": 0.12,
            "description": (
                "Detects knowledge, model, state, context or repository-like "
                "elements used as shared adaptation data."
            ),
        },
        {
            "id": "SAS-GATE-06",
            "name": "Partial control-loop relation evidence",
            "weight": 0.10,
            "description": (
                "Detects call or dependency evidence connecting at least two "
                "candidate MAPE-K roles."
            ),
        },
        {
            "id": "SAS-GATE-07",
            "name": "Responsibility and technology role coverage",
            "weight": 0.30,
            "description": (
                "Detects Monitor, Analyzer, Planner, Executor and Knowledge "
                "responsibilities using static syntactic-semantic evidence "
                "such as Android APIs, database access, rule evaluation and "
                "event-based control flow."
            ),
        },
    ]

    EXPLICIT_AUTONOMIC_TERMS = {
        "adapt", "adaptive", "adaptation", "autonomic", "selfadaptive",
        "self_adaptive", "self-adaptive", "feedback", "feedbackloop",
        "controlloop", "mape", "mapek", "reconfigure", "reconfiguration",
    }

    ROLE_TERMS = {
        "monitor": "Monitor",
        "analyzer": "Analyzer",
        "analyser": "Analyzer",
        "planner": "Planner",
        "executor": "Executor",
        "knowledge": "Knowledge",
        "sensor": "Sensor",
        "effector": "Effector",
    }

    SENSOR_TERMS = {
        "sensor", "probe", "metric", "measure", "measurement", "collect",
        "observe", "status", "runtime", "telemetry", "locationmanager",
        "locationlistener", "bluetoothadapter", "bluetoothdevice",
        "broadcastreceiver", "intentservice",
    }

    EFFECTOR_TERMS = {
        "effector", "actuator", "execute", "apply", "reconfigure", "adapt",
        "restart", "scale", "change", "deploy", "audiomanager",
        "settings_system", "setstreamvolume", "setringermode", "putint",
    }

    KNOWLEDGE_TERMS = {
        "knowledge", "context", "runtime_model", "model", "state",
        "repository", "history", "log", "sqlitedatabase", "sqliteopenhelper",
        "mydbadapter", "rule", "filter", "profile",
    }

    RESPONSIBILITY_SIGNALS = {
        "Monitor": {
            "contextmanager", "locationmanager", "locationlistener",
            "bluetoothadapter", "bluetoothdevice", "broadcastreceiver",
            "intentservice", "getsystemservice", "requestlocationupdates",
            "getlastknownlocation", "registerreceiver", "putextra",
            "gps_available", "gps_location", "gps_speed", "bt_device_list",
            "weekday", "time",
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
        "Knowledge": {
            "mydbadapter", "mydbhelper", "sqlitedatabase", "sqliteopenhelper",
            "cursor", "contentvalues", "table_rule", "table_filter",
            "table_profile", "table_constant", "fetch", "insert", "update",
            "delete", "rule", "filter", "profile", "contextconstant",
        },
    }

    CONTROL_FLOW_SIGNALS = {
        "sendbroadcast", "registerreceiver", "onreceive", "intent", "intentfilter",
        "putextra", "getbooleanextra", "getstringextra", "getdoubleextra",
        "startservice", "intentservice", "newcontext",
    }

    def __init__(
        self,
        not_applicable_threshold: float = 0.40,
        candidate_threshold: float = 0.70,
    ):
        self.not_applicable_threshold = not_applicable_threshold
        self.candidate_threshold = candidate_threshold

    def evaluate(self, project_model: dict):
        corpus = self._build_corpus(project_model)
        matched_rules = []
        evidence = []
        score = 0.0

        for rule_id, rule_fn in [
            ("SAS-GATE-01", self._rule_explicit_autonomic_vocabulary),
            ("SAS-GATE-02", self._rule_mapek_role_vocabulary),
            ("SAS-GATE-03", self._rule_sensor_evidence),
            ("SAS-GATE-04", self._rule_effector_evidence),
            ("SAS-GATE-05", self._rule_knowledge_evidence),
        ]:
            result = rule_fn(corpus)
            if result:
                score += self._weight(rule_id)
                matched_rules.append(rule_id)
                evidence.extend(result)

        result = self._rule_partial_control_loop_relations(project_model)
        if result:
            score += self._weight("SAS-GATE-06")
            matched_rules.append("SAS-GATE-06")
            evidence.extend(result)

        result = self._rule_responsibility_and_technology_coverage(project_model)
        if result:
            score += self._weight("SAS-GATE-07")
            matched_rules.append("SAS-GATE-07")
            evidence.extend(result)

        score = round(min(score, 1.0), 2)

        if score < self.not_applicable_threshold:
            decision = "not_applicable"
            status = "mapek_recovery_disabled"
            reason = (
                "No sufficient evidence of a self-adaptive control loop was "
                "found. The system may be conventional, for example layered."
            )
        elif score < self.candidate_threshold:
            decision = "possible_autonomic_system"
            status = "needs_review"
            reason = (
                "Some self-adaptive evidence was found, but it is not strong "
                "enough to activate automatic MAPE-K recovery without review."
            )
        else:
            decision = "candidate_autonomic_system"
            status = "mapek_recovery_enabled"
            reason = (
                "Sufficient static evidence of self-adaptive behavior was found. "
                "MAPE-K recovery can be activated."
            )

        return {
            "decision": decision,
            "status": status,
            "score": score,
            "matched_rules": matched_rules,
            "evidence": evidence,
            "reason": reason,
            "thresholds": {
                "not_applicable": self.not_applicable_threshold,
                "candidate": self.candidate_threshold,
            },
            "visible_rules": self.RULES,
        }

    # ------------------------------------------------------------
    # Corpus and basic rules
    # ------------------------------------------------------------

    def _build_corpus(self, project_model: dict):
        corpus = []

        for file_model in project_model.get("files", []):
            self._append_terms(corpus, file_model.get("name"))
            self._append_terms(corpus, file_model.get("path"))
            self._append_terms(corpus, file_model.get("qualified_name"))
            self._append_terms(corpus, file_model.get("packageName"))

            for import_model in file_model.get("imports", []):
                if isinstance(import_model, dict):
                    self._append_terms(corpus, import_model.get("module"))
                    self._append_terms(corpus, import_model.get("name"))
                    self._append_terms(corpus, import_model.get("alias"))
                else:
                    self._append_terms(corpus, import_model)

        for cls, file_model in self._iter_classes(project_model):
            self._append_terms(corpus, cls.get("name"))
            self._append_terms(corpus, cls.get("qualifiedName"))
            self._append_terms(corpus, cls.get("qualified_name"))
            self._append_terms(corpus, cls.get("packageName"))
            self._append_terms(corpus, cls.get("filePath"))

            for base in cls.get("bases", []) + cls.get("extendsTypes", []) + cls.get("implementsTypes", []):
                self._append_terms(corpus, base)

            for field in cls.get("fields", []) + cls.get("attributes", []) + cls.get("instance_attributes", []):
                self._append_terms(corpus, field.get("name") if isinstance(field, dict) else field)
                if isinstance(field, dict):
                    self._append_terms(corpus, field.get("type"))
                    self._append_terms(corpus, field.get("resolvedType"))

            for method in cls.get("methods", []):
                self._append_terms(corpus, method.get("name"))
                self._append_terms(corpus, method.get("qualifiedName"))
                self._append_terms(corpus, method.get("qualified_name"))
                self._append_terms(corpus, method.get("returnType"))
                self._append_terms(corpus, method.get("return_annotation"))
                self._append_callable_terms(corpus, method)

        for func in project_model.get("functions", []):
            self._append_terms(corpus, func.get("name"))
            self._append_terms(corpus, func.get("qualified_name"))
            self._append_callable_terms(corpus, func)

        return corpus

    def _append_callable_terms(self, corpus: list, callable_model: dict):
        for call in callable_model.get("calls", []):
            self._append_call_terms(corpus, call)

        for local in callable_model.get("localVariables", []) + callable_model.get("local_variables", []):
            if isinstance(local, dict):
                self._append_terms(corpus, local.get("name"))
                self._append_terms(corpus, local.get("type"))
                self._append_terms(corpus, local.get("assignedType"))
                self._append_terms(corpus, local.get("assignedValue"))

        for statement in callable_model.get("body", []):
            self._append_statement_terms(corpus, statement)

    def _append_statement_terms(self, corpus: list, statement: dict):
        if not isinstance(statement, dict):
            return

        for key in [
            "type", "statementType", "controlType", "condition", "selector",
            "value", "valueKind", "className", "exceptionType", "parameterName",
        ]:
            self._append_terms(corpus, statement.get(key))

        for target in statement.get("targets", []) or []:
            self._append_terms(corpus, target)

        for key in ["valueCall", "conditionCalls", "valueCalls", "exceptionCalls"]:
            value = statement.get(key)
            if isinstance(value, dict):
                self._append_call_terms(corpus, value)
            elif isinstance(value, list):
                for call in value:
                    self._append_call_terms(corpus, call)

        for nested_key in ["body", "elseBody", "finallyBody"]:
            for nested in statement.get(nested_key, []) or []:
                self._append_statement_terms(corpus, nested)

        for catch_clause in statement.get("catchClauses", []) or []:
            self._append_statement_terms(corpus, catch_clause)

    def _append_call_terms(self, corpus: list, call: dict):
        if not isinstance(call, dict):
            return

        for key in [
            "name", "methodName", "method", "function", "scope", "receiver",
            "resolvedTarget", "targetId", "classification", "kind",
        ]:
            self._append_terms(corpus, call.get(key))

        for argument in call.get("arguments", []) or []:
            self._append_terms(corpus, argument)

    def _append_terms(self, corpus: list, value):
        if value is None:
            return

        text = str(value).replace("-", "_").replace(".", "_").replace("/", "_")
        corpus.append(text.lower())

    def _contains_any(self, corpus: list, terms: set):
        matches = []

        for item in corpus:
            for term in terms:
                if term.lower() in item:
                    matches.append(term)

        return sorted(set(matches))

    def _rule_explicit_autonomic_vocabulary(self, corpus: list):
        matches = self._contains_any(corpus, self.EXPLICIT_AUTONOMIC_TERMS)
        if not matches:
            return []
        return [{"rule_id": "SAS-GATE-01", "message": "Explicit self-adaptation vocabulary detected: " + ", ".join(matches)}]

    def _rule_mapek_role_vocabulary(self, corpus: list):
        detected_roles = set()
        for item in corpus:
            for term, role in self.ROLE_TERMS.items():
                if term in item:
                    detected_roles.add(role)
        if len(detected_roles) < 3:
            return []
        return [{"rule_id": "SAS-GATE-02", "message": "At least three MAPE-K role terms detected: " + ", ".join(sorted(detected_roles))}]

    def _rule_sensor_evidence(self, corpus: list):
        matches = self._contains_any(corpus, self.SENSOR_TERMS)
        if not matches:
            return []
        return [{"rule_id": "SAS-GATE-03", "message": "Sensor/runtime observation evidence: " + ", ".join(matches)}]

    def _rule_effector_evidence(self, corpus: list):
        matches = self._contains_any(corpus, self.EFFECTOR_TERMS)
        if not matches:
            return []
        return [{"rule_id": "SAS-GATE-04", "message": "Effector/adaptation action evidence: " + ", ".join(matches)}]

    def _rule_knowledge_evidence(self, corpus: list):
        matches = self._contains_any(corpus, self.KNOWLEDGE_TERMS)
        if not matches:
            return []
        return [{"rule_id": "SAS-GATE-05", "message": "Knowledge/shared-state evidence: " + ", ".join(matches)}]

    # ------------------------------------------------------------
    # Responsibility evidence
    # ------------------------------------------------------------

    def _rule_responsibility_and_technology_coverage(self, project_model: dict):
        role_to_classes = {}
        flow_classes = []

        for cls, file_model in self._iter_classes(project_model):
            if not self._is_architecturally_eligible_class(cls, file_model):
                continue

            role_evidence = self._class_role_evidence(cls, file_model)
            if not role_evidence:
                continue

            for role, evidence in role_evidence.items():
                if not evidence:
                    continue
                role_to_classes.setdefault(role, []).append(
                    {
                        "class": self._class_display_name(cls),
                        "evidence": evidence[:4],
                    }
                )

            if self._class_has_control_flow_evidence(cls, file_model):
                flow_classes.append(self._class_display_name(cls))

        core_roles = {"Monitor", "Analyzer", "Planner", "Executor", "Knowledge"}
        present_core_roles = core_roles.intersection(role_to_classes.keys())

        # A candidate should show broad MAPE-K coverage, not just UI CRUD.
        if len(present_core_roles) < 4:
            return []

        messages = []
        for role in ["Monitor", "Analyzer", "Planner", "Executor", "Knowledge"]:
            entries = role_to_classes.get(role, [])
            if not entries:
                continue
            compact = []
            for entry in entries[:3]:
                compact.append(
                    f"{entry['class']} ({'; '.join(entry['evidence'][:2])})"
                )
            messages.append(f"{role}: " + ", ".join(compact))

        if flow_classes:
            messages.append(
                "Event/control-flow evidence: " + ", ".join(sorted(set(flow_classes))[:4])
            )

        return [
            {
                "rule_id": "SAS-GATE-07",
                "message": (
                    "MAPE-K responsibilities inferred from static responsibility "
                    "and technology evidence. " + " | ".join(messages)
                ),
                "roles_present": sorted(present_core_roles),
                "flow_evidence_classes": sorted(set(flow_classes)),
            }
        ]

    def _class_role_evidence(self, cls: dict, file_model: dict):
        tokens = self._class_tokens(cls, file_model)
        role_evidence = {}

        for role, signals in self.RESPONSIBILITY_SIGNALS.items():
            matches = sorted(signal for signal in signals if self._token_match(tokens, signal))
            if matches:
                role_evidence[role] = matches

        class_name = self._class_display_name(cls).lower()

        # Strong architectural canonicalization for common self-adaptive
        # components.  This is intentionally conservative: it cleans the gate
        # explanation, not the whole model. Database classes store rule/filter
        # schemas and profile fields, so terms such as priority, action or
        # airplane_mode are Knowledge evidence, not Analyzer/Planner/Executor
        # behaviour.
        role_evidence = self._canonicalize_role_evidence_for_known_components(
            class_name,
            role_evidence,
        )

        # Strong Java/Android class-name shortcuts after canonicalization.
        if "contextmanager" in class_name:
            role_evidence.setdefault("Monitor", []).append("class name ContextManager")
        if "adaptationmanager" in class_name:
            role_evidence.setdefault("Analyzer", []).append("class name AdaptationManager")
            role_evidence.setdefault("Planner", []).append("class name AdaptationManager")
            role_evidence.setdefault("Executor", []).append("class name AdaptationManager")
        if "mydbadapter" in class_name or "mydbhelper" in class_name:
            role_evidence.setdefault("Knowledge", []).append("database adapter/helper class")

        return role_evidence

    def _canonicalize_role_evidence_for_known_components(self, class_name: str, role_evidence: dict):
        """
        Cleans role evidence before SAS-GATE-07 formats its explanation.

        This method avoids noisy role assignments caused by vocabulary overlap.
        For example, MyDbAdapter contains rule/filter/priority/action fields,
        but its architectural responsibility is Knowledge.  ContextManager
        contains context and broadcast vocabulary, but it should be reported as
        Monitor/Sensor/LoopManager rather than Knowledge or Executor.
        """
        if not role_evidence:
            return role_evidence

        if "mydbadapter" in class_name or "mydbhelper" in class_name:
            knowledge = list(role_evidence.get("Knowledge", []))
            if not knowledge:
                knowledge = ["database adapter/helper class"]
            return {"Knowledge": knowledge}

        if "contextmanager" in class_name:
            cleaned = {}
            for role in ["Monitor", "Sensor"]:
                if role in role_evidence:
                    cleaned[role] = role_evidence[role]
            # Keep only genuinely strong executor evidence if it ever appears
            # in a future ContextManager-like class. Generic sendBroadcast or
            # putExtra are event-flow evidence, not Executor behaviour here.
            executor_matches = [
                item for item in role_evidence.get("Executor", [])
                if item in {
                    "audiomanager",
                    "settings",
                    "settings_system",
                    "setstreamvolume",
                    "setringermode",
                    "setvibratesetting",
                    "airplane_mode",
                    "action_airplane_mode_changed",
                    "ringer_mode",
                }
            ]
            if executor_matches:
                cleaned["Executor"] = executor_matches
            if not cleaned:
                cleaned["Monitor"] = ["class name ContextManager"]
            return cleaned

        if "adaptationmanager" in class_name:
            cleaned = {}
            for role in ["Analyzer", "Planner", "Executor", "Effector", "LoopManager"]:
                if role in role_evidence:
                    cleaned[role] = role_evidence[role]
            if "Analyzer" not in cleaned:
                cleaned["Analyzer"] = ["class name AdaptationManager"]
            if "Planner" not in cleaned:
                cleaned["Planner"] = ["class name AdaptationManager"]
            if "Executor" not in cleaned:
                cleaned["Executor"] = ["class name AdaptationManager"]
            return cleaned

        return role_evidence

    def _class_has_control_flow_evidence(self, cls: dict, file_model: dict):
        tokens = self._class_tokens(cls, file_model)
        return any(self._token_match(tokens, signal) for signal in self.CONTROL_FLOW_SIGNALS)

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

    def _token_match(self, tokens: list, signal: str):
        normalized = str(signal or "").lower().replace(".", "_").replace("-", "_")
        return any(normalized in token for token in tokens)

    # ------------------------------------------------------------
    # Control-loop relation evidence
    # ------------------------------------------------------------

    def _rule_partial_control_loop_relations(self, project_model: dict):
        role_by_class_id = {}
        for cls, file_model in self._iter_classes(project_model):
            role = self._role_from_name(cls.get("name", ""))
            if role:
                role_by_class_id[cls.get("id")] = role

        if len(set(role_by_class_id.values())) < 2:
            return []

        relations_between_roles = []
        for cls, file_model in self._iter_classes(project_model):
            source_role = role_by_class_id.get(cls.get("id"))
            if source_role is None:
                continue
            for method in cls.get("methods", []):
                for call in method.get("calls", []):
                    target_id = call.get("target_id") or call.get("targetId")
                    target_role = role_by_class_id.get(target_id)
                    if target_role and target_role != source_role:
                        relations_between_roles.append(f"{source_role}->{target_role}")

        if not relations_between_roles:
            return []

        return [{"rule_id": "SAS-GATE-06", "message": "Relations between candidate MAPE-K roles detected: " + ", ".join(sorted(set(relations_between_roles)))}]

    def _role_from_name(self, name: str):
        lowered = str(name or "").lower()
        for term, role in self.ROLE_TERMS.items():
            if term in lowered:
                return role
        return None

    # ------------------------------------------------------------
    # Class iteration and filtering
    # ------------------------------------------------------------

    def _iter_classes(self, project_model: dict):
        file_by_path = {file_model.get("path"): file_model for file_model in project_model.get("files", [])}

        seen = set()
        for file_model in project_model.get("files", []):
            for cls in file_model.get("classes", []) or []:
                key = cls.get("id") or cls.get("qualifiedName") or cls.get("qualified_name") or id(cls)
                seen.add(key)
                yield cls, file_model

        for element in project_model.get("elements", []) or []:
            if element.get("kind") != "class":
                continue
            key = element.get("id") or element.get("qualifiedName") or element.get("qualified_name") or id(element)
            if key in seen:
                continue
            file_model = file_by_path.get(element.get("filePath"), {})
            yield element, file_model

    def _is_architecturally_eligible_class(self, cls: dict, file_model: dict):
        name = self._class_display_name(cls)
        path = str(cls.get("filePath") or file_model.get("path") or "").lower().replace("\\", "/")
        qn = str(cls.get("qualifiedName") or cls.get("qualified_name") or name).lower()

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
        lowered_path = path.lower()
        eligible_terms = [
            "manager", "adapter", "helper", "rule", "filter", "profile",
            "context", "sensor", "effector", "service", "knowledge",
        ]
        if any(term in lowered_name for term in eligible_terms):
            return True
        if "/context/" in lowered_path or "/database/" in lowered_path:
            return True

        return False

    def _class_display_name(self, cls: dict):
        return str(cls.get("name") or cls.get("qualifiedName") or cls.get("qualified_name") or "")

    def _weight(self, rule_id: str):
        for rule in self.RULES:
            if rule["id"] == rule_id:
                return rule["weight"]
        return 0.0
