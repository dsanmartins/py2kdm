from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


class AgentContextBuilder:
    """
    Builds a compact context used by architecture agents.

    The context is intentionally derived from the architecture JSON instead of
    the KDM XMI. The architecture JSON remains the source of truth before KDM
    generation.
    """

    def build(
        self,
        model: dict[str, Any],
        code_model: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        structure_model = model.get("structure_model", {})
        components = structure_model.get("components", [])
        relationships = structure_model.get("structure_relationships", [])
        containment = structure_model.get("containment_relationships", [])
        loops = structure_model.get("control_loops", [])
        subsystems = structure_model.get("subsystems", [])

        materialized_components = [
            component for component in components
            if component.get("materialize", True) is not False
        ]

        by_id = {
            component.get("id"): component
            for component in components
            if component.get("id")
        }

        role_index = defaultdict(list)

        for component in materialized_components:
            role_index[component.get("role")].append(component)

        implementation_index = defaultdict(list)

        for component in materialized_components:
            for implementation in component.get("implemented_by", []) or []:
                implementation_index[implementation].append(component)

        relationship_index = defaultdict(list)

        for relationship in relationships + containment:
            source = relationship.get("source")
            target = relationship.get("target")
            relationship_index[source].append(relationship)
            relationship_index[target].append(relationship)

        loop_summaries = []

        for loop in loops:
            component_ids = loop.get("components", []) or []
            roles = [
                by_id[component_id].get("role")
                for component_id in component_ids
                if component_id in by_id
            ]

            loop_summaries.append(
                {
                    "id": loop.get("id"),
                    "name": loop.get("name"),
                    "roles": sorted(set(roles)),
                    "role_counts": dict(Counter(roles)),
                    "missing_core_roles": sorted(
                        {"Monitor", "Analyzer", "Planner", "Executor"}
                        - set(roles)
                    ),
                    "components": component_ids,
                }
            )

        runtime_summary = self._build_runtime_summary(
            model=model,
            implementation_index=implementation_index,
        )

        return {
            "projectName": model.get("projectName"),
            "language": model.get("language"),
            "components": components,
            "relationships": relationships,
            "containment_relationships": containment,
            "control_loops": loops,
            "subsystems": subsystems,
            "component_by_id": by_id,
            "components_by_role": dict(role_index),
            "components_by_implementation": dict(implementation_index),
            "relationships_by_endpoint": dict(relationship_index),
            "loop_summaries": loop_summaries,
            "runtime_summary": runtime_summary,
            "code_context": self._build_code_context(
                architecture_model=model,
                code_model=code_model,
                implementation_index=implementation_index,
            ),
            "architecture_consistency": structure_model.get(
                "architecture_consistency", {}
            ),
            "architecture_review": model.get("architecture_review", {}),
        }


    def _build_code_context(
        self,
        architecture_model: dict[str, Any],
        code_model: dict[str, Any] | None,
        implementation_index: dict,
    ) -> dict[str, Any]:
        """
        Builds a compact, review-oriented code context from the intermediate
        extractor JSON.

        The LLM must not receive the whole Java/Python model because it can be
        very large.  This method selects only architecture-relevant classes and
        summarizes imports, fields, methods, calls and role evidence.
        """
        if not code_model:
            return {
                "available": False,
                "reason": "No intermediate code model was provided.",
                "classes": [],
            }

        elements = [
            element for element in code_model.get("elements", [])
            if isinstance(element, dict) and element.get("kind") in {"class", "module"}
        ]

        file_by_path = {
            file_model.get("path"): file_model
            for file_model in code_model.get("files", [])
            if isinstance(file_model, dict) and file_model.get("path")
        }

        selected = self._select_code_context_classes(
            architecture_model=architecture_model,
            elements=elements,
            implementation_index=implementation_index,
        )

        classes = []

        for element in selected[:12]:
            file_model = file_by_path.get(element.get("filePath"), {})
            summary = self._summarize_code_class(
                element=element,
                file_model=file_model,
                architecture_model=architecture_model,
                implementation_index=implementation_index,
            )
            if (
                not summary.get("candidate_roles")
                and not summary.get("related_architecture_components")
            ):
                continue
            classes.append(summary)

        return {
            "available": True,
            "source": "intermediate_json",
            "selection_strategy": (
                "architecture implementations, MAPE-K role evidence, and "
                "technology APIs; generated/test/UI-only classes are deprioritized"
            ),
            "classes_count": len(classes),
            "classes": classes,
        }

    def _select_code_context_classes(
        self,
        architecture_model: dict[str, Any],
        elements: list[dict[str, Any]],
        implementation_index: dict,
    ) -> list[dict[str, Any]]:
        implementation_names = {
            self._simple_name(name)
            for name in implementation_index.keys()
            if name
        }

        scored = []

        for element in elements:
            name = element.get("name") or ""
            qualified_name = element.get("qualifiedName") or name
            file_path = element.get("filePath") or ""

            if self._is_generated_or_test_path(file_path):
                continue

            package_name = str(element.get("packageName", "")).lower()
            if package_name.endswith(".activity"):
                simple_name = self._simple_name(name)
                qualified_simple_name = self._simple_name(qualified_name)
                if (
                    simple_name not in implementation_names
                    and qualified_simple_name not in implementation_names
                ):
                    continue

            score = 0
            simple = self._simple_name(name)
            qualified_simple = self._simple_name(qualified_name)

            if simple in implementation_names or qualified_simple in implementation_names:
                score += 100

            if self._looks_like_architectural_class(name, qualified_name):
                score += 40

            tokens = self._element_tokens(element)
            score += self._technology_score(tokens)

            if str(element.get("packageName", "")).endswith(".context"):
                score += 20
            if str(element.get("packageName", "")).endswith(".database"):
                score += 20

            package_name = str(element.get("packageName", "")).lower()
            if name.endswith("Activity") or package_name.endswith(".activity"):
                score -= 70

            if score <= 0:
                continue

            scored.append((score, qualified_name, element))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [element for _, _, element in scored]

    def _summarize_code_class(
        self,
        element: dict[str, Any],
        file_model: dict[str, Any],
        architecture_model: dict[str, Any],
        implementation_index: dict,
    ) -> dict[str, Any]:
        name = element.get("name")
        qualified_name = element.get("qualifiedName") or name
        fields = element.get("fields", []) or []
        methods = element.get("methods", []) or []
        tokens = self._element_tokens(element)
        candidate_roles, evidence = self._infer_code_context_roles(
            element=element,
            tokens=tokens,
        )

        related_components = []
        for key in (name, qualified_name, self._simple_name(qualified_name)):
            for component in implementation_index.get(key, []):
                compact = {
                    "id": component.get("id"),
                    "name": component.get("name"),
                    "role": component.get("role"),
                    "confidence": component.get("confidence"),
                }
                if compact not in related_components:
                    related_components.append(compact)

        return {
            "name": name,
            "qualified_name": qualified_name,
            "package": element.get("packageName"),
            "file": self._compact_path(element.get("filePath")),
            "line_start": element.get("lineStart"),
            "line_end": element.get("lineEnd"),
            "extends": element.get("extendsTypes", [])[:5],
            "implements": element.get("implementsTypes", [])[:5],
            "imports": self._select_relevant_imports(file_model.get("imports", [])),
            "fields": [
                {
                    "name": field.get("name"),
                    "type": field.get("type") or field.get("resolvedType"),
                }
                for field in fields[:20]
            ],
            "methods": [
                self._summarize_method(method)
                for method in self._select_relevant_methods(methods)[:10]
            ],
            "candidate_roles": candidate_roles,
            "role_evidence": evidence,
            "related_architecture_components": related_components,
        }

    def _summarize_method(self, method: dict[str, Any]) -> dict[str, Any]:
        calls = self._collect_method_calls(method)
        local_variables = method.get("localVariables", []) or []
        return {
            "name": method.get("name"),
            "signature": method.get("signature"),
            "return_type": method.get("returnType") or method.get("resolvedReturnType"),
            "line_start": method.get("lineStart"),
            "line_end": method.get("lineEnd"),
            "parameters": [
                {
                    "name": parameter.get("name"),
                    "type": parameter.get("type") or parameter.get("resolvedType"),
                }
                for parameter in (method.get("parameters", []) or [])[:8]
            ],
            "calls": calls[:25],
            "local_variables": [
                {
                    "name": variable.get("name"),
                    "type": variable.get("type") or variable.get("assignedType"),
                }
                for variable in local_variables[:10]
            ],
        }

    def _select_relevant_methods(self, methods: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def score(method: dict[str, Any]) -> int:
            name = str(method.get("name") or "").lower()
            calls = " ".join(self._collect_method_calls(method)).lower()
            text = f"{name} {calls}"

            score_value = 0
            for token in (
                "check",
                "evaluate",
                "rule",
                "filter",
                "profile",
                "context",
                "receive",
                "broadcast",
                "intent",
                "location",
                "bluetooth",
                "audio",
                "settings",
                "insert",
                "fetch",
                "update",
                "delete",
                "open",
            ):
                if token in text:
                    score_value += 5

            if name in {"onreceive", "onhandleintent", "checkrules"}:
                score_value += 30

            return score_value

        return sorted(methods, key=lambda method: (-score(method), method.get("name") or ""))

    def _collect_method_calls(self, method: dict[str, Any]) -> list[str]:
        calls = []

        def add_call(call: dict[str, Any]):
            if not isinstance(call, dict):
                return
            scope = call.get("scope")
            name = call.get("methodName") or call.get("name")
            resolved = call.get("resolvedTarget")
            if scope and name:
                calls.append(f"{scope}.{name}")
            elif resolved:
                calls.append(str(resolved))
            elif name:
                calls.append(str(name))

        for call in method.get("calls", []) or []:
            add_call(call)

        def visit_statement(statement: dict[str, Any]):
            if not isinstance(statement, dict):
                return
            for key in ("valueCall",):
                value = statement.get(key)
                if isinstance(value, dict):
                    add_call(value)
            for key in ("valueCalls", "conditionCalls", "exceptionCalls"):
                for call in statement.get(key, []) or []:
                    add_call(call)
            for key in ("body", "elseBody", "finallyBody"):
                for child in statement.get(key, []) or []:
                    visit_statement(child)
            for catch_clause in statement.get("catchClauses", []) or []:
                visit_statement(catch_clause)

        for statement in method.get("body", []) or []:
            visit_statement(statement)

        seen = set()
        unique = []
        for call in calls:
            if call in seen:
                continue
            seen.add(call)
            unique.append(call)
        return unique

    def _infer_code_context_roles(
        self,
        element: dict[str, Any],
        tokens: set[str],
    ) -> tuple[list[str], list[str]]:
        roles = []
        evidence = []
        name = str(element.get("name") or "").lower()

        def add(role: str, reason: str):
            if role not in roles:
                roles.append(role)
            if reason not in evidence:
                evidence.append(reason)

        if name in {"mydbadapter", "mydbhelper"}:
            add("Knowledge", "database component evidence: DbAdapter/DbHelper stores rules, filters, profiles or context constants")
            return roles, evidence

        if name == "contextmanager":
            add("Monitor", "canonical component evidence: ContextManager observes context through Android sensors/events")
            if {"sendbroadcast", "broadcastreceiver", "onreceive", "intentfilter"} & tokens:
                add("LoopManager", "event/control-flow evidence: BroadcastReceiver, onReceive, sendBroadcast or IntentFilter")
            return roles, evidence

        if name == "adaptationmanager":
            add("Analyzer", "canonical component evidence: AdaptationManager evaluates context/rules")
            add("Planner", "canonical component evidence: AdaptationManager selects an adaptation rule or action")
            add("Executor", "canonical component evidence: AdaptationManager applies changes through Android APIs")
            if {"sendbroadcast", "broadcastreceiver", "onreceive", "intentfilter"} & tokens:
                add("LoopManager", "event/control-flow evidence: BroadcastReceiver, onReceive, sendBroadcast or IntentFilter")
            return roles, evidence

        if {
            "sqlitedatabase",
            "sqliteopenhelper",
            "contentvalues",
            "cursor",
        } & tokens:
            add("Knowledge", "database/API evidence: SQLiteDatabase, SQLiteOpenHelper, Cursor or ContentValues")

        if name == "contextmanager" or {
            "locationmanager",
            "locationlistener",
            "bluetoothadapter",
            "bluetoothdevice",
            "intentservice",
        } & tokens:
            add("Monitor", "context sensing evidence: LocationManager/LocationListener/Bluetooth/IntentService")

        if {
            "getbooleanextra",
            "getstringextra",
            "getdoubleextra",
            "checkrules",
            "contextoperator",
        } & tokens:
            add("Analyzer", "rule/context evaluation evidence: checkRules, ContextOperator or Intent extras")

        if {
            "priority",
            "candidate",
            "satisfiedrulelist",
            "random",
            "choice",
        } & tokens:
            add("Planner", "selection evidence: priority, candidate, satisfiedRuleList, Random or choice")

        if {
            "audiomanager",
            "settings",
            "settings.system",
            "setstreamvolume",
            "setringermode",
            "setvibratesetting",
            "putint",
            "action_airplane_mode_changed",
        } & tokens:
            add("Executor", "effecting evidence: AudioManager, Settings.System or system-setting writes")

        if {"sendbroadcast", "broadcastreceiver", "onreceive", "intentfilter"} & tokens:
            add("LoopManager", "event/control-flow evidence: BroadcastReceiver, onReceive, sendBroadcast or IntentFilter")

        return roles, evidence

    def _element_tokens(self, element: dict[str, Any]) -> set[str]:
        tokens = set()

        def add(value: Any):
            if value is None:
                return
            text = str(value)
            tokens.add(text.lower())
            tokens.add(text.replace(".", "_").lower())
            tokens.add(self._simple_name(text).lower())

        add(element.get("name"))
        add(element.get("qualifiedName"))
        add(element.get("packageName"))

        for field in element.get("fields", []) or []:
            add(field.get("name"))
            add(field.get("type"))
            add(field.get("resolvedType"))

        for method in element.get("methods", []) or []:
            add(method.get("name"))
            add(method.get("signature"))
            add(method.get("returnType"))
            for call in self._collect_method_calls(method):
                add(call)
            for parameter in method.get("parameters", []) or []:
                add(parameter.get("name"))
                add(parameter.get("type"))
            for variable in method.get("localVariables", []) or []:
                add(variable.get("name"))
                add(variable.get("type"))
                add(variable.get("assignedType"))

        return tokens

    def _technology_score(self, tokens: set[str]) -> int:
        score = 0
        for token in (
            "locationmanager",
            "locationlistener",
            "bluetoothadapter",
            "bluetoothdevice",
            "intentservice",
            "broadcastreceiver",
            "sendbroadcast",
            "onreceive",
            "audiomanager",
            "settings",
            "settings.system",
            "sqlitedatabase",
            "sqliteopenhelper",
            "contentvalues",
            "cursor",
            "checkrules",
            "priority",
            "random",
        ):
            if token in tokens:
                score += 10
        return score

    def _looks_like_architectural_class(self, name: str, qualified_name: str) -> bool:
        lowered = f"{name} {qualified_name}".lower()
        return any(
            token in lowered
            for token in (
                "manager",
                "adapter",
                "helper",
                "repository",
                "monitor",
                "analyzer",
                "planner",
                "executor",
                "knowledge",
                "sensor",
                "effector",
            )
        )

    def _select_relevant_imports(self, imports: list[str]) -> list[str]:
        relevant = []
        for item in imports or []:
            lowered = str(item).lower()
            if any(
                token in lowered
                for token in (
                    "android.bluetooth",
                    "android.location",
                    "android.content",
                    "android.database",
                    "android.media",
                    "android.provider",
                    "intentservice",
                    "sqlite",
                    "mydbadapter",
                    "contextmanager",
                    "adaptationmanager",
                )
            ):
                relevant.append(item)
        return relevant[:20]

    def _is_generated_or_test_path(self, path: str) -> bool:
        lowered = str(path or "").lower()
        return any(
            token in lowered
            for token in (
                "/build/generated/",
                "/androidtest/",
                "/test/",
                "/r.java",
                "/buildconfig.java",
            )
        )

    def _simple_name(self, name: str | None) -> str:
        if not name:
            return ""
        text = str(name).replace("\\", ".").replace("/", ".")
        return text.split(".")[-1]

    def _compact_path(self, path: str | None) -> str | None:
        if not path:
            return None
        text = str(path)
        marker = "/app/src/"
        if marker in text:
            return "app/src/" + text.split(marker, 1)[1]
        return text.split("/")[-1]

    def _build_runtime_summary(
        self,
        model: dict[str, Any],
        implementation_index: dict,
    ) -> dict[str, Any]:
        runtime_calls = [
            relationship
            for relationship in model.get("relationships", [])
            if relationship.get("type") == "runtime_calls"
        ]

        source_counter = Counter()
        target_counter = Counter()
        scenario_counter = Counter()
        component_pair_counter = Counter()

        unresolved_to_components = 0
        resolved_component_pairs = []

        for relationship in runtime_calls:
            source = relationship.get("source")
            target = relationship.get("target")
            scenario = relationship.get("scenario") or "unknown_scenario"

            if source:
                source_counter[source] += 1

            if target:
                target_counter[target] += 1

            scenario_counter[scenario] += 1

            source_components = self._find_components_for_runtime_name(
                source,
                implementation_index,
            )
            target_components = self._find_components_for_runtime_name(
                target,
                implementation_index,
            )

            if not source_components or not target_components:
                unresolved_to_components += 1
                continue

            for source_component in source_components:
                for target_component in target_components:
                    key = (
                        source_component.get("id"),
                        target_component.get("id"),
                    )
                    component_pair_counter[key] += 1

        component_by_pair_key = {}

        for relationship in runtime_calls:
            source = relationship.get("source")
            target = relationship.get("target")

            source_components = self._find_components_for_runtime_name(
                source,
                implementation_index,
            )
            target_components = self._find_components_for_runtime_name(
                target,
                implementation_index,
            )

            for source_component in source_components:
                for target_component in target_components:
                    key = (
                        source_component.get("id"),
                        target_component.get("id"),
                    )
                    component_by_pair_key[key] = {
                        "source_component": source_component.get("id"),
                        "source_name": source_component.get("name"),
                        "source_role": source_component.get("role"),
                        "target_component": target_component.get("id"),
                        "target_name": target_component.get("name"),
                        "target_role": target_component.get("role"),
                    }

        for key, count in component_pair_counter.most_common(25):
            item = dict(component_by_pair_key.get(key, {}))
            item["runtime_call_count"] = count
            resolved_component_pairs.append(item)

        runtime_enrichment = model.get("runtime_enrichment", {})
        enrichment_summary = runtime_enrichment.get("summary", {})

        return {
            "available": bool(runtime_calls),
            "total_runtime_calls": len(runtime_calls),
            "runtime_calls_by_scenario": dict(scenario_counter),
            "top_sources": [
                {"source": source, "count": count}
                for source, count in source_counter.most_common(20)
            ],
            "top_targets": [
                {"target": target, "count": count}
                for target, count in target_counter.most_common(20)
            ],
            "top_component_pairs": resolved_component_pairs,
            "runtime_calls_unmapped_to_components": unresolved_to_components,
            "runtime_enrichment_summary": enrichment_summary,
            "observed_argument_types": enrichment_summary.get(
                "observed_argument_types"
            ),
            "observed_return_types": enrichment_summary.get(
                "observed_return_types"
            ),
        }

    def _find_components_for_runtime_name(
        self,
        runtime_name: str | None,
        implementation_index: dict,
    ) -> list[dict[str, Any]]:
        if not runtime_name:
            return []

        if runtime_name in implementation_index:
            return implementation_index[runtime_name]

        normalized_runtime_name = self._normalize(runtime_name)
        matches = []

        for implementation, components in implementation_index.items():
            normalized_implementation = self._normalize(implementation)

            if normalized_implementation == normalized_runtime_name:
                matches.extend(components)
                continue

            if normalized_runtime_name.endswith("." + normalized_implementation):
                matches.extend(components)
                continue

            if normalized_implementation.endswith("." + normalized_runtime_name):
                matches.extend(components)
                continue

            runtime_parts = normalized_runtime_name.split(".")
            implementation_parts = normalized_implementation.split(".")

            if len(runtime_parts) >= 2 and len(implementation_parts) >= 2:
                if runtime_parts[-2:] == implementation_parts[-2:]:
                    matches.extend(components)

        # Remove duplicate components by id while preserving order.
        seen = set()
        unique = []

        for component in matches:
            component_id = component.get("id")

            if component_id in seen:
                continue

            seen.add(component_id)
            unique.append(component)

        return unique

    def _normalize(self, name: str) -> str:
        return (
            str(name)
            .replace("-", "_")
            .replace("/", ".")
            .replace("\\", ".")
        )
