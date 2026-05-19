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
            self._append_terms(corpus, file_model.get("name"))
            self._append_terms(corpus, file_model.get("path"))
            self._append_terms(corpus, file_model.get("qualified_name"))

            for import_model in file_model.get("imports", []):
                self._append_terms(corpus, import_model.get("module"))
                self._append_terms(corpus, import_model.get("name"))
                self._append_terms(corpus, import_model.get("alias"))

            for cls in file_model.get("classes", []):
                self._append_terms(corpus, cls.get("name"))
                self._append_terms(corpus, cls.get("qualified_name"))

                for base in cls.get("bases", []):
                    self._append_terms(corpus, base)

                for method in cls.get("methods", []):
                    self._append_terms(corpus, method.get("name"))
                    self._append_terms(corpus, method.get("qualified_name"))
                    self._append_terms(corpus, method.get("return_annotation"))

                    for call in method.get("calls", []):
                        self._append_terms(corpus, call.get("name"))
                        self._append_terms(corpus, call.get("receiver"))
                        self._append_terms(corpus, call.get("method"))
                        self._append_terms(corpus, call.get("function"))

                for attr in cls.get("attributes", []):
                    self._append_terms(corpus, attr.get("name"))

                for attr in cls.get("instance_attributes", []):
                    self._append_terms(corpus, attr.get("name"))
                    self._append_terms(corpus, attr.get("full_name"))

            for func in file_model.get("functions", []):
                self._append_terms(corpus, func.get("name"))
                self._append_terms(corpus, func.get("qualified_name"))

                for call in func.get("calls", []):
                    self._append_terms(corpus, call.get("name"))
                    self._append_terms(corpus, call.get("receiver"))
                    self._append_terms(corpus, call.get("method"))
                    self._append_terms(corpus, call.get("function"))

        return corpus

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

        for file_model in project_model.get("files", []):
            for cls in file_model.get("classes", []):
                role = self._role_from_name(cls.get("name", ""))
                if role:
                    role_by_class_id[cls.get("id")] = role

        if len(set(role_by_class_id.values())) < 2:
            return []

        relations_between_roles = []

        for file_model in project_model.get("files", []):
            for cls in file_model.get("classes", []):
                source_role = role_by_class_id.get(cls.get("id"))

                if source_role is None:
                    continue

                for method in cls.get("methods", []):
                    for call in method.get("calls", []):
                        target_id = call.get("target_id")
                        target_role = role_by_class_id.get(target_id)

                        if target_role and target_role != source_role:
                            relations_between_roles.append(
                                f"{source_role}->{target_role}"
                            )

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
