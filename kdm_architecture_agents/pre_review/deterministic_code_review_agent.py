from __future__ import annotations

from typing import Any


class DeterministicCodeReviewAgent:
    """
    Produces a deterministic, non-LLM review from the recovered architecture
    and the compact code_context.

    This agent is intentionally non-invasive: it does not modify
    structure_model. It only summarizes whether the recovered components and
    roles are supported by compact static code evidence.
    """

    CORE_MAPEK_ROLES = {"Monitor", "Analyzer", "Planner", "Executor", "Knowledge"}

    def run(self, model: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        code_context = context.get("code_context", {}) or {}
        structure_model = model.get("structure_model", {}) or {}
        architecture_recovery = model.get("architecture_recovery", {}) or {}
        applicability = architecture_recovery.get("autonomic_applicability", {}) or {}

        components = structure_model.get("components", []) or []
        loops = structure_model.get("control_loops", []) or []
        classes = code_context.get("classes", []) or []

        component_index = self._component_index(components)
        class_reviews = [
            self._review_class_against_architecture(cls, component_index)
            for cls in classes
        ]

        role_confirmations = self._build_role_confirmations(class_reviews)
        unsupported_architecture_roles = self._find_architecture_roles_without_code_support(
            components=components,
            class_reviews=class_reviews,
        )
        loop_review = self._review_loops(loops)
        assessment = self._build_assessment(
            applicability=applicability,
            role_confirmations=role_confirmations,
            unsupported_architecture_roles=unsupported_architecture_roles,
            loop_review=loop_review,
            code_context=code_context,
        )

        return {
            "status": "available" if code_context.get("available") else "code_context_unavailable",
            "source": "deterministic_code_review_agent",
            "non_invasive": True,
            "architecture_assessment": assessment,
            "role_confirmations": role_confirmations,
            "unsupported_architecture_roles": unsupported_architecture_roles,
            "class_reviews": class_reviews,
            "control_loop_review": loop_review,
            "summary": {
                "code_context_available": bool(code_context.get("available")),
                "classes_reviewed": len(class_reviews),
                "role_confirmations": len(role_confirmations),
                "unsupported_architecture_roles": len(unsupported_architecture_roles),
                "complete_loops": loop_review.get("complete_loops", 0),
            },
        }

    def _component_index(self, components: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        index: dict[str, list[dict[str, Any]]] = {}

        for component in components:
            keys = set()
            for key in ("name", "id"):
                value = component.get(key)
                if value:
                    keys.add(str(value))
                    keys.add(self._simple_name(str(value)))

            for implementation in component.get("implemented_by", []) or []:
                keys.add(str(implementation))
                keys.add(self._simple_name(str(implementation)))

            for key in keys:
                index.setdefault(key, []).append(component)

        return index

    def _review_class_against_architecture(
        self,
        cls: dict[str, Any],
        component_index: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        class_name = cls.get("name") or ""
        qualified_name = cls.get("qualified_name") or ""
        candidate_roles = set(cls.get("candidate_roles", []) or [])
        inferred_secondary_roles = self._infer_secondary_roles_from_code_context(cls)
        candidate_roles.update(inferred_secondary_roles)

        related_components = []
        for key in (class_name, qualified_name, self._simple_name(qualified_name)):
            for component in component_index.get(key, []):
                if component not in related_components:
                    related_components.append(component)

        related_roles = {
            component.get("role")
            for component in related_components
            if component.get("role")
        }
        confirmed_roles = sorted(candidate_roles & related_roles)
        code_only_roles = sorted(candidate_roles - related_roles)
        architecture_only_roles = sorted(related_roles - candidate_roles)

        status = "confirmed"
        if architecture_only_roles and confirmed_roles:
            status = "partially_confirmed"
        elif architecture_only_roles and not confirmed_roles:
            status = "needs_review"
        elif candidate_roles and not related_roles:
            status = "code_candidate_not_materialized"

        return {
            "class": class_name,
            "qualified_name": qualified_name,
            "file": cls.get("file"),
            "candidate_roles": sorted(candidate_roles),
            "inferred_secondary_roles": sorted(inferred_secondary_roles),
            "architecture_roles": sorted(related_roles),
            "confirmed_roles": confirmed_roles,
            "code_only_roles": code_only_roles,
            "architecture_only_roles": architecture_only_roles,
            "status": status,
            "evidence": cls.get("role_evidence", []) or [],
            "representative_methods": [
                {
                    "name": method.get("name"),
                    "signature": method.get("signature"),
                    "calls": method.get("calls", [])[:8],
                }
                for method in (cls.get("methods", []) or [])[:5]
            ],
        }

    def _infer_secondary_roles_from_code_context(self, cls: dict[str, Any]) -> set[str]:
        """
        Infers secondary architecture roles that may not be listed explicitly in
        code_context.candidate_roles.

        The compact code_context tends to list the core responsibilities
        (Monitor/Analyzer/Planner/Executor/Knowledge).  The recovered
        structure_model may also contain secondary roles such as Sensor and
        Effector.  These roles can be confirmed deterministically from the same
        code evidence:

        - Sensor: LocationManager, LocationListener, BluetoothAdapter,
          BluetoothDevice or sensor-like Android context APIs.
        - Effector: AudioManager, Settings.System, setStreamVolume,
          setRingerMode, setVibrateSetting, putInt or similar actuator APIs.
        """
        text = self._class_search_text(cls)

        inferred: set[str] = set()

        sensor_tokens = (
            "locationmanager",
            "locationlistener",
            "bluetoothadapter",
            "bluetoothdevice",
            "sensor",
            "gps",
            "onlocationchanged",
            "action_found",
            "action_discovery_started",
            "action_discovery_finished",
        )

        effector_tokens = (
            "audiomanager",
            "settings.system",
            "settings",
            "setstreamvolume",
            "setringermode",
            "setvibratesetting",
            "putint",
            "airplane_mode",
            "ringer_mode",
            "stream_music",
            "stream_ring",
        )

        if any(token in text for token in sensor_tokens):
            inferred.add("Sensor")

        if any(token in text for token in effector_tokens):
            inferred.add("Effector")

        return inferred

    def _class_search_text(self, cls: dict[str, Any]) -> str:
        parts: list[str] = []

        def add(value: Any) -> None:
            if value is None:
                return
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, (int, float, bool)):
                parts.append(str(value))
            elif isinstance(value, list):
                for item in value:
                    add(item)
            elif isinstance(value, dict):
                for item in value.values():
                    add(item)

        for key in (
            "name",
            "qualified_name",
            "package",
            "file",
            "extends",
            "implements",
            "imports",
            "fields",
            "methods",
            "role_evidence",
        ):
            add(cls.get(key))

        return " ".join(parts).lower()

    def _build_role_confirmations(self, class_reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
        confirmations = []

        for review in class_reviews:
            confirmed_roles = review.get("confirmed_roles", []) or []
            if not confirmed_roles:
                continue

            confirmations.append(
                {
                    "component": review.get("class"),
                    "qualified_name": review.get("qualified_name"),
                    "confirmed_roles": confirmed_roles,
                    "confidence": self._confidence_for_confirmation(confirmed_roles, review),
                    "evidence": review.get("evidence", [])[:5],
                    "representative_methods": review.get("representative_methods", [])[:3],
                }
            )

        return confirmations

    def _find_architecture_roles_without_code_support(
        self,
        components: list[dict[str, Any]],
        class_reviews: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        supported_pairs = set()
        for review in class_reviews:
            class_name = review.get("class")
            qualified_name = review.get("qualified_name")
            for role in review.get("confirmed_roles", []) or []:
                supported_pairs.add((class_name, role))
                supported_pairs.add((qualified_name, role))
                supported_pairs.add((self._simple_name(qualified_name), role))

        unsupported = []
        for component in components:
            role = component.get("role")
            if not role:
                continue
            implementations = component.get("implemented_by", []) or [component.get("name")]
            if any((impl, role) in supported_pairs or (self._simple_name(str(impl)), role) in supported_pairs for impl in implementations):
                continue
            unsupported.append(
                {
                    "component_id": component.get("id"),
                    "component": component.get("name"),
                    "role": role,
                    "implemented_by": implementations,
                    "status": "needs_review",
                    "reason": "The role is present in structure_model but was not confirmed by compact code_context.",
                }
            )

        return unsupported

    def _review_loops(self, loops: list[dict[str, Any]]) -> dict[str, Any]:
        loop_summaries = []
        complete_loops = 0
        best_confidence = 0.0

        for loop in loops:
            roles = set(loop.get("roles_present", []) or loop.get("rolesPresent", []) or [])
            missing = sorted(self.CORE_MAPEK_ROLES - roles)
            completeness = loop.get("loop_completeness") or loop.get("completeness")
            confidence = float(loop.get("confidence", 0.0) or 0.0)
            best_confidence = max(best_confidence, confidence)
            if completeness == "complete" and not missing:
                complete_loops += 1

            loop_summaries.append(
                {
                    "id": loop.get("id"),
                    "name": loop.get("name"),
                    "completeness": completeness,
                    "confidence": confidence,
                    "roles_present": sorted(roles),
                    "missing_core_roles": missing,
                }
            )

        return {
            "complete_loops": complete_loops,
            "best_confidence": best_confidence,
            "loops": loop_summaries,
        }

    def _build_assessment(
        self,
        applicability: dict[str, Any],
        role_confirmations: list[dict[str, Any]],
        unsupported_architecture_roles: list[dict[str, Any]],
        loop_review: dict[str, Any],
        code_context: dict[str, Any],
    ) -> dict[str, Any]:
        confirmed_roles = set()
        for confirmation in role_confirmations:
            confirmed_roles.update(confirmation.get("confirmed_roles", []) or [])

        core_confirmed = self.CORE_MAPEK_ROLES & confirmed_roles
        complete_loop = loop_review.get("complete_loops", 0) > 0
        score = float(applicability.get("score", 0.0) or 0.0)

        if not code_context.get("available"):
            status = "needs_code_context"
            confidence = 0.0
            is_autonomic = False
            reason = "No compact code_context was available for deterministic review."
        else:
            is_autonomic = len(core_confirmed) >= 5 and complete_loop
            penalty = min(0.20, 0.03 * len(unsupported_architecture_roles))
            confidence = max(0.0, min(0.95, max(score, 0.50 + 0.08 * len(core_confirmed)) - penalty))
            status = "supported_by_code_context" if is_autonomic else "needs_review"
            reason = (
                "Recovered MAPE-K architecture is supported by compact code evidence."
                if is_autonomic
                else "The compact code evidence does not confirm all core MAPE-K roles."
            )

        return {
            "is_autonomic_system_candidate": is_autonomic,
            "confidence": round(confidence, 2),
            "status": status,
            "reason": reason,
            "confirmed_core_roles": sorted(core_confirmed),
            "missing_core_roles": sorted(self.CORE_MAPEK_ROLES - core_confirmed),
            "applicability_decision": applicability.get("decision"),
            "applicability_status": applicability.get("status"),
            "applicability_score": applicability.get("score"),
            "complete_loop_confirmed": complete_loop,
        }

    def _confidence_for_confirmation(self, roles: list[str], review: dict[str, Any]) -> float:
        evidence_count = len(review.get("evidence", []) or [])
        method_count = len(review.get("representative_methods", []) or [])
        confidence = 0.70 + min(0.15, 0.03 * evidence_count) + min(0.10, 0.02 * method_count)
        if len(roles) >= 3:
            confidence += 0.03
        return round(min(confidence, 0.92), 2)

    def _simple_name(self, value: str | None) -> str:
        if not value:
            return ""
        return str(value).split(".")[-1]
