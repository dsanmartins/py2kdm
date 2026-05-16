import builtins

from extractor.builtin_type_registry import BuiltinTypeRegistry
from extractor.external_type_registry import ExternalTypeRegistry


class CallResolver:
    """
    Resolves and classifies function, method, constructor, external,
    built-in, ambiguous, self, inherited, and local-variable calls.
    """

    def __init__(self, symbol_table):
        self.symbol_table = symbol_table
        self.builtin_names = set(dir(builtins))

        self.class_models_by_qualified_name = {}
        self.class_models_by_name = {}

    def resolve_project_calls(self, project_model: dict):
        """
        Traverses the full project model and resolves all calls found
        inside functions and methods.
        """

        self._build_class_model_index(project_model)

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue

            imports = file_model.get("imports", [])

            for function_model in file_model.get("functions", []):
                self.resolve_parameters(function_model, imports)
                self.resolve_local_variables(function_model, imports)
                self.resolve_context_manager_variables(function_model)
                self.resolve_function_calls(function_model, imports)

            for class_model in file_model.get("classes", []):
                self.resolve_instance_attributes(class_model, imports)

                for method_model in class_model.get("methods", []):
                    self.resolve_parameters(method_model, imports, class_model)
                    self.resolve_local_variables(
                        method_model,
                        imports,
                        class_model
                    )
                    self.resolve_context_manager_variables(method_model)
                    self.resolve_function_calls(
                        method_model,
                        imports,
                        class_model
                    )

        return project_model

    def _build_class_model_index(self, project_model: dict):
        """
        Builds an index of class models to support inheritance resolution.
        """

        self.class_models_by_qualified_name = {}
        self.class_models_by_name = {}

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue

            for class_model in file_model.get("classes", []):
                name = class_model.get("name")
                qualified_name = class_model.get("qualified_name")

                if qualified_name:
                    self.class_models_by_qualified_name[qualified_name] = class_model

                if name:
                    self.class_models_by_name.setdefault(name, []).append(class_model)

    def resolve_local_variables(
        self,
        callable_model: dict,
        imports: list,
        class_model: dict = None
    ):
        """
        Resolves local variable assigned types.

        Examples:
        service = UserService()          -> UserService
        active_users = []                -> list
        logger = logging.getLogger(...)  -> logging.Logger
        """

        for variable in callable_model.get("local_variables", []):
            assigned_type = variable.get("assigned_type")

            if not assigned_type:
                continue

            if assigned_type == "cls" and class_model is not None:
                variable["resolved_type_id"] = class_model.get("id")
                variable["resolved_type_qualified_name"] = class_model.get(
                    "qualified_name"
                )
                variable["type_resolution"] = "cls_constructor"
                variable["resolved_from_cls"] = True
                continue

            if BuiltinTypeRegistry.is_builtin_type(assigned_type):
                variable["resolved_type_id"] = f"builtin_type:{assigned_type}"
                variable["resolved_type_qualified_name"] = assigned_type
                variable["type_resolution"] = "builtin"
                continue

            external_return_type = ExternalTypeRegistry.get_factory_return_type(
                assigned_type
            )

            if external_return_type:
                variable["resolved_type_id"] = (
                    f"external_type:{external_return_type}"
                )
                variable["resolved_type_qualified_name"] = external_return_type
                variable["type_resolution"] = "external_type"
                variable["external_factory"] = assigned_type
                continue

            class_candidates = self.symbol_table.find_classes_by_name(
                assigned_type
            )

            if len(class_candidates) == 1:
                variable["resolved_type_id"] = class_candidates[0].get("id")
                variable["resolved_type_qualified_name"] = class_candidates[0].get(
                    "qualified_name"
                )
                variable["type_resolution"] = "resolved"
                continue

            if len(class_candidates) > 1:
                variable["resolved_type_id"] = None
                variable["resolved_type_qualified_name"] = None
                variable["type_resolution"] = "ambiguous"
                variable["candidate_type_ids"] = [
                    candidate.get("id") for candidate in class_candidates
                ]
                continue

            imported_symbol = self._find_imported_symbol(assigned_type, imports)

            if imported_symbol is not None:
                variable["resolved_type_id"] = imported_symbol.get("target_id")
                variable["resolved_type_qualified_name"] = imported_symbol.get(
                    "target_qualified_name"
                )
                variable["type_resolution"] = imported_symbol.get(
                    "classification",
                    "external"
                )
                variable["import_source"] = imported_symbol
                continue

            variable["resolved_type_id"] = None
            variable["resolved_type_qualified_name"] = None
            variable["type_resolution"] = "unresolved"

    def resolve_instance_attributes(self, class_model: dict, imports: list = None):
        """
        Resolves the assigned types of instance attributes.

        Examples:
        self.repository = UserRepository()      -> UserRepository
        self.roles = []                         -> list
        self.logger = logging.getLogger(...)    -> logging.Logger
        """

        imports = imports or []

        for attribute in class_model.get("instance_attributes", []):
            assigned_type = attribute.get("assigned_type")

            if not assigned_type:
                continue

            if BuiltinTypeRegistry.is_builtin_type(assigned_type):
                attribute["resolved_type_id"] = f"builtin_type:{assigned_type}"
                attribute["resolved_type_qualified_name"] = assigned_type
                attribute["type_resolution"] = "builtin"
                continue

            external_return_type = ExternalTypeRegistry.get_factory_return_type(
                assigned_type
            )

            if external_return_type:
                attribute["resolved_type_id"] = (
                    f"external_type:{external_return_type}"
                )
                attribute["resolved_type_qualified_name"] = external_return_type
                attribute["type_resolution"] = "external_type"
                attribute["external_factory"] = assigned_type
                continue

            class_candidates = self.symbol_table.find_classes_by_name(
                assigned_type
            )

            if len(class_candidates) == 1:
                attribute["resolved_type_id"] = class_candidates[0].get("id")
                attribute["resolved_type_qualified_name"] = class_candidates[0].get(
                    "qualified_name"
                )
                attribute["type_resolution"] = "resolved"
                continue

            if len(class_candidates) > 1:
                attribute["resolved_type_id"] = None
                attribute["resolved_type_qualified_name"] = None
                attribute["type_resolution"] = "ambiguous"
                attribute["candidate_type_ids"] = [
                    candidate.get("id") for candidate in class_candidates
                ]
                continue

            imported_symbol = self._find_imported_symbol(assigned_type, imports)

            if imported_symbol is not None:
                attribute["resolved_type_id"] = imported_symbol.get("target_id")
                attribute["resolved_type_qualified_name"] = imported_symbol.get(
                    "target_qualified_name"
                )
                attribute["type_resolution"] = imported_symbol.get(
                    "classification",
                    "external"
                )
                attribute["import_source"] = imported_symbol
                continue

            attribute["resolved_type_id"] = None
            attribute["resolved_type_qualified_name"] = None
            attribute["type_resolution"] = "unresolved"

    def resolve_function_calls(
        self,
        callable_model: dict,
        imports: list,
        class_model: dict = None
    ):
        """
        Resolves every call contained in a function or method model.
        """

        for call_model in callable_model.get("calls", []):
            self.resolve_call(
                call_model,
                imports,
                callable_model=callable_model,
                class_model=class_model
            )

    def resolve_call(
        self,
        call_model: dict,
        imports: list,
        callable_model: dict = None,
        class_model: dict = None
    ):
        """
        Resolves a single call model.
        """

        call_kind = call_model.get("kind")

        if call_kind == "function_call":
            if self._resolve_cls_constructor_call(
                call_model,
                callable_model=callable_model,
                class_model=class_model
            ):
                return

            self._resolve_function_or_constructor_call(call_model, imports)

        elif call_kind == "method_call":
            self._resolve_method_call(
                call_model,
                imports,
                callable_model=callable_model,
                class_model=class_model
            )

        else:
            self._mark_unresolved(call_model)

    def _resolve_function_or_constructor_call(
        self,
        call_model: dict,
        imports: list
    ):
        """
        Resolves calls such as:

        print(...)
        UserService(...)
        validate_user(...)
        Path(...)
        """

        function_name = call_model.get("function") or call_model.get("name")

        if not function_name:
            self._mark_unresolved(call_model)
            return

        if function_name in self.builtin_names:
            call_model.update({
                "classification": "builtin",
                "resolved": True,
                "target_id": f"builtin:{function_name}",
                "candidate_targets": []
            })
            return

        class_candidates = self.symbol_table.find_classes_by_name(function_name)

        if len(class_candidates) == 1:
            candidate = class_candidates[0]
            call_model.update({
                "kind": "constructor_call",
                "classification": "constructor",
                "class_name": function_name,
                "resolved": True,
                "target_id": candidate.get("id"),
                "candidate_targets": []
            })
            return

        if len(class_candidates) > 1:
            call_model.update({
                "kind": "constructor_call",
                "classification": "constructor_ambiguous",
                "class_name": function_name,
                "resolved": False,
                "target_id": None,
                "candidate_targets": [
                    candidate.get("id") for candidate in class_candidates
                ]
            })
            return

        function_candidates = self.symbol_table.find_functions_by_name(
            function_name
        )

        if len(function_candidates) == 1:
            candidate = function_candidates[0]
            call_model.update({
                "classification": "internal",
                "resolved": True,
                "target_id": candidate.get("id"),
                "candidate_targets": []
            })
            return

        if len(function_candidates) > 1:
            call_model.update({
                "classification": "internal_ambiguous",
                "resolved": False,
                "target_id": None,
                "candidate_targets": [
                    candidate.get("id") for candidate in function_candidates
                ]
            })
            return

        imported_symbol = self._find_imported_symbol(function_name, imports)

        if imported_symbol is not None:
            if imported_symbol.get("classification") == "internal":
                target_type = imported_symbol.get("target_type")
                target_id = imported_symbol.get("target_id")

                if target_type == "class":
                    call_model.update({
                        "kind": "constructor_call",
                        "classification": "constructor",
                        "class_name": function_name,
                        "resolved": True,
                        "target_id": target_id,
                        "candidate_targets": [],
                        "import_source": imported_symbol
                    })
                    return

                if target_type == "function":
                    call_model.update({
                        "classification": "internal",
                        "resolved": True,
                        "target_id": target_id,
                        "candidate_targets": [],
                        "import_source": imported_symbol
                    })
                    return

            call_model.update({
                "classification": "external",
                "resolved": False,
                "target_id": None,
                "candidate_targets": [],
                "import_source": imported_symbol
            })
            return

        self._mark_unresolved(call_model)

    def _resolve_method_call(
        self,
        call_model: dict,
        imports: list,
        callable_model: dict = None,
        class_model: dict = None
    ):
        """
        Resolves method calls such as:

        json.dumps(...)
        logging.getLogger(...)
        self.repository.save(...)
        self._write_to_disk(...)
        service.create_user(...)
        """

        receiver = call_model.get("receiver")
        method_name = call_model.get("method")

        if not receiver or not method_name:
            self._mark_unresolved(call_model)
            return

        # 1. Imported receiver, e.g. json.dumps or logging.getLogger
        imported_receiver = self._find_imported_symbol(receiver, imports)

        if imported_receiver is not None:
            if imported_receiver.get("classification") == "internal":
                target_type = imported_receiver.get("target_type")
                target_qn = imported_receiver.get("target_qualified_name")

                if target_type == "class" and target_qn:
                    candidates = self._find_method_in_class_or_bases(
                        target_qn,
                        method_name
                    )

                    if self._apply_method_candidates(
                        call_model,
                        candidates,
                        "internal",
                        import_source=imported_receiver
                    ):
                        return

            call_model.update({
                "classification": "external",
                "resolved": False,
                "target_id": None,
                "candidate_targets": [],
                "import_source": imported_receiver
            })
            return

        # 2. super().method(...)
        if receiver == "super" and class_model is not None:
            resolved = self._resolve_super_method_call(
                call_model,
                method_name,
                class_model
            )

            if resolved:
                return

        # 3. self.method(...)
        if receiver == "self" and class_model is not None:
            candidates = self._find_method_in_class_or_bases(
                class_model.get("qualified_name"),
                method_name
            )

            if self._apply_method_candidates(
                call_model,
                candidates,
                "internal"
            ):
                return

        # 4. self.attribute.method(...)
        if receiver.startswith("self.") and class_model is not None:
            resolved = self._resolve_self_attribute_method_call(
                call_model,
                receiver,
                method_name,
                class_model
            )

            if resolved:
                return

        # 4. parameter.method(...)
        if callable_model is not None:
            resolved = self._resolve_parameter_method_call(
                call_model,
                receiver,
                method_name,
                callable_model
            )

            if resolved:
                return

        # 5. chained builtin method call, e.g. name.strip().title()
        if callable_model is not None:
            resolved = self._resolve_chained_builtin_method_call(
                call_model,
                receiver,
                method_name,
                callable_model,
                class_model
            )

            if resolved:
                return

        # context_variable.method(...), e.g. file.write(...)
        if callable_model is not None:
            resolved = self._resolve_context_variable_method_call(
                call_model,
                receiver,
                method_name,
                callable_model
            )

            if resolved:
                return

        # 5. local_variable.method(...)
        if callable_model is not None:
            resolved = self._resolve_local_variable_method_call(
                call_model,
                receiver,
                method_name,
                callable_model
            )

            if resolved:
                return

        # 6. ClassName.method(...)
        class_method_key = f"{receiver}.{method_name}"
        method_candidates = self.symbol_table.find_methods_by_class_and_name(
            class_method_key
        )

        if self._apply_method_candidates(
            call_model,
            method_candidates,
            "internal"
        ):
            return

        # 7. Method-name fallback
        method_name_candidates = self.symbol_table.find_methods_by_name(
            method_name
        )

        if len(method_name_candidates) == 1:
            candidate = method_name_candidates[0]
            call_model.update({
                "classification": "internal_candidate",
                "resolved": False,
                "target_id": None,
                "candidate_targets": [candidate.get("id")]
            })
            return

        if len(method_name_candidates) > 1:
            call_model.update({
                "classification": "internal_ambiguous",
                "resolved": False,
                "target_id": None,
                "candidate_targets": [
                    candidate.get("id") for candidate in method_name_candidates
                ]
            })
            return

        self._mark_unresolved(call_model)

    def _resolve_self_attribute_method_call(
        self,
        call_model: dict,
        receiver: str,
        method_name: str,
        class_model: dict
    ):
        """
        Resolves calls such as:

        self.repository.save()
        """

        for attribute in class_model.get("instance_attributes", []):
            if attribute.get("full_name") != receiver:
                continue

            assigned_type = attribute.get("assigned_type")
            resolved_type_qn = attribute.get("resolved_type_qualified_name")
            resolved_type_id = attribute.get("resolved_type_id")

            if not assigned_type and not resolved_type_qn:
                call_model.update({
                    "classification": "unresolved_attribute_type",
                    "resolved": False,
                    "target_id": None,
                    "candidate_targets": []
                })
                return True

            receiver_type = resolved_type_qn or assigned_type

            if self._apply_builtin_type_method(
                call_model,
                receiver_type=receiver_type,
                receiver_type_id=resolved_type_id,
                method_name=method_name
            ):
                return True

            if self._apply_external_type_method(
                call_model,
                receiver_type=receiver_type,
                receiver_type_id=resolved_type_id,
                method_name=method_name
            ):
                return True

            search_key = resolved_type_qn or assigned_type

            candidates = self._find_method_in_class_or_bases(
                search_key,
                method_name
            )

            if self._apply_method_candidates(
                call_model,
                candidates,
                "internal",
                receiver_type=assigned_type,
                receiver_type_id=attribute.get("resolved_type_id")
            ):
                return True

            call_model.update({
                "classification": "unresolved_method_on_attribute",
                "resolved": False,
                "target_id": None,
                "candidate_targets": [],
                "receiver_type": assigned_type,
                "receiver_type_id": attribute.get("resolved_type_id")
            })
            return True

        return False

    def _resolve_local_variable_method_call(
        self,
        call_model: dict,
        receiver: str,
        method_name: str,
        callable_model: dict
    ):
        """
        Resolves calls such as:

        service = UserService()
        service.create_user(...)
        """

        for variable in callable_model.get("local_variables", []):
            if variable.get("name") != receiver:
                continue

            assigned_type = variable.get("assigned_type")
            resolved_type_qn = variable.get("resolved_type_qualified_name")
            resolved_type_id = variable.get("resolved_type_id")

            if not assigned_type and not resolved_type_qn:
                return False

            receiver_type = resolved_type_qn or assigned_type

            if self._apply_builtin_type_method(
                call_model,
                receiver_type=receiver_type,
                receiver_type_id=resolved_type_id,
                method_name=method_name
            ):
                return True

            if self._apply_external_type_method(
                call_model,
                receiver_type=receiver_type,
                receiver_type_id=resolved_type_id,
                method_name=method_name
            ):
                return True

            search_key = resolved_type_qn or assigned_type

            candidates = self._find_method_in_class_or_bases(
                search_key,
                method_name
            )

            if self._apply_method_candidates(
                call_model,
                candidates,
                "internal",
                receiver_type=assigned_type,
                receiver_type_id=variable.get("resolved_type_id")
            ):
                return True

        return False

    def _find_method_in_class_or_bases(
        self,
        class_name_or_qn: str,
        method_name: str,
        visited: set = None
    ):
        """
        Finds a method in a class or its base classes.
        """

        visited = visited or set()

        if not class_name_or_qn or class_name_or_qn in visited:
            return []

        visited.add(class_name_or_qn)

        class_models = []

        if class_name_or_qn in self.class_models_by_qualified_name:
            class_models.append(
                self.class_models_by_qualified_name[class_name_or_qn]
            )
        else:
            class_models.extend(
                self.class_models_by_name.get(class_name_or_qn, [])
            )

        candidates = []

        for class_model in class_models:
            class_name = class_model.get("name")
            class_qn = class_model.get("qualified_name")

            keys = [
                f"{class_name}.{method_name}",
                f"{class_qn}.{method_name}"
            ]

            for key in keys:
                candidates.extend(
                    self.symbol_table.find_methods_by_class_and_name(key)
                )

            for base in class_model.get("bases", []):
                candidates.extend(
                    self._find_method_in_class_or_bases(
                        base,
                        method_name,
                        visited
                    )
                )

        return self._deduplicate_symbols(candidates)

    def _apply_method_candidates(
        self,
        call_model: dict,
        candidates: list,
        classification: str,
        receiver_type: str = None,
        receiver_type_id: str = None,
        import_source: dict = None
    ):
        """
        Applies method resolution candidates to a call model.
        """

        candidates = self._deduplicate_symbols(candidates)

        if len(candidates) == 1:
            candidate = candidates[0]

            update = {
                "classification": classification,
                "resolved": True,
                "target_id": candidate.get("id"),
                "candidate_targets": []
            }

            if receiver_type is not None:
                update["receiver_type"] = receiver_type

            if receiver_type_id is not None:
                update["receiver_type_id"] = receiver_type_id

            if import_source is not None:
                update["import_source"] = import_source

            call_model.update(update)
            return True

        if len(candidates) > 1:
            update = {
                "classification": "internal_ambiguous",
                "resolved": False,
                "target_id": None,
                "candidate_targets": [
                    candidate.get("id") for candidate in candidates
                ]
            }

            if receiver_type is not None:
                update["receiver_type"] = receiver_type

            if receiver_type_id is not None:
                update["receiver_type_id"] = receiver_type_id

            if import_source is not None:
                update["import_source"] = import_source

            call_model.update(update)
            return True

        return False

    def _deduplicate_symbols(self, symbols: list):
        """
        Deduplicates symbols by id.
        """

        result = []
        seen = set()

        for symbol in symbols:
            symbol_id = symbol.get("id")

            if not symbol_id or symbol_id in seen:
                continue

            seen.add(symbol_id)
            result.append(symbol)

        return result

    def _find_imported_symbol(self, symbol_name: str, imports: list):
        """
        Checks whether a symbol name appears in the imports of the current file.

        Supports:
        - import json
        - import logging
        - import numpy as np
        - from pathlib import Path
        - from package.module import ClassName
        """

        if not symbol_name:
            return None

        root_name = symbol_name.split(".")[0]

        for import_model in imports:
            import_type = import_model.get("type")

            if import_type == "import":
                module = import_model.get("module")
                alias = import_model.get("alias")

                visible_name = alias if alias else module

                if root_name == visible_name:
                    return import_model

                if module and root_name == module.split(".")[0]:
                    return import_model

            elif import_type == "from_import":
                name = import_model.get("name")
                alias = import_model.get("alias")

                visible_name = alias if alias else name

                if root_name == visible_name:
                    return import_model

        return None

    def _mark_unresolved(self, call_model: dict):
        """
        Marks a call as unresolved.
        """

        call_model.update({
            "classification": "unresolved",
            "resolved": False,
            "target_id": None,
            "candidate_targets": []
        })


    def _apply_builtin_type_method(
        self,
        call_model: dict,
        receiver_type: str,
        receiver_type_id: str,
        method_name: str
    ):
        """
        Classifies a method call on a known built-in type.

        Example:
        self.roles.append(...)
        active_users.append(...)
        name.strip(...)
        """

        if not BuiltinTypeRegistry.is_builtin_type(receiver_type):
            return False

        if not BuiltinTypeRegistry.has_method(receiver_type, method_name):
            return False

        call_model.update({
            "classification": "builtin_type_method",
            "resolved": True,
            "target_id": f"builtin_type:{receiver_type}.{method_name}",
            "candidate_targets": [],
            "receiver_type": receiver_type,
            "receiver_type_id": receiver_type_id or f"builtin_type:{receiver_type}"
        })

        return True


    def _resolve_super_method_call(
        self,
        call_model: dict,
        method_name: str,
        class_model: dict
    ):
        """
        Resolves calls such as:

        super().method()

        using the base classes of the current class.

        Example:
        class User(BaseEntity):
            def to_dict(self):
                return super().to_dict()

        super().to_dict() should resolve to BaseEntity.to_dict().
        """

        if class_model is None:
            return False

        bases = class_model.get("bases", [])

        if not bases:
            call_model.update({
                "classification": "unresolved_super_call",
                "resolved": False,
                "target_id": None,
                "candidate_targets": []
            })
            return True

        candidates = []

        for base in bases:
            candidates.extend(
                self._find_method_in_class_or_bases(
                    base,
                    method_name
                )
            )

        candidates = self._deduplicate_symbols(candidates)

        if len(candidates) == 1:
            candidate = candidates[0]

            call_model.update({
                "classification": "internal",
                "resolved": True,
                "target_id": candidate.get("id"),
                "candidate_targets": [],
                "receiver_type": "super",
                "receiver_type_id": self._find_class_id_by_name_or_qn(
                    class_model.get("bases", [None])[0]
                ),
                "super_base_candidates": bases
            })
            return True

        if len(candidates) > 1:
            call_model.update({
                "classification": "internal_ambiguous",
                "resolved": False,
                "target_id": None,
                "candidate_targets": [
                    candidate.get("id") for candidate in candidates
                ],
                "receiver_type": "super",
                "super_base_candidates": bases
            })
            return True

        call_model.update({
            "classification": "unresolved_super_method",
            "resolved": False,
            "target_id": None,
            "candidate_targets": [],
            "receiver_type": "super",
            "super_base_candidates": bases
        })
        return True

    def _find_class_id_by_name_or_qn(self, class_name_or_qn: str):
        """
        Finds the class id for a class name or qualified name.
        """

        if not class_name_or_qn:
            return None

        if class_name_or_qn in self.class_models_by_qualified_name:
            return self.class_models_by_qualified_name[class_name_or_qn].get("id")

        class_models = self.class_models_by_name.get(class_name_or_qn, [])

        if len(class_models) == 1:
            return class_models[0].get("id")

        return None

    def resolve_parameters(
        self,
        callable_model: dict,
        imports: list,
        class_model: dict = None
    ):
        """
        Resolves parameter annotations.

        Examples:
        user: User              -> class:...User
        user_data: dict         -> builtin_type:dict
        name: str               -> builtin_type:str
        repository: UserRepository -> class:...UserRepository
        """

        for parameter in callable_model.get("parameters", []):
            # Backward compatibility: old models may still have string parameters.
            if isinstance(parameter, str):
                continue

            parameter_name = parameter.get("name")
            annotation = parameter.get("annotation")

            if not annotation:
                # Special case for self and cls.
                if parameter_name == "self" and class_model is not None:
                    parameter["resolved_type_id"] = class_model.get("id")
                    parameter["resolved_type_qualified_name"] = class_model.get(
                        "qualified_name"
                    )
                    parameter["type_resolution"] = "self"
                elif parameter_name == "cls" and class_model is not None:
                    parameter["resolved_type_id"] = class_model.get("id")
                    parameter["resolved_type_qualified_name"] = class_model.get(
                        "qualified_name"
                    )
                    parameter["type_resolution"] = "cls"
                continue

            self._resolve_type_annotation(parameter, annotation, imports)

    def _resolve_type_annotation(
        self,
        target_model: dict,
        annotation: str,
        imports: list
    ):
        """
        Resolves a type annotation into an internal class, built-in type,
        imported symbol, or unresolved type.
        """

        if not annotation:
            return

        # Simple normalization for common annotations.
        normalized_annotation = self._normalize_annotation(annotation)

        # 1. Built-in type
        if BuiltinTypeRegistry.is_builtin_type(normalized_annotation):
            target_model["resolved_type_id"] = (
                f"builtin_type:{normalized_annotation}"
            )
            target_model["resolved_type_qualified_name"] = normalized_annotation
            target_model["type_resolution"] = "builtin"
            return

        if ExternalTypeRegistry.is_external_type(normalized_annotation):
            target_model["resolved_type_id"] = (
                f"external_type:{normalized_annotation}"
            )
            target_model["resolved_type_qualified_name"] = normalized_annotation
            target_model["type_resolution"] = "external_type"
            return

        # 2. Internal class by simple name
        class_candidates = self.symbol_table.find_classes_by_name(
            normalized_annotation
        )

        if len(class_candidates) == 1:
            candidate = class_candidates[0]
            target_model["resolved_type_id"] = candidate.get("id")
            target_model["resolved_type_qualified_name"] = candidate.get(
                "qualified_name"
            )
            target_model["type_resolution"] = "resolved"
            return

        if len(class_candidates) > 1:
            target_model["resolved_type_id"] = None
            target_model["resolved_type_qualified_name"] = None
            target_model["type_resolution"] = "ambiguous"
            target_model["candidate_type_ids"] = [
                candidate.get("id") for candidate in class_candidates
            ]
            return

        # 3. Internal class by qualified name
        class_symbol = self.symbol_table.find_class_by_qualified_name(
            normalized_annotation
        )

        if class_symbol is not None:
            target_model["resolved_type_id"] = class_symbol.get("id")
            target_model["resolved_type_qualified_name"] = class_symbol.get(
                "qualified_name"
            )
            target_model["type_resolution"] = "resolved"
            return

        # 4. Imported symbol
        imported_symbol = self._find_imported_symbol(
            normalized_annotation,
            imports
        )

        if imported_symbol is not None:
            target_model["resolved_type_id"] = imported_symbol.get("target_id")
            target_model["resolved_type_qualified_name"] = imported_symbol.get(
                "target_qualified_name"
            )
            target_model["type_resolution"] = imported_symbol.get(
                "classification",
                "external"
            )
            target_model["import_source"] = imported_symbol
            return

        # 5. Unknown type
        target_model["resolved_type_id"] = None
        target_model["resolved_type_qualified_name"] = None
        target_model["type_resolution"] = "unresolved"

    def _normalize_annotation(self, annotation: str):
        """
        Normalizes simple annotation strings.

        Examples:
        list[str]      -> list
        dict[str, int] -> dict
        Optional[User] -> User
        List[User]     -> list
        """

        if not annotation:
            return annotation

        annotation = annotation.strip()

        # PEP 604 unions: User | None
        if "|" in annotation:
            parts = [
                part.strip()
                for part in annotation.split("|")
                if part.strip() not in {"None", "NoneType"}
            ]

            if len(parts) == 1:
                return self._normalize_annotation(parts[0])

            return annotation

        lower_map = {
            "List": "list",
            "Dict": "dict",
            "Tuple": "tuple",
            "Set": "set",
            "str": "str",
            "int": "int",
            "float": "float",
            "bool": "bool",
            "dict": "dict",
            "list": "list",
            "tuple": "tuple",
            "set": "set"
        }

        # Generic annotation: list[str], dict[str, int], List[User]
        if "[" in annotation and annotation.endswith("]"):
            base = annotation.split("[", 1)[0]

            if base in lower_map:
                return lower_map[base]

            # Optional[User] or Union[User, None]
            if base in {"Optional", "typing.Optional"}:
                inside = annotation.split("[", 1)[1][:-1]
                return self._normalize_annotation(inside)

            if base in {"Union", "typing.Union"}:
                inside = annotation.split("[", 1)[1][:-1]
                parts = [
                    part.strip()
                    for part in inside.split(",")
                    if part.strip() not in {"None", "NoneType"}
                ]

                if len(parts) == 1:
                    return self._normalize_annotation(parts[0])

        return lower_map.get(annotation, annotation)


    def _resolve_parameter_method_call(
        self,
        call_model: dict,
        receiver: str,
        method_name: str,
        callable_model: dict
    ):
        """
        Resolves method calls on annotated parameters.

        Example:
        def export_user(self, user: User):
            user.to_dict()

        user.to_dict() -> User.to_dict
        """

        for parameter in callable_model.get("parameters", []):
            if isinstance(parameter, str):
                continue

            if parameter.get("name") != receiver:
                continue

            annotation = parameter.get("annotation")
            resolved_type_id = parameter.get("resolved_type_id")
            resolved_type_qn = parameter.get("resolved_type_qualified_name")

            receiver_type = resolved_type_qn or annotation

            if not receiver_type:
                return False

            # Built-in parameter type: name: str, user_data: dict
            if self._apply_builtin_type_method(
                call_model,
                receiver_type=receiver_type,
                receiver_type_id=resolved_type_id,
                method_name=method_name
            ):
                return True

            if self._apply_external_type_method(
                call_model,
                receiver_type=receiver_type,
                receiver_type_id=resolved_type_id,
                method_name=method_name
            ):
                return True

            # 1. Prefer the exact receiver type.
            exact_candidates = self._find_method_in_exact_class(
                receiver_type,
                method_name
            )

            if self._apply_method_candidates(
                call_model,
                exact_candidates,
                "internal",
                receiver_type=annotation,
                receiver_type_id=resolved_type_id
            ):
                return True

            # 2. If the exact class does not define the method, search in base classes.
            inherited_candidates = self._find_method_in_class_or_bases(
                receiver_type,
                method_name
            )

            if self._apply_method_candidates(
                call_model,
                inherited_candidates,
                "internal",
                receiver_type=annotation,
                receiver_type_id=resolved_type_id
            ):
                return True

            call_model.update({
                "classification": "unresolved_method_on_parameter",
                "resolved": False,
                "target_id": None,
                "candidate_targets": [],
                "receiver_type": annotation,
                "receiver_type_id": resolved_type_id
            })
            return True

        return False

    def _find_method_in_exact_class(self, class_name_or_qn: str, method_name: str):
        """
        Finds a method only in the exact class, without searching base classes.

        This is useful for parameter-based dispatch:

        user: User
        user.to_dict()

        should prefer User.to_dict before inherited methods.
        """

        if not class_name_or_qn or not method_name:
            return []

        class_models = []

        if class_name_or_qn in self.class_models_by_qualified_name:
            class_models.append(
                self.class_models_by_qualified_name[class_name_or_qn]
            )
        else:
            class_models.extend(
                self.class_models_by_name.get(class_name_or_qn, [])
            )

        candidates = []

        for class_model in class_models:
            class_name = class_model.get("name")
            class_qn = class_model.get("qualified_name")

            keys = [
                f"{class_name}.{method_name}",
                f"{class_qn}.{method_name}"
            ]

            for key in keys:
                candidates.extend(
                    self.symbol_table.find_methods_by_class_and_name(key)
                )

        return self._deduplicate_symbols(candidates)

    def _resolve_chained_builtin_method_call(
        self,
        call_model: dict,
        receiver: str,
        method_name: str,
        callable_model: dict,
        class_model: dict = None
    ):
        """
        Resolves chained calls on built-in types.

        Example:
        name: str
        name.strip().title()

        The call analyzer may represent the second call as:

        receiver = "name.strip"
        method = "title"

        This method infers:
        name -> str
        str.strip() -> str
        str.title() -> str.title
        """

        if not receiver or "." not in receiver:
            return False

        receiver_parts = receiver.split(".")

        if len(receiver_parts) < 2:
            return False

        base_receiver = ".".join(receiver_parts[:-1])
        previous_method = receiver_parts[-1]

        base_type_info = self._infer_receiver_type(
            base_receiver,
            callable_model,
            class_model
        )

        if base_type_info is None:
            return False

        base_type = base_type_info.get("receiver_type")
        base_type_id = base_type_info.get("receiver_type_id")

        previous_return_type = BuiltinTypeRegistry.get_method_return_type(
            base_type,
            previous_method
        )

        if not previous_return_type:
            return False

        if not BuiltinTypeRegistry.is_builtin_type(previous_return_type):
            return False

        if not BuiltinTypeRegistry.has_method(
            previous_return_type,
            method_name
        ):
            return False

        call_model.update({
            "classification": "builtin_type_method",
            "resolved": True,
            "target_id": f"builtin_type:{previous_return_type}.{method_name}",
            "candidate_targets": [],
            "receiver_type": previous_return_type,
            "receiver_type_id": f"builtin_type:{previous_return_type}",
            "chained_receiver": receiver,
            "base_receiver": base_receiver,
            "base_receiver_type": base_type,
            "base_receiver_type_id": base_type_id,
            "previous_method": previous_method,
            "previous_return_type": previous_return_type,
            "inferred_from_chained_call": True
        })

        return True

    def _infer_receiver_type(
        self,
        receiver: str,
        callable_model: dict = None,
        class_model: dict = None
    ):
        """
        Infers the type of a receiver expression.

        Supported examples:
        name            -> from parameter annotation
        active_users    -> from local variable assignment
        self.roles      -> from instance attributes
        self.repository -> from instance attributes
        """

        if not receiver:
            return None

        # 1. self.attribute
        if receiver.startswith("self.") and class_model is not None:
            for attribute in class_model.get("instance_attributes", []):
                if attribute.get("full_name") == receiver:
                    receiver_type = (
                        attribute.get("resolved_type_qualified_name")
                        or attribute.get("assigned_type")
                    )

                    if receiver_type:
                        return {
                            "receiver_type": receiver_type,
                            "receiver_type_id": attribute.get("resolved_type_id")
                        }

        # 2. local variables
        if callable_model is not None:
            for variable in callable_model.get("local_variables", []):
                if variable.get("name") == receiver:
                    receiver_type = (
                        variable.get("resolved_type_qualified_name")
                        or variable.get("assigned_type")
                    )

                    if receiver_type:
                        return {
                            "receiver_type": receiver_type,
                            "receiver_type_id": variable.get("resolved_type_id")
                        }

        # 3. parameters
        if callable_model is not None:
            for parameter in callable_model.get("parameters", []):
                if isinstance(parameter, str):
                    continue

                if parameter.get("name") == receiver:
                    receiver_type = (
                        parameter.get("resolved_type_qualified_name")
                        or parameter.get("annotation")
                    )

                    if receiver_type:
                        return {
                            "receiver_type": receiver_type,
                            "receiver_type_id": parameter.get("resolved_type_id")
                        }

        return None

    def _resolve_cls_constructor_call(
        self,
        call_model: dict,
        callable_model: dict = None,
        class_model: dict = None
    ):
        """
        Resolves calls such as cls() inside class methods.

        Example:
        @classmethod
        def from_repository(cls, repository):
            service = cls()

        cls() should resolve to the current class.
        """

        if class_model is None:
            return False

        function_name = call_model.get("function") or call_model.get("name")

        if function_name != "cls":
            return False

        # Verify that the callable has a parameter named cls.
        has_cls_parameter = False

        if callable_model is not None:
            for parameter in callable_model.get("parameters", []):
                if isinstance(parameter, str):
                    if parameter == "cls":
                        has_cls_parameter = True
                        break
                else:
                    if parameter.get("name") == "cls":
                        has_cls_parameter = True
                        break

        if not has_cls_parameter:
            return False

        call_model.update({
            "kind": "constructor_call",
            "classification": "constructor",
            "resolved": True,
            "target_id": class_model.get("id"),
            "candidate_targets": [],
            "class_name": class_model.get("name"),
            "receiver_type": class_model.get("name"),
            "receiver_type_id": class_model.get("id"),
            "resolved_from_cls": True
        })

        return True

    def _apply_external_type_method(
        self,
        call_model: dict,
        receiver_type: str,
        receiver_type_id: str,
        method_name: str
    ):
        """
        Classifies a method call on a known external type.

        Example:
        self.logger.info(...)
        where self.logger: logging.Logger
        """

        if not ExternalTypeRegistry.is_external_type(receiver_type):
            return False

        if not ExternalTypeRegistry.has_method(receiver_type, method_name):
            return False

        call_model.update({
            "classification": "external_type_method",
            "resolved": True,
            "target_id": f"external_type:{receiver_type}.{method_name}",
            "candidate_targets": [],
            "receiver_type": receiver_type,
            "receiver_type_id": receiver_type_id or f"external_type:{receiver_type}"
        })

        return True

    def resolve_context_manager_variables(
        self,
        callable_model: dict
    ):
        """
        Extracts and resolves variables introduced by context managers.

        Example:
        with open(self.path, "w") as file:
            file.write(...)

        Produces:
        file -> io.TextIOWrapper
        """

        context_variables = []

        self._collect_context_manager_variables_from_body(
            callable_model.get("body", []),
            context_variables
        )

        callable_model["context_variables"] = context_variables

    def _collect_context_manager_variables_from_body(
        self,
        body_nodes: list,
        context_variables: list
    ):
        """
        Recursively collects context manager variables from body nodes.
        """

        for node in body_nodes:
            if node.get("type") == "control_structure" and node.get("control_type") == "with":
                for item in node.get("items", []):
                    optional_var = item.get("optional_vars")
                    context_expr = item.get("context_expr")

                    if not optional_var or not context_expr:
                        continue

                    context_variable = {
                        "name": optional_var,
                        "assigned_value": context_expr,
                        "assigned_type": context_expr,
                        "line": node.get("line_start"),
                        "resolved_type_id": None,
                        "resolved_type_qualified_name": None,
                        "type_resolution": None,
                        "resolved_from_context_manager": True
                    }

                    external_return_type = ExternalTypeRegistry.get_factory_return_type(
                        context_expr
                    )

                    if external_return_type:
                        context_variable["resolved_type_id"] = (
                            f"external_type:{external_return_type}"
                        )
                        context_variable["resolved_type_qualified_name"] = (
                            external_return_type
                        )
                        context_variable["type_resolution"] = "external_type"
                        context_variable["external_factory"] = context_expr

                    context_variables.append(context_variable)

            # Recursively inspect nested bodies.
            for child_key in ["body", "orelse", "handlers", "finalbody"]:
                child_nodes = node.get(child_key, [])

                if isinstance(child_nodes, list):
                    for child in child_nodes:
                        if child_key == "handlers":
                            self._collect_context_manager_variables_from_body(
                                child.get("body", []),
                                context_variables
                            )
                        else:
                            if isinstance(child, dict):
                                self._collect_context_manager_variables_from_body(
                                    [child],
                                    context_variables
                                )

    def _resolve_context_variable_method_call(
        self,
        call_model: dict,
        receiver: str,
        method_name: str,
        callable_model: dict
    ):
        """
        Resolves method calls on variables introduced by context managers.

        Example:
        with open(...) as file:
            file.write(...)

        file.write -> io.TextIOWrapper.write
        """

        for context_variable in callable_model.get("context_variables", []):
            if context_variable.get("name") != receiver:
                continue

            receiver_type = (
                context_variable.get("resolved_type_qualified_name")
                or context_variable.get("assigned_type")
            )

            receiver_type_id = context_variable.get("resolved_type_id")

            if not receiver_type:
                return False

            if self._apply_external_type_method(
                call_model,
                receiver_type=receiver_type,
                receiver_type_id=receiver_type_id,
                method_name=method_name
            ):
                call_model["resolved_from_context_manager"] = True
                call_model["context_variable"] = receiver
                call_model["context_factory"] = context_variable.get(
                    "external_factory"
                )
                return True

            call_model.update({
                "classification": "unresolved_method_on_context_variable",
                "resolved": False,
                "target_id": None,
                "candidate_targets": [],
                "receiver_type": receiver_type,
                "receiver_type_id": receiver_type_id,
                "resolved_from_context_manager": True,
                "context_variable": receiver
            })
            return True

        return False
