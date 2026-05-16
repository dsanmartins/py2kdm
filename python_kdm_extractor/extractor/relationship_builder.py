import hashlib

class RelationshipBuilder:
    """
    Builds global relationships from the intermediate project model.

    The generated relationships are useful for later mapping the model
    to KDM/EMF because KDM represents not only code elements but also
    semantic links among them.
    """

    def __init__(self):
        self.relationships = []
        self.relationship_keys = set()

    def build_relationships(self, project_model: dict):
        """
        Builds relationships for the full project model.
        """

        self.relationships = []
        self.relationship_keys = set()

        project_id = f"project:{project_model.get('projectName')}"

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue

            self._new_relationship(
                "contains",
                project_id,
                file_model.get("id"),
                {
                    "source_kind": "project",
                    "target_kind": "module"
                }
            )

            self._build_module_relationships(file_model)

        project_model["relationships"] = self.relationships

        return project_model

    def _new_relationship(
        self,
        relationship_type: str,
        source: str,
        target: str,
        metadata: dict = None
    ):
        """
        Creates a relationship with a stable identifier and avoids duplicates.

        The identity of a relationship is based on:
        - relationship type
        - source
        - target
        - relevant metadata such as line and call name
        """

        if not source or not target:
            return

        metadata = metadata or {}

        relationship_key = self._build_relationship_key(
            relationship_type,
            source,
            target,
            metadata
        )

        if relationship_key in self.relationship_keys:
            return

        self.relationship_keys.add(relationship_key)

        relationship = {
            "id": self._build_relationship_id(relationship_key),
            "type": relationship_type,
            "source": source,
            "target": target
        }

        relationship.update(metadata)

        self.relationships.append(relationship)

    def _build_relationship_key(
        self,
        relationship_type: str,
        source: str,
        target: str,
        metadata: dict
    ):
        """
        Builds a canonical key for a relationship.

        This key is used both for deduplication and for stable ID generation.
        """

        relevant_parts = [
            relationship_type,
            source,
            target,
            str(metadata.get("line", "")),
            str(metadata.get("call_name", "")),
            str(metadata.get("import_type", "")),
            str(metadata.get("attribute_name", "")),
            str(metadata.get("base", ""))
        ]

        return "|".join(relevant_parts)

    def _build_relationship_id(self, relationship_key: str):
        """
        Builds a stable ID from the relationship key using a short hash.
        """

        digest = hashlib.sha1(
            relationship_key.encode("utf-8")
        ).hexdigest()[:12]

        return f"rel:{digest}"

    def _build_module_relationships(self, file_model: dict):
        """
        Builds relationships involving a module.
        """

        module_id = file_model.get("id")

        self._build_import_relationships(file_model, module_id)

        for class_model in file_model.get("classes", []):
            self._build_class_relationships(module_id, class_model)

        for function_model in file_model.get("functions", []):
            self._new_relationship(
                "contains",
                module_id,
                function_model.get("id"),
                {
                    "source_kind": "module",
                    "target_kind": "function"
                }
            )

            self._build_callable_relationships(function_model)

    def _build_class_relationships(self, module_id: str, class_model: dict):
        """
        Builds relationships for a class.
        """

        class_id = class_model.get("id")

        self._new_relationship(
            "contains",
            module_id,
            class_id,
            {
                "source_kind": "module",
                "target_kind": "class"
            }
        )

        self._build_inheritance_relationships(class_model)

        self._build_instance_attribute_relationships(class_model)

        for method_model in class_model.get("methods", []):
            self._new_relationship(
                "contains",
                class_id,
                method_model.get("id"),
                {
                    "source_kind": "class",
                    "target_kind": "method"
                }
            )

            self._build_callable_relationships(method_model)

    def _build_import_relationships(self, file_model: dict, module_id: str):
        """
        Builds import relationships from a module to imported internal or external elements.
        """

        for import_model in file_model.get("imports", []):
            import_type = import_model.get("type")
            classification = import_model.get("classification")
            target_id = import_model.get("target_id")

            if classification == "internal" and target_id:
                self._new_relationship(
                    "imports",
                    module_id,
                    target_id,
                    {
                        "line": import_model.get("line"),
                        "classification": "internal",
                        "import_type": import_type,
                        "module": import_model.get("module"),
                        "name": import_model.get("name"),
                        "alias": import_model.get("alias"),
                        "target_type": import_model.get("target_type"),
                        "target_qualified_name": import_model.get(
                            "target_qualified_name"
                        )
                    }
                )
                continue

            if import_type == "import":
                target = import_model.get("module")

                self._new_relationship(
                    "imports",
                    module_id,
                    f"external:{target}",
                    {
                        "line": import_model.get("line"),
                        "classification": "external",
                        "import_type": "import",
                        "module": target,
                        "alias": import_model.get("alias")
                    }
                )

            elif import_type == "from_import":
                module = import_model.get("module")
                name = import_model.get("name")

                if module and name:
                    target = f"external:{module}.{name}"
                elif module:
                    target = f"external:{module}"
                else:
                    target = f"external:{name}"

                self._new_relationship(
                    "imports",
                    module_id,
                    target,
                    {
                        "line": import_model.get("line"),
                        "classification": "external",
                        "import_type": "from_import",
                        "module": module,
                        "name": name,
                        "alias": import_model.get("alias")
                    }
                )

    def _build_inheritance_relationships(self, class_model: dict):
        """
        Builds inheritance relationships from classes to their bases.
        """

        class_id = class_model.get("id")

        for base in class_model.get("bases", []):
            if not base:
                continue

            self._new_relationship(
                "inherits",
                class_id,
                f"class_or_external:{base}",
                {
                    "base": base
                }
            )

    def _build_instance_attribute_relationships(self, class_model: dict):
        """
        Builds relationships derived from instance attributes.

        Example:
        self.repository = UserRepository()

        Produces:
        UserService --uses--> UserRepository
        UserService --instantiates--> UserRepository
        """

        class_id = class_model.get("id")

        for attribute in class_model.get("instance_attributes", []):
            resolved_type_id = attribute.get("resolved_type_id")
            assigned_type = attribute.get("assigned_type")

            if resolved_type_id:
                target = resolved_type_id
            elif assigned_type:
                target = f"class_or_external:{assigned_type}"
            else:
                continue

            self._new_relationship(
                "uses",
                class_id,
                target,
                {
                    "via": attribute.get("full_name"),
                    "line": attribute.get("line"),
                    "attribute_name": attribute.get("name")
                }
            )

            if assigned_type:
                self._new_relationship(
                    "instantiates",
                    class_id,
                    target,
                    {
                        "via": attribute.get("full_name"),
                        "line": attribute.get("line"),
                        "attribute_name": attribute.get("name"),
                        "assigned_type": assigned_type
                    }
                )

    def _build_callable_relationships(self, callable_model: dict):
        """
        Builds call, instantiation, and body containment relationships
        from functions or methods.
        """

        source_id = callable_model.get("id")

        for call_model in callable_model.get("calls", []):
            classification = call_model.get("classification")
            kind = call_model.get("kind")
            target_id = call_model.get("target_id")

            if kind == "constructor_call":
                self._build_constructor_relationship(source_id, call_model)
                continue

            if classification in {"internal","builtin","builtin_type_method","external_type_method"} and target_id:
                self._new_relationship(
                    "calls",
                    source_id,
                    target_id,
                    {
                        "line": call_model.get("line"),
                        "call_name": call_model.get("name"),
                        "classification": classification,
                        "call_kind": kind
                    }
                )

            elif classification == "external":
                self._new_relationship(
                    "calls",
                    source_id,
                    f"external:{call_model.get('name')}",
                    {
                        "line": call_model.get("line"),
                        "call_name": call_model.get("name"),
                        "classification": "external",
                        "call_kind": kind,
                        "import_source": call_model.get("import_source")
                    }
                )

            elif classification in {
                "internal_ambiguous",
                "constructor_ambiguous",
                "internal_candidate"
            }:
                self._new_relationship(
                    "calls_unresolved",
                    source_id,
                    f"unresolved:{call_model.get('name')}",
                    {
                        "line": call_model.get("line"),
                        "call_name": call_model.get("name"),
                        "classification": classification,
                        "call_kind": kind,
                        "candidate_targets": call_model.get("candidate_targets", [])
                    }
                )

            else:
                self._new_relationship(
                    "calls_unresolved",
                    source_id,
                    f"unresolved:{call_model.get('name')}",
                    {
                        "line": call_model.get("line"),
                        "call_name": call_model.get("name"),
                        "classification": classification or "unresolved",
                        "call_kind": kind
                    }
                )

        self._build_body_relationships(
            callable_model.get("body", []),
            parent_id=source_id,
            parent_kind=callable_model.get("type")
        )


    def _build_body_relationships(
        self,
        body_nodes: list,
        parent_id: str,
        parent_kind: str,
        branch: str = "body"
    ):
        """
        Builds containment relationships for nested body elements.
        """

        for body_node in body_nodes:
            body_node_id = body_node.get("id")

            if not body_node_id:
                continue

            self._new_relationship(
                "contains",
                parent_id,
                body_node_id,
                {
                    "source_kind": parent_kind,
                    "target_kind": body_node.get("type"),
                    "branch": branch,
                    "line": body_node.get("line_start")
                }
            )

            self._build_body_relationships(
                body_node.get("body", []),
                parent_id=body_node_id,
                parent_kind=body_node.get("type"),
                branch="body"
            )

            self._build_body_relationships(
                body_node.get("orelse", []),
                parent_id=body_node_id,
                parent_kind=body_node.get("type"),
                branch="orelse"
            )

            self._build_body_relationships(
                body_node.get("finalbody", []),
                parent_id=body_node_id,
                parent_kind=body_node.get("type"),
                branch="finalbody"
            )

            for handler in body_node.get("handlers", []):
                handler_id = handler.get("id")

                if not handler_id:
                    continue

                self._new_relationship(
                    "contains",
                    body_node_id,
                    handler_id,
                    {
                        "source_kind": body_node.get("type"),
                        "target_kind": "exception_handler",
                        "branch": "handlers",
                        "line": handler.get("line_start")
                    }
                )

                self._build_body_relationships(
                    handler.get("body", []),
                    parent_id=handler_id,
                    parent_kind="exception_handler",
                    branch="body"
                )


    def _build_constructor_relationship(self, source_id: str, call_model: dict):
        """
        Builds relationships for constructor calls.

        Example:
        UserRepository()

        Produces:
        method --instantiates--> class
        method --calls--> class
        """

        target_id = call_model.get("target_id")
        classification = call_model.get("classification")

        if target_id and classification == "constructor":
            self._new_relationship(
                "instantiates",
                source_id,
                target_id,
                {
                    "line": call_model.get("line"),
                    "call_name": call_model.get("name"),
                    "class_name": call_model.get("class_name"),
                    "resolved_from_cls": call_model.get("resolved_from_cls", False),
                }
            )

            self._new_relationship(
                "calls",
                source_id,
                target_id,
                {
                    "line": call_model.get("line"),
                    "call_name": call_model.get("name"),
                    "classification": classification,
                    "call_kind": "constructor_call"
                }
            )

        elif classification == "constructor_ambiguous":
            self._new_relationship(
                "instantiates_unresolved",
                source_id,
                f"unresolved:{call_model.get('name')}",
                {
                    "line": call_model.get("line"),
                    "call_name": call_model.get("name"),
                    "candidate_targets": call_model.get("candidate_targets", [])
                }
            )

        else:
            self._new_relationship(
                "instantiates_unresolved",
                source_id,
                f"unresolved:{call_model.get('name')}",
                {
                    "line": call_model.get("line"),
                    "call_name": call_model.get("name"),
                    "classification": classification or "unresolved"
                }
            )
