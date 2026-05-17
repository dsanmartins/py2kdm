class ExceptionRelationResolver:
    """
    Resolves exception-related semantics in the generated KDM model.

    Current implementation:

    - raise X(...)  -> action:Throws -> StorableUnit X_exception
                       and X_exception --HasType--> X

    - try/except    -> TryUnit --ExceptionFlow--> CatchUnit

    - try/finally   -> TryUnit --ExitFlow--> FinallyUnit

    Notes:
    - KDM has a standard Throws relation.
    - KDM does not define a direct Catches relation.
    - Catch blocks are modeled as CatchUnit elements connected from TryUnit
      through ExceptionFlow.
    """

    def __init__(
        self,
        factory,
        id_index,
        statement_action_index,
        builtin_model=None,
        builtin_index=None,
        external_index=None,
        finally_action_index=None,
    ):
        self.factory = factory
        self.id_index = id_index
        self.statement_action_index = statement_action_index
        self.builtin_model = builtin_model
        self.builtin_index = builtin_index or {}
        self.external_index = external_index or {}
        self.finally_action_index = finally_action_index or {}

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
        control_type = item.get("control_type")

        if item_type == "control_structure" and control_type == "try":
            self._resolve_try_flows(item)

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
    # Try / catch / finally flow resolution
    # ------------------------------------------------------------

    def _resolve_try_flows(self, item: dict):
        try_action = self.statement_action_index.get(item.get("id"))

        if try_action is None:
            return

        for handler in item.get("handlers", []):
            catch_action = self.statement_action_index.get(handler.get("id"))

            if catch_action is None:
                continue

            self._create_exception_flow_relation(
                source=try_action,
                target=catch_action,
            )

            self._annotate_catch_unit(
                catch_action=catch_action,
                handler=handler,
            )

        finally_action = self.finally_action_index.get(item.get("id"))

        if finally_action is not None:
            self._create_exit_flow_relation(
                source=try_action,
                target=finally_action,
            )

    def _create_exception_flow_relation(self, source, target):
        if source is None or target is None:
            return

        if self._has_action_relation(
            source=source,
            target=target,
            relation_type="ExceptionFlow",
        ):
            return

        relation = self.factory.create_exception_flow_relation(target)

        if relation is None:
            return

        if self.factory.has_feature(source, "actionRelation"):
            source.actionRelation.append(relation)

    def _create_exit_flow_relation(self, source, target):
        if source is None or target is None:
            return

        if self._has_action_relation(
            source=source,
            target=target,
            relation_type="ExitFlow",
        ):
            return

        relation = self.factory.create_exit_flow_relation(target)

        if relation is None:
            return

        if self.factory.has_feature(source, "actionRelation"):
            source.actionRelation.append(relation)

    def _has_action_relation(self, source, target, relation_type: str) -> bool:
        if not self.factory.has_feature(source, "actionRelation"):
            return False

        for relation in source.actionRelation:
            if relation.eClass.name != relation_type:
                continue

            if getattr(relation, "to", None) is target:
                return True

        return False

    def _annotate_catch_unit(self, catch_action, handler: dict):
        exception_name = handler.get("exception")

        if not exception_name:
            self._add_attribute_once(
                catch_action,
                "exception_flow",
                "catch_all",
            )
            return

        exception_target = self._find_exception_by_name(exception_name)

        if exception_target is None:
            self._add_attribute_once(
                catch_action,
                "unresolved_exception_type",
                exception_name,
            )
            return

        self._add_attribute_once(
            catch_action,
            "exception_type_name",
            exception_name,
        )

        self._add_attribute_once(
            catch_action,
            "exception_target_name",
            getattr(exception_target, "name", exception_name),
        )

        self._get_or_create_catch_exception_parameter(
            catch_action=catch_action,
            exception_type=exception_target,
            exception_name=exception_name,
        )

    def _get_or_create_catch_exception_parameter(
        self,
        catch_action,
        exception_type,
        exception_name: str,
    ):
        """
        Creates a ParameterUnit inside CatchUnit to represent the exception
        object received by the handler.

        CatchUnit
          └── ParameterUnit exception_RepositoryError
                └── HasType -> RepositoryError
        """

        if catch_action is None or exception_type is None:
            return None

        if not self.factory.has_feature(catch_action, "codeElement"):
            return None

        parameter_name = f"exception_{exception_name}"

        for child in catch_action.codeElement:
            if getattr(child.eClass, "name", None) != "ParameterUnit":
                continue

            if getattr(child, "name", None) == parameter_name:
                return child

        parameter = self.factory.create_parameter_unit(parameter_name)

        self._add_attribute_once(
            parameter,
            "role",
            "caught_exception",
        )

        self._add_attribute_once(
            parameter,
            "exception_type_name",
            exception_name,
        )

        catch_action.codeElement.append(parameter)

        has_type = self.factory.create_has_type_relation(exception_type)

        if (
            has_type is not None
            and self.factory.has_feature(parameter, "codeRelation")
        ):
            parameter.codeRelation.append(has_type)

        return parameter

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
            if not item.get("exception") and not item.get("exception_calls"):
                self._add_attribute_once(
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
    # CatchUnit annotation only
    # ------------------------------------------------------------

    def _resolve_exception_handler(self, item: dict):
        """
        CatchUnit is connected and annotated from TryUnit using ExceptionFlow
        in _resolve_try_flows.

        This method intentionally does nothing to avoid duplicate attributes.
        """
        return

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

        self._add_attribute_once(
            exception_unit,
            "builtin_id",
            builtin_id,
        )

        self._add_attribute_once(
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
    # Throw relation creation
    # ------------------------------------------------------------

    def _create_exception_relation(self, source, target, kind: str):
        if source is None or target is None:
            return

        if kind != "throws":
            return

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

        if relation is None:
            return

        if self.factory.has_feature(source, "actionRelation"):
            source.actionRelation.append(relation)
            return

        self._add_attribute_once(
            source,
            "unresolved_exception_relation_throws",
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

        return False

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

        self._add_attribute_once(
            exception_data,
            "role",
            "thrown_exception",
        )

        self._add_attribute_once(
            exception_data,
            "exception_type_name",
            exception_type_name,
        )

        if self.factory.has_feature(source, "codeElement"):
            source.codeElement.append(exception_data)
        else:
            return None

        has_type = self.factory.create_has_type_relation(exception_type)

        if (
            has_type is not None
            and self.factory.has_feature(exception_data, "codeRelation")
        ):
            exception_data.codeRelation.append(has_type)

        return exception_data

    # ------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------

    def _has_attribute(self, element, tag: str, value: str) -> bool:
        if not self.factory.has_feature(element, "attribute"):
            return False

        for attribute in element.attribute:
            if getattr(attribute, "tag", None) != tag:
                continue

            if getattr(attribute, "value", None) == str(value):
                return True

        return False

    def _add_attribute_once(self, element, tag: str, value):
        if value is None:
            return

        if self._has_attribute(element, tag, value):
            return

        self.factory.add_attribute(element, tag, value)
