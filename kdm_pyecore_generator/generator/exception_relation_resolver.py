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
        -> X_exception --code::HasType--> X

    - try / except
        -> TryUnit
        -> CatchUnit
        -> TryUnit --action::ExceptionFlow--> CatchUnit

    - try / finally
        -> TryUnit
        -> FinallyUnit
        -> TryUnit --action::ExitFlow--> FinallyUnit

    The resolver intentionally avoids generic ActionRelationship elements with
    temporary attributes such as kind="catches". Exception handling is modeled
    with KDM-specific metaclasses whenever possible.
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
        self.known_builtin_exceptions = {
            "BaseException", "Exception", "ArithmeticError", "AssertionError",
            "AttributeError", "EOFError", "ImportError", "IndexError",
            "KeyError", "KeyboardInterrupt", "LookupError", "MemoryError",
            "NameError", "NotImplementedError", "OSError", "OverflowError",
            "RecursionError", "ReferenceError", "RuntimeError", "StopIteration",
            "SyntaxError", "SystemError", "SystemExit", "TypeError",
            "UnboundLocalError", "ValueError", "ZeroDivisionError",
        }
        self.finally_action_index = finally_action_index or {}

    # ------------------------------------------------------------
    # JSON compatibility helpers
    # ------------------------------------------------------------

    def _json_get(self, item: dict, snake_name: str, camel_name: str = None, default=None):
        if item is None:
            return default

        if snake_name in item:
            return item.get(snake_name)

        if camel_name and camel_name in item:
            return item.get(camel_name)

        return default

    def _json_list(self, item: dict, snake_name: str, camel_name: str = None):
        value = self._json_get(item, snake_name, camel_name, [])

        if value is None:
            return []

        return value

    def _element_type_name(self, element):
        if element is None:
            return None

        try:
            return getattr(element.eClass, "name", None)
        except Exception:
            return None

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

        for item in callable_model.get("body", []):
            self._resolve_body_item(item)

    def _resolve_body_item(self, item: dict):
        """
        Recursively resolves exception semantics for a body item and its nested
        children.
        """

        item_type = item.get("type")
        statement_type = self._json_get(item, "statement_type", "statementType")
        control_type = self._json_get(item, "control_type", "controlType")

        if item_type == "control_structure" and control_type == "try":
            self._resolve_try_flows(item)

        if statement_type in {"raise", "throw"}:
            self._resolve_raise(item)

        if item_type == "exception_handler":
            self._resolve_exception_handler(item)

        for child in self._json_list(item, "body"):
            self._resolve_body_item(child)

        for child in self._json_list(item, "orelse", "elseBody"):
            self._resolve_body_item(child)

        for child in self._json_list(item, "finalbody", "finallyBody"):
            self._resolve_body_item(child)

        for handler in self._json_list(item, "handlers", "catchClauses"):
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
            try_action = self._find_try_unit_by_source(item)

        if try_action is None:
            return

        for handler in self._json_list(item, "handlers", "catchClauses"):
            catch_action = self.statement_action_index.get(handler.get("id"))

            if catch_action is None:
                catch_action = self._find_catch_unit_by_source(try_action, handler)

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

    def _find_try_unit_by_source(self, item: dict):
        return self._find_action_by_type_and_source(
            element_type="TryUnit",
            line_start=self._json_get(item, "line_start", "lineStart"),
            line_end=self._json_get(item, "line_end", "lineEnd"),
        )

    def _find_catch_unit_by_source(self, try_action, handler: dict):
        if try_action is None or not self.factory.has_feature(try_action, "codeElement"):
            return None

        line_start = self._json_get(handler, "line_start", "lineStart")
        line_end = self._json_get(handler, "line_end", "lineEnd")

        for child in try_action.codeElement:
            if self._element_type_name(child) != "CatchUnit":
                continue

            if self._source_lines_match(child, line_start, line_end):
                return child

        for child in try_action.codeElement:
            if self._element_type_name(child) == "CatchUnit":
                return child

        return None

    def _find_action_by_type_and_source(self, element_type: str, line_start, line_end):
        for action in self.statement_action_index.values():
            if self._element_type_name(action) != element_type:
                continue

            if self._source_lines_match(action, line_start, line_end):
                return action

        return None

    def _source_lines_match(self, element, line_start, line_end) -> bool:
        if element is None:
            return False

        if line_start is None and line_end is None:
            return False

        if not self.factory.has_feature(element, "source"):
            return False

        for source_ref in element.source:
            for region in getattr(source_ref, "region", []):
                start = getattr(region, "startLine", None)
                end = getattr(region, "endLine", None)

                if line_start is not None and start != line_start:
                    continue

                if line_end is not None and end != line_end:
                    continue

                return True

        return False

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
            if self._element_type_name(relation) != relation_type:
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

        exception_name = (
            self._json_get(handler, "exception", "exceptionType")
            or handler.get("type")
        )

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
                    └── code::HasType -> RepositoryError
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

        Resolution priority:
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

        # Search external index by exact or simple name before falling back to builtins.
        for element_id, element in self.external_index.items():
            element_name = getattr(element, "name", None)
            if element_name == exception_name:
                return element
            if isinstance(element_id, str):
                clean_id = element_id.replace("external_type:", "").replace("external:", "")
                if clean_id == exception_name or clean_id.endswith(f".{exception_name}"):
                    return element

        return self._get_or_create_builtin_exception(exception_name)

    def _get_or_create_builtin_exception(self, exception_name: str):
        """
        Creates or reuses a builtin exception ClassUnit inside the
        PythonBuiltins CodeModel.
        """

        if not exception_name:
            return None

        # Only true Python built-in exceptions belong in PythonBuiltins.
        # Qualified external exceptions such as aiohttp.client_exceptions.ClientError
        # must remain in ExternalLibraries or be left unresolved.
        simple_name = str(exception_name).split(".")[-1]
        if "." in str(exception_name) or simple_name not in self.known_builtin_exceptions:
            return None

        exception_name = simple_name
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
        creates a StorableUnit and, only when a valid KDM Datatype is available,
        links it with code::HasType.

        This method is intentionally defensive because Python exception targets
        can sometimes resolve to StorableUnit instances. HasType.to cannot point
        to StorableUnit; it must point to a Datatype-compatible element.
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

        datatype_target = self._extract_hastype_target(exception_type)

        if datatype_target is not None:
            try:
                has_type = self.factory.create_has_type_relation(datatype_target)
            except Exception:
                has_type = None

            if (
                has_type is not None
                and self.factory.has_feature(exception_data, "codeRelation")
            ):
                exception_data.codeRelation.append(has_type)

        return exception_data

    def _extract_hastype_target(self, element):
        """
        Returns an element that is safe to use as HasType.to, or None.

        If the resolved exception target is already a Datatype-compatible KDM
        element, it is returned. If it is a StorableUnit, the method tries to
        reuse an existing HasType target from that StorableUnit.
        """

        if element is None:
            return None

        element_type = self._element_type_name(element)

        if element_type == "StorableUnit":
            if self.factory.has_feature(element, "codeRelation"):
                for relation in element.codeRelation:
                    if self._element_type_name(relation) != "HasType":
                        continue

                    target = getattr(relation, "to", None)

                    if target is not None and self._element_type_name(target) != "StorableUnit":
                        return target

            return None

        return element

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
