class AutonomicApplicabilityGate:
    """
    Decides whether MAPE-K recovery should be activated.

    The gate prevents conventional systems, such as simple layered systems, from
    being over-interpreted as self-adaptive systems.

    The decision is based on visible rules. Each rule contributes evidence and a
    weighted score. A single syntactic hint is not enough to activate MAPE-K
    recovery.
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
            "weight": 0.25,
            "description": (
                "Detects several distinct MAPE-K role terms in classes, "
                "methods or modules."
            ),
        },
        {
            "id": "SAS-GATE-03",
            "name": "Sensor or runtime observation evidence",
            "weight": 0.15,
            "description": (
                "Detects components or methods that collect measurements, "
                "status, metrics or runtime data."
            ),
        },
        {
            "id": "SAS-GATE-04",
            "name": "Effector or adaptation action evidence",
            "weight": 0.15,
            "description": (
                "Detects components or methods that apply changes, execute "
                "plans, reconfigure or adapt the managed system."
            ),
        },
        {
            "id": "SAS-GATE-05",
            "name": "Shared knowledge evidence",
            "weight": 0.15,
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
    ]

    EXPLICIT_AUTONOMIC_TERMS = {
        "adapt",
        "adaptive",
        "adaptation",
        "autonomic",
        "selfadaptive",
        "self_adaptive",
        "self-adaptive",
        "feedback",
        "feedbackloop",
        "controlloop",
        "mape",
        "mapek",
        "reconfigure",
        "reconfiguration",
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
        "sensor",
        "probe",
        "metric",
        "measure",
        "measurement",
        "collect",
        "observe",
        "status",
        "runtime",
        "telemetry",
    }

    EFFECTOR_TERMS = {
        "effector",
        "actuator",
        "execute",
        "apply",
        "reconfigure",
        "adapt",
        "restart",
        "scale",
        "change",
        "deploy",
    }

    KNOWLEDGE_TERMS = {
        "knowledge",
        "context",
        "runtime_model",
        "model",
        "state",
        "repository",
        "history",
        "log",
    }

    def __init__(
        self,
        not_applicable_threshold: float = 0.40,
        candidate_threshold: float = 0.70,
    ):
        self.not_applicable_threshold = not_applicable_threshold
        self.candidate_threshold = candidate_threshold

    def evaluate(self, project_model: dict):
        """
        Evaluates whether the project contains enough evidence to activate
        MAPE-K recovery.
        """

        corpus = self._build_corpus(project_model)
        matched_rules = []
        evidence = []
        score = 0.0

        result = self._rule_explicit_autonomic_vocabulary(corpus)
        if result:
            score += self._weight("SAS-GATE-01")
            matched_rules.append("SAS-GATE-01")
            evidence.extend(result)

        result = self._rule_mapek_role_vocabulary(corpus)
        if result:
            score += self._weight("SAS-GATE-02")
            matched_rules.append("SAS-GATE-02")
            evidence.extend(result)

        result = self._rule_sensor_evidence(corpus)
        if result:
            score += self._weight("SAS-GATE-03")
            matched_rules.append("SAS-GATE-03")
            evidence.extend(result)

        result = self._rule_effector_evidence(corpus)
        if result:
            score += self._weight("SAS-GATE-04")
            matched_rules.append("SAS-GATE-04")
            evidence.extend(result)

        result = self._rule_knowledge_evidence(corpus)
        if result:
            score += self._weight("SAS-GATE-05")
            matched_rules.append("SAS-GATE-05")
            evidence.extend(result)

        result = self._rule_partial_control_loop_relations(project_model)
        if result:
            score += self._weight("SAS-GATE-06")
            matched_rules.append("SAS-GATE-06")
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
                "Sufficient evidence of self-adaptive behavior was found. "
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

    def _build_corpus(self, project_model: dict):
        corpus = []

        for file_model in project_model.get("files", []):
            self._append_terms(corpus, self._value(file_model, "name"))
            self._append_terms(corpus, self._value(file_model, "path"))
            self._append_terms(corpus, self._value(file_model, "qualified_name"))

            for import_model in file_model.get("imports", []):
                self._append_import_terms(corpus, import_model)

            for cls in self._iter_classes_from_file(file_model):
                self._append_class_terms(corpus, cls)

            for func in file_model.get("functions", []):
                self._append_callable_terms(corpus, func)

        # Java extractor output stores the main code entities at top-level
        # under elements[]. Keep this support here so the MAPE-K gate works
        # for both Python and Java models.
        for element in project_model.get("elements", []):
            kind = str(self._value(element, "kind", "type") or "").lower()

            if kind in {"class", "interface", "enum"}:
                self._append_class_terms(corpus, element)
            else:
                self._append_element_terms(corpus, element)

        for relationship in project_model.get("relationships", []):
            self._append_relationship_terms(corpus, relationship)

        return corpus

    def _append_import_terms(self, corpus: list, import_model):
        if isinstance(import_model, dict):
            self._append_terms(corpus, self._value(import_model, "module"))
            self._append_terms(corpus, self._value(import_model, "name"))
            self._append_terms(corpus, self._value(import_model, "alias"))
            self._append_terms(corpus, self._value(import_model, "qualifiedName", "qualified_name"))
        else:
            self._append_terms(corpus, import_model)

    def _append_class_terms(self, corpus: list, cls: dict):
        self._append_element_terms(corpus, cls)

        for base in cls.get("bases", []):
            self._append_terms(corpus, base)

        for base in cls.get("superTypes", []):
            self._append_terms(corpus, base)

        for interface in cls.get("interfaces", []):
            self._append_terms(corpus, interface)

        for field in cls.get("fields", []):
            self._append_element_terms(corpus, field)

        for attr in cls.get("attributes", []):
            self._append_element_terms(corpus, attr)

        for attr in cls.get("instance_attributes", []):
            self._append_element_terms(corpus, attr)

        for variable in cls.get("variables", []):
            self._append_element_terms(corpus, variable)

        for method in cls.get("methods", []):
            self._append_callable_terms(corpus, method)

    def _append_callable_terms(self, corpus: list, callable_model: dict):
        self._append_element_terms(corpus, callable_model)
        self._append_terms(corpus, self._value(callable_model, "return_annotation", "returnType"))
        self._append_terms(corpus, self._value(callable_model, "qualifiedSignature"))

        for annotation in callable_model.get("annotations", []):
            self._append_terms(corpus, annotation)

        for decorator in callable_model.get("decorators", []):
            self._append_terms(corpus, decorator)

        for parameter in callable_model.get("parameters", []):
            self._append_element_terms(corpus, parameter)

        for variable in callable_model.get("local_variables", []):
            self._append_element_terms(corpus, variable)

        for variable in callable_model.get("variables", []):
            self._append_element_terms(corpus, variable)

        for call in callable_model.get("calls", []):
            self._append_call_terms(corpus, call)

    def _append_call_terms(self, corpus: list, call):
        if isinstance(call, dict):
            for key in [
                "name",
                "qualified_name",
                "qualifiedName",
                "receiver",
                "method",
                "function",
                "target",
                "targetName",
                "targetQualifiedName",
            ]:
                self._append_terms(corpus, call.get(key))
        else:
            self._append_terms(corpus, call)

    def _append_relationship_terms(self, corpus: list, relationship):
        if isinstance(relationship, dict):
            for key in [
                "type",
                "kind",
                "source",
                "sourceName",
                "sourceQualifiedName",
                "target",
                "targetName",
                "targetQualifiedName",
            ]:
                self._append_terms(corpus, relationship.get(key))
        else:
            self._append_terms(corpus, relationship)

    def _append_element_terms(self, corpus: list, element):
        if isinstance(element, dict):
            for key in [
                "name",
                "qualified_name",
                "qualifiedName",
                "full_name",
                "fullName",
                "path",
                "type",
                "kind",
                "assigned_type",
                "assignedType",
                "fieldType",
                "returnType",
            ]:
                self._append_terms(corpus, element.get(key))
        else:
            self._append_terms(corpus, element)

    def _iter_classes_from_file(self, file_model: dict):
        for cls in file_model.get("classes", []):
            yield cls

        # Some extractors may store file-level elements instead of classes.
        for element in file_model.get("elements", []):
            kind = str(self._value(element, "kind", "type") or "").lower()
            if kind in {"class", "interface", "enum"}:
                yield element

    def _iter_all_classes(self, project_model: dict):
        for file_model in project_model.get("files", []):
            yield from self._iter_classes_from_file(file_model)

        for element in project_model.get("elements", []):
            kind = str(self._value(element, "kind", "type") or "").lower()
            if kind in {"class", "interface", "enum"}:
                yield element

    def _iter_class_methods(self, cls: dict):
        for method in cls.get("methods", []):
            yield method

    def _value(self, data: dict, *keys):
        if not isinstance(data, dict):
            return None

        for key in keys:
            if key in data and data.get(key) is not None:
                return data.get(key)

        return None

    def _append_terms(self, corpus: list, value):
        if value is None:
            return

        text = str(value).replace("-", "_").replace(".", "_")
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

        return [
            {
                "rule_id": "SAS-GATE-01",
                "message": (
                    "Explicit self-adaptation vocabulary detected: "
                    + ", ".join(matches)
                ),
            }
        ]

    def _rule_mapek_role_vocabulary(self, corpus: list):
        detected_roles = set()

        for item in corpus:
            for term, role in self.ROLE_TERMS.items():
                if term in item:
                    detected_roles.add(role)

        if len(detected_roles) < 3:
            return []

        return [
            {
                "rule_id": "SAS-GATE-02",
                "message": (
                    "At least three MAPE-K role terms detected: "
                    + ", ".join(sorted(detected_roles))
                ),
            }
        ]

    def _rule_sensor_evidence(self, corpus: list):
        matches = self._contains_any(corpus, self.SENSOR_TERMS)

        if not matches:
            return []

        return [
            {
                "rule_id": "SAS-GATE-03",
                "message": "Sensor/runtime observation evidence: " + ", ".join(matches),
            }
        ]

    def _rule_effector_evidence(self, corpus: list):
        matches = self._contains_any(corpus, self.EFFECTOR_TERMS)

        if not matches:
            return []

        return [
            {
                "rule_id": "SAS-GATE-04",
                "message": "Effector/adaptation action evidence: " + ", ".join(matches),
            }
        ]

    def _rule_knowledge_evidence(self, corpus: list):
        matches = self._contains_any(corpus, self.KNOWLEDGE_TERMS)

        if not matches:
            return []

        return [
            {
                "rule_id": "SAS-GATE-05",
                "message": "Knowledge/shared-state evidence: " + ", ".join(matches),
            }
        ]

    def _rule_partial_control_loop_relations(self, project_model: dict):
        role_by_class_id = {}
        role_by_class_name = {}

        for cls in self._iter_all_classes(project_model):
            name = self._value(cls, "name", "qualified_name", "qualifiedName")
            role = self._role_from_name(name)

            if not role:
                continue

            class_id = self._value(cls, "id")
            qualified_name = self._value(cls, "qualified_name", "qualifiedName", "name")

            if class_id:
                role_by_class_id[class_id] = role

            if qualified_name:
                role_by_class_name[str(qualified_name)] = role
                role_by_class_name[str(qualified_name).split(".")[-1]] = role

        if len(set(role_by_class_id.values()) | set(role_by_class_name.values())) < 2:
            return []

        relations_between_roles = []

        for cls in self._iter_all_classes(project_model):
            source_role = self._role_for_element(cls, role_by_class_id, role_by_class_name)

            if source_role is None:
                continue

            for method in self._iter_class_methods(cls):
                for call in method.get("calls", []):
                    target_role = self._role_for_call(call, role_by_class_id, role_by_class_name)

                    if target_role and target_role != source_role:
                        relations_between_roles.append(f"{source_role}->{target_role}")

        # Java models may expose inter-class dependencies at project level.
        for relationship in project_model.get("relationships", []):
            if not isinstance(relationship, dict):
                continue

            source_role = self._role_for_relationship_endpoint(
                relationship,
                role_by_class_id,
                role_by_class_name,
                prefix="source",
            )
            target_role = self._role_for_relationship_endpoint(
                relationship,
                role_by_class_id,
                role_by_class_name,
                prefix="target",
            )

            if source_role and target_role and source_role != target_role:
                relations_between_roles.append(f"{source_role}->{target_role}")

        if not relations_between_roles:
            return []

        return [
            {
                "rule_id": "SAS-GATE-06",
                "message": (
                    "Relations between candidate MAPE-K roles detected: "
                    + ", ".join(sorted(set(relations_between_roles)))
                ),
            }
        ]

    def _role_for_element(self, element, role_by_id: dict, role_by_name: dict):
        if not isinstance(element, dict):
            return None

        element_id = self._value(element, "id")
        if element_id in role_by_id:
            return role_by_id[element_id]

        for key in ["qualified_name", "qualifiedName", "name"]:
            value = self._value(element, key)
            if value and str(value) in role_by_name:
                return role_by_name[str(value)]
            if value and str(value).split(".")[-1] in role_by_name:
                return role_by_name[str(value).split(".")[-1]]

        return None

    def _role_for_call(self, call, role_by_id: dict, role_by_name: dict):
        if isinstance(call, dict):
            target_id = self._value(call, "target_id", "targetId")
            if target_id in role_by_id:
                return role_by_id[target_id]

            for key in [
                "target",
                "targetName",
                "targetQualifiedName",
                "qualified_name",
                "qualifiedName",
                "name",
                "receiver",
                "function",
                "method",
            ]:
                value = self._value(call, key)
                role = self._role_from_text_or_index(value, role_by_name)
                if role:
                    return role
        else:
            return self._role_from_text_or_index(call, role_by_name)

        return None

    def _role_for_relationship_endpoint(
        self,
        relationship: dict,
        role_by_id: dict,
        role_by_name: dict,
        prefix: str,
    ):
        candidate_keys = [
            prefix,
            f"{prefix}Id",
            f"{prefix}_id",
            f"{prefix}Name",
            f"{prefix}QualifiedName",
            f"{prefix}_qualified_name",
        ]

        for key in candidate_keys:
            value = self._value(relationship, key)

            if value in role_by_id:
                return role_by_id[value]

            role = self._role_from_text_or_index(value, role_by_name)
            if role:
                return role

        return None

    def _role_from_text_or_index(self, value, role_by_name: dict):
        if value is None:
            return None

        text = str(value)

        if text in role_by_name:
            return role_by_name[text]

        short_name = text.split(".")[-1]
        if short_name in role_by_name:
            return role_by_name[short_name]

        return self._role_from_name(text)

    def _role_from_name(self, name: str):
        lowered = str(name or "").lower()

        for term, role in self.ROLE_TERMS.items():
            if term in lowered:
                return role

        return None

    def _weight(self, rule_id: str):
        for rule in self.RULES:
            if rule["id"] == rule_id:
                return rule["weight"]

        return 0.0
