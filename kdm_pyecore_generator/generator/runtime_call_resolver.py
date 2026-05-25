class RuntimeCallResolver:
    """
    Maps runtime_calls relationships to semantic KDM action::Calls relations.

    Runtime relationships are facts collected from execution traces. They are
    represented using the native KDM Calls relation, not as TaggedValues.

    Rule:
    - relationship.type == "runtime_calls" -> action::Calls
    - if an equivalent Calls(source, target) already exists, do not duplicate it
    - runtime call ActionElements are contained in a BlockUnit body
    """

    def __init__(
        self,
        factory,
        qualified_name_index=None,
        id_index=None,
        inventory_builder=None,
        language="unknown",
    ):
        self.factory = factory
        self.qualified_name_index = qualified_name_index or {}
        self.id_index = id_index or {}
        self.inventory_builder = inventory_builder
        self.language = language
        self.created_runtime_calls = 0
        self.skipped_duplicates = 0
        self.unresolved_runtime_calls = 0
        self._runtime_action_counter = 0

    def add_runtime_call_relations(self, data: dict):
        for relationship in data.get("relationships", []):
            if relationship.get("type") != "runtime_calls":
                continue

            self._add_runtime_call_relation(relationship)

    def _add_runtime_call_relation(self, relationship: dict):
        source_name = relationship.get("source")
        target_name = relationship.get("target")

        if not source_name or not target_name:
            self.unresolved_runtime_calls += 1
            return

        source = self._resolve_runtime_endpoint(source_name)
        target = self._resolve_runtime_endpoint(target_name)

        if source is None or target is None:
            self.unresolved_runtime_calls += 1
            return

        if self._calls_relation_exists(source, target):
            self.skipped_duplicates += 1
            return

        container = self._get_or_create_runtime_action_container(source)
        if container is None:
            self.unresolved_runtime_calls += 1
            return

        action = self.factory.create_action_element(
            name=self._runtime_action_name(source_name, target_name, container),
            kind="runtime_call",
        )

        self._add_runtime_call_source_region(action, relationship)
        self._add_runtime_call_metadata(action, relationship)

        container.codeElement.append(action)

        calls_relation = self.factory.create_calls_relation(target)
        action.actionRelation.append(calls_relation)

        self.created_runtime_calls += 1

    def _resolve_runtime_endpoint(self, runtime_name: str):
        """
        Resolves a runtime qualified name to a KDM code item.

        The runtime tracer may use names produced by dynamic loading, for
        example hierarchical_cruise_control_runtime.foo, while the static
        extractor may have used a different module name. Therefore resolution
        tries exact matches first and then conservative suffix matches.
        """

        if runtime_name in self.qualified_name_index:
            return self.qualified_name_index[runtime_name]

        normalized = self._normalize_name(runtime_name)

        for qualified_name, element in self.qualified_name_index.items():
            if self._normalize_name(qualified_name) == normalized:
                return element

        suffix = "." + normalized

        matches = [
            element
            for qualified_name, element in self.qualified_name_index.items()
            if self._normalize_name(qualified_name).endswith(suffix)
        ]

        if len(matches) == 1:
            return matches[0]

        # Last-resort callable suffix matching:
        # fixtures.VirtualCarSpeed.gas should match any static qualified name
        # ending in .VirtualCarSpeed.gas.
        parts = normalized.split(".")
        if len(parts) >= 2:
            short_suffix = "." + ".".join(parts[-2:])
            matches = [
                element
                for qualified_name, element in self.qualified_name_index.items()
                if self._normalize_name(qualified_name).endswith(short_suffix)
            ]

            if len(matches) == 1:
                return matches[0]

        return None

    def _normalize_name(self, name: str) -> str:
        return (
            str(name)
            .replace("-", "_")
            .replace("/", ".")
            .replace("\\", ".")
        )

    def _get_or_create_runtime_action_container(self, source):
        """
        Returns a BlockUnit body that can contain runtime ActionElements.

        KDM validators should not see ActionElement instances directly under
        MethodUnit or CallableUnit. Therefore, runtime call actions are appended
        to an existing BlockUnit body when possible. If no BlockUnit exists,
        one is created.
        """

        if not self.factory.has_feature(source, "codeElement"):
            return None

        existing_block = self._find_direct_body_block(source)
        if existing_block is not None:
            return existing_block

        block = self.factory.create_block_unit(name="body", kind="body")
        source.codeElement.append(block)
        return block

    def _find_direct_body_block(self, source):
        if not self.factory.has_feature(source, "codeElement"):
            return None

        for element in source.codeElement:
            if element.eClass.name == "BlockUnit":
                return element

        return None

    def _calls_relation_exists(self, source, target) -> bool:
        """
        Checks whether source already contains an ActionElement with a Calls
        relation to target. The search is recursive because actions can be
        contained inside BlockUnit bodies.
        """

        for element in self._walk_code_elements(source):
            if not self.factory.has_feature(element, "actionRelation"):
                continue

            for relation in element.actionRelation:
                if relation.eClass.name != "Calls":
                    continue

                if getattr(relation, "to", None) is target:
                    return True

        return False

    def _walk_code_elements(self, element):
        if not self.factory.has_feature(element, "codeElement"):
            return

        for child in element.codeElement:
            yield child
            yield from self._walk_code_elements(child)

    def _runtime_action_name(self, source_name: str, target_name: str, container) -> str:
        """
        Creates a unique runtime action name within the destination BlockUnit.

        The KDM validator flags duplicate ActionElement children in the same
        BlockUnit using their name/kind/source-region signature. Runtime traces
        often contain several calls to methods named __init__, so a simple
        runtime_call:__init__ name is not unique enough.
        """

        target_simple_name = str(target_name).split(".")[-1]
        target_owner = self._owner_fragment(target_name)
        source_owner = self._owner_fragment(source_name)

        base_name = self._safe_action_name(
            f"runtime_call:{source_owner}->{target_owner}.{target_simple_name}"
        )

        if not self._action_name_exists(container, base_name):
            return base_name

        while True:
            self._runtime_action_counter += 1
            candidate = f"{base_name}#{self._runtime_action_counter}"

            if not self._action_name_exists(container, candidate):
                return candidate

    def _owner_fragment(self, qualified_name: str) -> str:
        parts = str(qualified_name).split(".")

        if len(parts) >= 2:
            return parts[-2]

        return parts[0] if parts else "unknown"

    def _safe_action_name(self, name: str) -> str:
        return (
            name.replace(" ", "_")
            .replace("/", ".")
            .replace("\\", ".")
        )

    def _action_name_exists(self, container, name: str) -> bool:
        if not self.factory.has_feature(container, "codeElement"):
            return False

        for element in container.codeElement:
            if element.eClass.name != "ActionElement":
                continue

            if getattr(element, "name", None) == name:
                return True

        return False

    def _add_runtime_call_source_region(self, action, relationship: dict):
        file_path = relationship.get("file")
        line = relationship.get("line")

        if not file_path and line is None:
            return

        source_file = None
        if self.inventory_builder is not None and file_path:
            source_file = self.inventory_builder.get_source_file_by_path(file_path)

        self.factory.add_source_region(
            action,
            path=file_path,
            language=self.language,
            start_line=line,
            end_line=line,
            file_item=source_file,
        )

    def _add_runtime_call_metadata(self, action, relationship: dict):
        """
        Adds only traceability attributes. The semantic relation itself is
        represented by action::Calls.
        """

        metadata = {
            "runtime_relationship_id": relationship.get("id"),
            "runtime_evidence": relationship.get("evidence"),
            "runtime_scenario": relationship.get("scenario"),
            "runtime_source_level": relationship.get("source_level"),
        }

        self.factory.add_attributes_from_dict(action, metadata)
