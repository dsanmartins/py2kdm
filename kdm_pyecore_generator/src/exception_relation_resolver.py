class ExceptionRelationResolver:
    """
    Resolves exception-related semantics in the generated KDM model.

    Current implementation:

    - raise X(...)  -> action:Throws -> X
    - except X:     -> generic ActionRelationship with attribute kind="catches"

    Notes:
    - KDM has a standard Throws relation.
    - KDM does not define a direct Catches relation. The more precise KDM
      modeling for catch blocks is TryUnit/CatchUnit plus ExceptionFlow.
      For now, we keep catches as a generic ActionRelationship.
    """

    def __init__(
        self,
        factory,
        id_index,
        statement_action_index,
        builtin_model=None,
        builtin_index=None,
        external_index=None,
    ):
        self.factory = factory
        self.id_index = id_index
        self.statement_action_index = statement_action_index
        self.builtin_model = builtin_model
        self.builtin_index = builtin_index or {}
        self.external_index = external_index or {}

    def resolve(self, data: dict):
        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._resolve_callable(method)

            for func in file_model.get("functions", []):
                self._resolve_callable(func)

    def _resolve_callable(self, callable_model: dict):
        for item in callable_model.get("body", []):
            self._resolve_body_item(item)

    def _resolve_body_item(self, item: dict):
        item_type = item.get("type")
        statement_type = item.get("statement_type")

        if statement_type == "raise":
            self._resolve_raise(item)

        if item_type == "exception_handler":
            self._resolve_exception_handler(item)

        for child in item.get("body", []):
            self._resolve_body_item(child)

        for child in item.get("orelse", []):
            self._resolve_body_item(child)

        for child in item.get("finalbody", []):
            self._resolve_body_item(child)

        for handler in item.get("handlers", []):
            self._resolve_body_item(handler)

    # ------------------------------------------------------------
    # Raise resolution
    # ------------------------------------------------------------

    def _resolve_raise(self, item: dict):
        raise_action = self.statement_action_index.get(item.get("id"))

        if raise_action is None:
            return

        exception_target = self._find_exception_target_from_raise(item)

        if exception_target is None:
            # Python supports bare raise inside except blocks.
            #
            # Example:
            #     except Exception:
            #         raise
            #
            # This is not a new thrown type, but a rethrow of the active
            # exception.
            if not item.get("exception") and not item.get("exception_calls"):
                self.factory.add_attribute(
                    raise_action,
                    "exception_flow",
                    "rethrow",
                )
            return

        self._create_exception_relation(
            source=raise_action,
            target=exception_target,
            kind="throws",
        )

    def _find_exception_target_from_raise(self, item: dict):
        """
        Finds the KDM target for a raise statement.

        Priority:
        1. exception_calls[*].target_id
        2. item["exception"]
        """

        for call in item.get("exception_calls", []):
            target_id = call.get("target_id")

            if target_id:
                target = self._find_target_by_id(target_id)

                if target is not None:
                    return target

        exception_name = item.get("exception")

        if exception_name:
            return self._find_exception_by_name(exception_name)

        return None

    # ------------------------------------------------------------
    # Except resolution
    # ------------------------------------------------------------

    def _resolve_exception_handler(self, item: dict):
        except_action = self.statement_action_index.get(item.get("id"))

        if except_action is None:
            return

        exception_name = item.get("exception")

        # Bare except:
        #
        #     except:
        #         ...
        #
        # This catches any exception, but there is no explicit target class.
        if not exception_name:
            self.factory.add_attribute(
                except_action,
                "exception_flow",
                "catch_all",
            )
            return

        exception_target = self._find_exception_by_name(exception_name)

        if exception_target is None:
            return

        self._create_exception_relation(
            source=except_action,
            target=exception_target,
            kind="catches",
        )

    # ------------------------------------------------------------
    # Target resolution
    # ------------------------------------------------------------

    def _find_target_by_id(self, target_id: str):
        if not target_id:
            return None

        target = self.id_index.get(target_id)

        if target is not None:
            return target

        target = self.builtin_index.get(target_id)

        if target is not None:
            return target

        target = self.external_index.get(target_id)

        if target is not None:
            return target

        return None

    def _find_exception_by_name(self, exception_name: str):
        if not exception_name:
            return None

        candidates = [
            f"builtin:{exception_name}",
            f"class:{exception_name}",
            exception_name,
        ]

        for candidate in candidates:
            target = self._find_target_by_id(candidate)

            if target is not None:
                return target

        # Search by KDM element name or by fully qualified id ending.
        #
        # Example:
        #   exception_name = "RepositoryError"
        #   id = "class:example_project.repository.user_repository.RepositoryError"
        for element_id, element in self.id_index.items():
            element_name = getattr(element, "name", None)

            if element_name == exception_name:
                return element

            if isinstance(element_id, str) and element_id.endswith(
                f".{exception_name}"
            ):
                return element

        return self._get_or_create_builtin_exception(exception_name)

    def _get_or_create_builtin_exception(self, exception_name: str):
        """
        Creates builtin exception classes such as ValueError or OSError
        inside the PythonBuiltins CodeModel.

        If builtin_model is not provided, the exception is not created.
        """

        if not exception_name:
            return None

        builtin_id = f"builtin:{exception_name}"

        if builtin_id in self.builtin_index:
            return self.builtin_index[builtin_id]

        if self.builtin_model is None:
            return None

        exception_unit = self.factory.create_class_unit(
            name=exception_name
        )

        if self.factory.has_feature(exception_unit, "kind"):
            exception_unit.kind = "builtin_exception"

        self.factory.add_attribute(
            exception_unit,
            "builtin_id",
            builtin_id,
        )

        self.factory.add_attribute(
            exception_unit,
            "classification",
            "builtin",
        )

        if not self.factory.has_feature(self.builtin_model, "codeElement"):
            return None

        self.builtin_model.codeElement.append(exception_unit)

        self.builtin_index[builtin_id] = exception_unit
        self.id_index[builtin_id] = exception_unit

        return exception_unit

    # ------------------------------------------------------------
    # Relation creation
    # ------------------------------------------------------------

    def _create_exception_relation(self, source, target, kind: str):
        if source is None or target is None:
            return

        if kind == "throws":
            exception_data = self._get_or_create_thrown_exception_data(
                source=source,
                exception_type=target,
            )

            if exception_data is None:
                return

            if self._has_exception_relation(
                source=source,
                target=exception_data,
                kind="throws",
            ):
                return

            relation = self.factory.create_throws_relation(exception_data)

        elif kind == "catches":
            if self._has_exception_relation(source, target, kind):
                return

            relation = self.factory.create_action_relationship(
                target=target,
                kind="catches",
            )

        else:
            if self._has_exception_relation(source, target, kind):
                return

            relation = self.factory.create_action_relationship(
                target=target,
                kind=kind,
            )

        if relation is None:
            return

        if self.factory.has_feature(source, "actionRelation"):
            source.actionRelation.append(relation)
            return

        self.factory.add_attribute(
            source,
            f"unresolved_exception_relation_{kind}",
            getattr(target, "name", None),
        )

    def _has_exception_relation(self, source, target, kind: str) -> bool:
        if not self.factory.has_feature(source, "actionRelation"):
            return False

        for relation in source.actionRelation:
            if getattr(relation, "to", None) is not target:
                continue

            if kind == "throws" and relation.eClass.name == "Throws":
                return True

            relation_kind = self._get_relation_kind(relation)

            if relation_kind == kind:
                return True

        return False

    def _get_relation_kind(self, relation):
        if self.factory.has_feature(relation, "kind"):
            return getattr(relation, "kind", None)

        if self.factory.has_feature(relation, "attribute"):
            for attribute in relation.attribute:
                if getattr(attribute, "tag", None) == "kind":
                    return getattr(attribute, "value", None)

        return None


    def _get_or_create_thrown_exception_data(self, source, exception_type):
        """
        Creates or reuses a DataElement representing the exception object
        thrown by a raise action.

        KDM Throws.to must point to a DataElement, not to a ClassUnit.
        Therefore, we create:

            raise ActionElement
            ├── StorableUnit RepositoryError_exception
            │     └── HasType -> RepositoryError
            └── Throws -> RepositoryError_exception
        """

        if source is None or exception_type is None:
            return None

        exception_type_name = getattr(exception_type, "name", None)

        if not exception_type_name:
            return None

        # Reuse if it already exists under the raise action.
        if self.factory.has_feature(source, "codeElement"):
            for child in source.codeElement:
                if getattr(child.eClass, "name", None) != "StorableUnit":
                    continue

                if self._has_attribute(
                    child,
                    "exception_type_name",
                    exception_type_name,
                ):
                    return child

        exception_data = self.factory.create_storable_unit(
            name=f"{exception_type_name}_exception"
        )

        # Do not set:
        # exception_data.kind = "thrown_exception"
        #
        # StorableUnit.kind is an enum and only accepts:
        # global, local, external, register, unknown.
        #
        # We keep the semantic role as an Attribute instead.
        self.factory.add_attribute(
            exception_data,
            "role",
            "thrown_exception",
        )

        self.factory.add_attribute(
            exception_data,
            "exception_type_name",
            exception_type_name,
        )

        if self.factory.has_feature(source, "codeElement"):
            source.codeElement.append(exception_data)
        else:
            return None

        # Link the thrown exception data object to its exception class/type.
        has_type = self.factory.create_has_type_relation(exception_type)

        if (
            has_type is not None
            and self.factory.has_feature(exception_data, "codeRelation")
        ):
            exception_data.codeRelation.append(has_type)

        return exception_data

    def _has_attribute(self, element, tag: str, value: str) -> bool:
        if not self.factory.has_feature(element, "attribute"):
            return False

        for attribute in element.attribute:
            if getattr(attribute, "tag", None) != tag:
                continue

            if getattr(attribute, "value", None) == value:
                return True

        return False
