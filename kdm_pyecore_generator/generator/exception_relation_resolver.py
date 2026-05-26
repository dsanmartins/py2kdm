class ExceptionRelationResolver:
    """
    Resolves exception-related semantics in the generated KDM model.

    This resolver transforms exception information from the intermediate JSON
    model into standard KDM 1.4 action elements and action relations.

    It creates the following mappings:

    - raise X(...)
        -> ActionElement kind="raise"
        -> StorableUnit X_exception
        -> action::Throws -> X_exception
        -> X_exception --code::HasType--> Datatype(X)

    - try / except
        -> TryUnit
        -> CatchUnit
        -> TryUnit --action::ExceptionFlow--> CatchUnit

    - try / finally
        -> TryUnit
        -> FinallyUnit
        -> TryUnit --action::ExitFlow--> FinallyUnit

    Important:
    code::HasType.to must point to a Datatype. It must not point to ClassUnit,
    StorableUnit, MethodUnit, ActionElement, etc. Therefore, whenever an
    exception target is resolved to a non-Datatype KDM element, this resolver
    creates or reuses a generic Datatype with the same name.
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
        """
        Initializes the exception relation resolver.

        Parameters
        ----------
        factory:
            KDMFactory used to create KDM elements and relations.

        id_index:
            Dictionary mapping intermediate JSON ids to generated KDM elements.

        statement_action_index:
            Dictionary mapping JSON body ids to ActionElement, TryUnit,
            CatchUnit or FinallyUnit instances created by BodyActionMapper.

        builtin_model:
            CodeModel used to store builtin Python exceptions such as
            ValueError, OSError or Exception.

        builtin_index:
            Optional dictionary of already-created builtin elements.

        external_index:
            Optional dictionary of external KDM targets created by the external
            model builder.

        finally_action_index:
            Dictionary mapping try body ids to synthetic FinallyUnit elements.
        """

        self.factory = factory
        self.id_index = id_index
        self.statement_action_index = statement_action_index
        self.builtin_model = builtin_model
        self.builtin_index = builtin_index or {}
        self.external_index = external_index or {}
        self.finally_action_index = finally_action_index or {}

        # Cache for Datatype objects used as targets of code::HasType.
        self.exception_datatype_index = {}

    def _get_value(self, data: dict, *keys, default=None):
        if not isinstance(data, dict):
            return default

        for key in keys:
            if key in data and data.get(key) is not None:
                return data.get(key)

        return default

    def _get_list(self, data: dict, *keys):
        value = self._get_value(data, *keys, default=[])

        if value is None:
            return []

        if isinstance(value, list):
            return value

        return [value]

    def _statement_type(self, item: dict):
        return self._get_value(item, "statement_type", "statementType")

    def _control_type(self, item: dict):
        return self._get_value(item, "control_type", "controlType")

    def resolve(self, data: dict):
        """
        Resolves exception semantics for all functions and methods contained
        in the intermediate JSON model.
        """

        for file_model in data.get("files", []):
            for cls in file_model.get("classes", []):
                for method in cls.get("methods", []):
                    self._resolve_callable(method)

            for func in file_model.get("functions", []):
                self._resolve_callable(func)

        for element in data.get("elements", []):
            for method in element.get("methods", []):
                self._resolve_callable(method)

    def _resolve_callable(self, callable_model: dict):
        """
        Resolves exception-related statements inside a single callable body.
        """

        for item in self._get_list(callable_model, "body"):
            self._resolve_body_item(item)

    def _resolve_body_item(self, item: dict):
        """
        Recursively resolves exception semantics for a body item and its nested
        children.
        """

        item_type = item.get("type")
        statement_type = self._statement_type(item)
        control_type = self._control_type(item)

        if item_type == "control_structure" and control_type == "try":
            self._resolve_try_flows(item)

        if statement_type in {"raise", "throw"}:
            self._resolve_raise(item)

        if item_type == "exception_handler":
            self._resolve_exception_handler(item)

        for child in self._get_list(item, "body"):
            self._resolve_body_item(child)

        for child in self._get_list(item, "orelse", "elseBody"):
            self._resolve_body_item(child)

        for child in self._get_list(item, "finalbody", "finallyBody"):
            self._resolve_body_item(child)

        for handler in self._get_list(item, "handlers", "catchClauses"):
            self._resolve_body_item(handler)

    # ------------------------------------------------------------
    # Try / catch / finally flow resolution
    # ------------------------------------------------------------

    def _resolve_try_flows(self, item: dict):
        """
        Creates ExceptionFlow and ExitFlow relations for a try statement.
        """

        try_action = self.statement_action_index.get(item.get("id"))

        if try_action is None:
            return

        for handler in self._get_list(item, "handlers", "catchClauses"):
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
        """
        Adds lightweight traceability metadata to a CatchUnit and creates a
        ParameterUnit representing the caught exception object when the
        exception type is known.
        """

        exception_name = self._get_value(handler, "exception", "exceptionType")

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
        Creates or reuses a ParameterUnit inside a CatchUnit to represent the
        exception object received by an exception handler.

        Expected structure:

            CatchUnit
              └── ParameterUnit exception_RepositoryError
                    └── code::HasType -> Datatype(RepositoryError)
        """

        if catch_action is None or exception_type is None:
            return None

        if not self.factory.has_feature(catch_action, "codeElement"):
            return None

        datatype_target = self._as_datatype_target(exception_type)

        if datatype_target is None:
            return None

        parameter_name = f"exception_{exception_name}"

        for child in catch_action.codeElement:
            if getattr(child.eClass, "name", None) != "ParameterUnit":
                continue

            if getattr(child, "name", None) == parameter_name:
                self._ensure_has_type(child, datatype_target)
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

        self._ensure_has_type(parameter, datatype_target)

        return parameter

    # ------------------------------------------------------------
    # Raise resolution
    # ------------------------------------------------------------

    def _resolve_raise(self, item: dict):
        """
        Resolves a raise statement.

        A typed raise creates a Throws relation. A bare raise is marked as a
        rethrow using exception_flow="rethrow".
        """

        raise_action = self.statement_action_index.get(item.get("id"))

        if raise_action is None:
            return

        exception_target = self._find_exception_target_from_raise(item)

        if exception_target is None:
            if not self._get_value(item, "exception") and not self._get_list(item, "exception_calls", "exceptionCalls"):
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

        Resolution priority:
        1. exception_calls[*].target_id
        2. item["exception"]
        """

        for call in self._get_list(item, "exception_calls", "exceptionCalls"):
            target_id = self._get_value(call, "target_id", "targetId", "resolvedTarget")

            if target_id:
                target = self._find_target_by_id(target_id)

                if target is not None:
                    return target

        exception_name = self._get_value(item, "exception", "exceptionType")

        if exception_name:
            return self._find_exception_by_name(exception_name)

        return None

    # ------------------------------------------------------------
    # CatchUnit annotation only
    # ------------------------------------------------------------

    def _resolve_exception_handler(self, item: dict):
        """
        Intentionally does nothing.

        CatchUnit elements are connected and annotated from the owning TryUnit
        in _resolve_try_flows. This avoids duplicate attributes when the
        recursive traversal later reaches the handler node.
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
        Creates or reuses a builtin exception ClassUnit inside the
        PythonBuiltins CodeModel.

        The ClassUnit is useful for structural navigation. When the exception
        is used as a type target of HasType, it will be converted to a Datatype
        by _as_datatype_target(...).
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
        """
        Creates a KDM Throws relation for a raise action.
        """

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
        Creates or reuses a StorableUnit representing a thrown exception object.

        KDM Throws.to must point to a DataElement. Therefore, the generator
        creates a StorableUnit and links it to a Datatype using code::HasType.

        Expected structure:

            raise ActionElement
              ├── StorableUnit RepositoryError_exception
              │     └── code::HasType -> Datatype(RepositoryError)
              └── action::Throws -> RepositoryError_exception
        """

        if source is None or exception_type is None:
            return None

        exception_type_name = getattr(exception_type, "name", None)

        if not exception_type_name:
            exception_type_name = str(exception_type)

        datatype_target = self._as_datatype_target(exception_type)

        if datatype_target is None:
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
                    self._ensure_has_type(child, datatype_target)
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

        self._ensure_has_type(exception_data, datatype_target)

        return exception_data

    # ------------------------------------------------------------
    # Datatype normalization for HasType
    # ------------------------------------------------------------

    def _as_datatype_target(self, exception_type):
        """
        Ensures that the target used by code::HasType is a Datatype.

        HasType.to must point to a Datatype. It must not point to StorableUnit,
        ClassUnit, MethodUnit, ActionElement, etc.

        If exception_type is already a Datatype or one of its concrete
        subclasses, it is returned as-is. Otherwise, a generic Datatype is
        created or reused using the element name.
        """

        if exception_type is None:
            return None

        if self._is_datatype(exception_type):
            return exception_type

        type_name = getattr(exception_type, "name", None)

        if not type_name:
            type_name = str(exception_type)

        return self._get_or_create_exception_datatype(type_name)

    def _is_datatype(self, element) -> bool:
        """
        Returns True when element is a Datatype-compatible KDM type.
        """

        try:
            eclass_name = element.eClass.name
        except AttributeError:
            return False

        datatype_names = {
            "Datatype",
            "BooleanType",
            "IntegerType",
            "StringType",
            "FloatType",
            "VoidType",
            "CharType",
            "OctetType",
            "DecimalType",
            "ScaledType",
            "DateType",
            "TimeType",
            "OrdinalType",
            "BitstringType",
            "EnumeratedType",
            "CompositeType",
            "RecordType",
            "ArrayType",
            "PointerType",
            "RangeType",
            "BagType",
            "SetType",
            "SequenceType",
            "Signature",
        }

        return eclass_name in datatype_names

    def _get_or_create_exception_datatype(self, type_name: str):
        """
        Creates or reuses a generic Datatype for an exception type.
        """

        if not type_name:
            return None

        if type_name in self.exception_datatype_index:
            return self.exception_datatype_index[type_name]

        datatype_id = f"exception_datatype:{type_name}"

        if datatype_id in self.id_index:
            candidate = self.id_index[datatype_id]

            if self._is_datatype(candidate):
                self.exception_datatype_index[type_name] = candidate
                return candidate

        datatype = self.factory.create_generic_datatype(type_name)

        self._add_attribute_once(
            datatype,
            "external",
            "true",
        )

        self._add_attribute_once(
            datatype,
            "exception_type",
            "true",
        )

        self._add_attribute_once(
            datatype,
            "exception_type_name",
            type_name,
        )

        if (
            self.builtin_model is not None
            and self.factory.has_feature(self.builtin_model, "codeElement")
        ):
            self.builtin_model.codeElement.append(datatype)

        self.exception_datatype_index[type_name] = datatype
        self.id_index[datatype_id] = datatype

        return datatype

    def _ensure_has_type(self, element, datatype_target):
        """
        Adds code::HasType from element to datatype_target if possible and not
        already present.
        """

        if element is None or datatype_target is None:
            return

        if not self._is_datatype(datatype_target):
            return

        if not self.factory.has_feature(element, "codeRelation"):
            return

        for relation in element.codeRelation:
            if relation.eClass.name != "HasType":
                continue

            if getattr(relation, "to", None) is datatype_target:
                return

        has_type = self.factory.create_has_type_relation(datatype_target)

        if has_type is not None:
            element.codeRelation.append(has_type)

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
