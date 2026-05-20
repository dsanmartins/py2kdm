class SemanticArchitectureRules:
    """
    Rule set used during architecture construction.

    This is not a post-hoc validator. The rules are used by recoverers to avoid
    creating semantically invalid architecture relations and to explain partial
    constructions.
    """

    CONTROL_LOOP_INTERNAL_ROLES = {
        "Monitor", "Analyzer", "Planner", "Executor", "Knowledge", "ReferenceInput",
    }

    MAPE_CORE_ROLES = {"Monitor", "Analyzer", "Planner", "Executor"}
    MANAGED_ROLES = {"Sensor", "Effector", "MeasuredOutput"}

    def __init__(self):
        self.applied_rules = []
        self.warnings = []
        self.blocked_constructions = []

    def can_contain(self, source_id, source_role, target_id, target_role, context=None):
        context = context or {}

        allowed = self._can_contain_without_side_effects(
            source_role=source_role,
            target_role=target_role,
            context=context,
        )

        if allowed:
            self.applied_rules.append(
                {
                    "rule_id": "CONTAIN-OK",
                    "level": "ok",
                    "source": source_id,
                    "target": target_id,
                    "message": (
                        f"{source_role} can contain {target_role} in the "
                        "Adaptive System Domain."
                    ),
                }
            )
            return True

        self.blocked_constructions.append(
            {
                "rule_id": "CONTAIN-FORBIDDEN",
                "level": "blocked",
                "source": source_id,
                "target": target_id,
                "message": (
                    f"Blocked containment: {source_role} cannot directly "
                    f"contain {target_role} in the current architecture hierarchy."
                ),
            }
        )
        return False

    def _can_contain_without_side_effects(self, source_role, target_role, context):
        if source_role == "Managing Subsystem":
            if target_role == "CL Manager":
                return True
            if target_role == "Control Loop" and not context.get("has_loop_manager"):
                return True
            return False

        if source_role == "CL Manager":
            return target_role == "Control Loop"

        if source_role == "Control Loop":
            return target_role in self.CONTROL_LOOP_INTERNAL_ROLES

        if source_role == "Managed Subsystem":
            return target_role in self.MANAGED_ROLES

        return False

    def assess_control_loop(self, loop):
        roles = set(loop.get("roles_present", []))
        loop_id = loop.get("id")
        missing_core = sorted(self.MAPE_CORE_ROLES - roles)

        if missing_core:
            self.warnings.append(
                {
                    "rule_id": "LOOP-W01",
                    "level": "warning",
                    "target": loop_id,
                    "message": (
                        "Control Loop is partial. Missing core MAPE role(s): "
                        + ", ".join(missing_core)
                    ),
                }
            )
        else:
            self.applied_rules.append(
                {
                    "rule_id": "LOOP-OK01",
                    "level": "ok",
                    "target": loop_id,
                    "message": "Control Loop contains all core MAPE roles.",
                }
            )

        if "Knowledge" not in roles:
            self.warnings.append(
                {
                    "rule_id": "LOOP-W02",
                    "level": "warning",
                    "target": loop_id,
                    "message": "Control Loop has no explicit Knowledge component.",
                }
            )

    def assess_control_io_presence(self, components):
        roles = {component.get("role") for component in components}

        if "ReferenceInput" not in roles:
            self.warnings.append(
                {
                    "rule_id": "CTRL-W01",
                    "level": "warning",
                    "message": "No Reference Input was recovered.",
                }
            )

        if "MeasuredOutput" not in roles:
            self.warnings.append(
                {
                    "rule_id": "CTRL-W02",
                    "level": "warning",
                    "message": "No Measured Output was recovered.",
                }
            )

        if "Sensor" not in roles:
            self.warnings.append(
                {
                    "rule_id": "CTRL-W03",
                    "level": "warning",
                    "message": "No Sensor was recovered.",
                }
            )

    def report(self):
        if self.blocked_constructions:
            status = "constructed_with_blocked_relations"
        elif self.warnings:
            status = "constructed_with_warnings"
        else:
            status = "constructed"

        return {
            "status": status,
            "interpretation": (
                "This is a construction report, not a post-hoc validation. "
                "The architecture was generated using semantic construction "
                "rules that block invalid containments and record partial "
                "recoveries as warnings."
            ),
            "applied_rules": self.applied_rules,
            "warnings": self.warnings,
            "blocked_constructions": self.blocked_constructions,
        }
