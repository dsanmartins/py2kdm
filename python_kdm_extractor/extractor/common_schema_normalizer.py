import re
from typing import Any

from extractor.builtin_type_registry import BuiltinTypeRegistry
from extractor.external_type_registry import ExternalTypeRegistry


class CommonSchemaNormalizer:
    """
    Adds a Java-compatible common JSON view to the Python extractor output.

    The normalizer is intentionally additive: it keeps the original Python
    fields (qualified_name, line_start, type, inherits, instantiates, etc.) and
    adds the common fields consumed by a language-independent KDM generator:

        packages, externalTypes, qualifiedName, packageName, kind,
        lineStart, lineEnd, uses_type, creates, throws, reads, writes,
        extends, implements.
    """

    PRIMITIVE_TYPES = {
        "str", "int", "float", "bool", "list", "dict", "tuple", "set",
        "bytes", "NoneType", "object", "Exception", "RuntimeError",
        "ValueError", "KeyError", "TypeError", "NotImplementedError",
    }

    TYPE_ALIASES = {
        "str": "builtins.str",
        "int": "builtins.int",
        "float": "builtins.float",
        "bool": "builtins.bool",
        "list": "builtins.list",
        "dict": "builtins.dict",
        "tuple": "builtins.tuple",
        "set": "builtins.set",
        "bytes": "builtins.bytes",
        "NoneType": "builtins.NoneType",
        "object": "builtins.object",
        "Exception": "builtins.Exception",
        "RuntimeError": "builtins.RuntimeError",
        "ValueError": "builtins.ValueError",
        "KeyError": "builtins.KeyError",
        "TypeError": "builtins.TypeError",
        "AttributeError": "builtins.AttributeError",
        "FileNotFoundError": "builtins.FileNotFoundError",
        "KeyboardInterrupt": "builtins.KeyboardInterrupt",
        "TimeoutError": "builtins.TimeoutError",
        "OSError": "builtins.OSError",
        "NotImplementedError": "builtins.NotImplementedError",
        "None": "builtins.NoneType",
        "Any": "typing.Any",
        "Optional": "typing.Optional",
        "Callable": "typing.Callable",
        "Union": "typing.Union",
        "Final": "typing.Final",
        "Type": "typing.Type",
        "Dict": "typing.Dict",
        "List": "typing.List",
        "Set": "typing.Set",
        "Tuple": "typing.Tuple",
        "Protocol": "typing.Protocol",
        "ABC": "abc.ABC",
        "Enum": "enum.Enum",
        "Flag": "enum.Flag",
        "IntEnum": "enum.IntEnum",
    }

    INTERFACE_BASES = {
        "Protocol", "typing.Protocol", "ABC", "abc.ABC"
    }

    STOPWORDS = {
        "and", "or", "not", "in", "is", "None", "True", "False",
        "return", "raise", "if", "else", "for", "while", "with", "as",
        "try", "except", "finally", "pass", "break", "continue", "self",
        "new", "lambda",
    }

    # Names produced by the Python AST/value analyser. They describe syntax
    # nodes, not real datatypes. Keeping them in externalTypes pollutes the KDM
    # with pseudo classes such as BinOp, Await or ListComp.
    AST_PSEUDO_TYPES = {
        "AST", "Add", "And", "AnnAssign", "Assert", "Assign", "AsyncFor",
        "AsyncFunctionDef", "AsyncWith", "Attribute", "AugAssign", "Await",
        "BinOp", "BoolOp", "Break", "Call", "ClassDef", "Compare",
        "Constant", "Continue", "Del", "Delete", "Dict", "DictComp",
        "Div", "Ellipsis", "Eq", "ExceptHandler", "Expr", "Expression",
        "For", "FormattedValue", "FunctionDef", "GeneratorExp", "Global",
        "Gt", "GtE", "If", "IfExp", "Import", "ImportFrom", "In",
        "Invert", "Is", "IsNot", "JoinedStr", "Lambda", "List",
        "ListComp", "Load", "Lt", "LtE", "MatMult", "Mod", "Module",
        "Mult", "Name", "NamedExpr", "Nonlocal", "Not", "NotEq",
        "NotIn", "Or", "Pass", "Pow", "Raise", "Return", "Set",
        "SetComp", "Slice", "Starred", "Store", "Sub", "Subscript",
        "Try", "Tuple", "UAdd", "USub", "UnaryOp", "While", "With",
        "Yield", "YieldFrom", "unknown",
    }

    def normalize(self, project_model: dict) -> dict:
        project_model.setdefault("packages", [])
        project_model.setdefault("externalTypes", [])
        project_model.setdefault("relationships", [])
        project_model["commonSchemaVersion"] = "1.2"

        internal_types = self._collect_internal_types(project_model)
        self._internal_model_kinds = self._collect_internal_model_kinds(project_model)
        interface_names = self._detect_interfaces(project_model)

        self._normalize_files(project_model)
        self._normalize_hierarchical_elements(project_model, interface_names)
        self._normalize_flat_elements(project_model, interface_names)
        self._build_packages(project_model)
        self._add_common_relationships(project_model, internal_types, interface_names)
        self._filter_invalid_common_relationships(project_model)
        self._build_external_types(project_model, internal_types)
        self._add_safe_qualified_names(project_model)
        self._enrich_relationship_metadata(project_model)
        self._recalculate_summary(project_model)

        return project_model

    # ------------------------------------------------------------------
    # Files, packages and elements
    # ------------------------------------------------------------------

    def _normalize_files(self, project_model: dict):
        project_name = project_model.get("projectName")

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue

            qualified_name = file_model.get("qualified_name")
            package_name = qualified_name if str(file_model.get("path", "")).endswith("__init__.py") else self._package_from_qualified_name(qualified_name)

            file_model.setdefault("kind", file_model.get("type", "module"))
            file_model.setdefault("qualifiedName", qualified_name)
            file_model.setdefault("packageName", package_name or project_name)
            file_model.setdefault("lineStart", file_model.get("line_start"))
            file_model.setdefault("lineEnd", file_model.get("line_end"))

    def _normalize_hierarchical_elements(self, project_model: dict, interface_names: set[str]):
        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue

            for class_model in file_model.get("classes", []):
                qn = class_model.get("qualified_name")
                kind = "interface" if qn in interface_names else "class"
                class_model["kind"] = kind
                class_model["qualifiedName"] = qn
                class_model["packageName"] = self._package_from_qualified_name(qn)
                class_model["lineStart"] = class_model.get("line_start")
                class_model["lineEnd"] = class_model.get("line_end")
                class_model["extendsTypes"] = []
                class_model["implementsTypes"] = []

                # Normalize Python bases into extends/implements-like lists.
                for base in class_model.get("bases", []):
                    base_qn = self._resolve_type_name(base, project_model, file_model)
                    if self._is_interface_base(base, base_qn, interface_names):
                        class_model["implementsTypes"].append(base_qn)
                    elif base_qn:
                        class_model["extendsTypes"].append(base_qn)

                class_model["fields"] = self._deduplicate_fields(self._build_python_fields(class_model))

                for field in class_model["fields"]:
                    self._normalize_typed_node(field)

                for method in class_model.get("methods", []):
                    self._normalize_callable(method, project_model, file_model)

            for function in file_model.get("functions", []):
                self._normalize_callable(function, project_model, file_model)

    def _normalize_flat_elements(self, project_model: dict, interface_names: set[str]):
        for element in project_model.get("elements", []):
            element_type = element.get("type")
            qn = element.get("qualified_name")

            if element_type == "class" and qn in interface_names:
                kind = "interface"
            else:
                kind = element_type

            element.setdefault("kind", kind)
            element.setdefault("qualifiedName", qn)
            element.setdefault("lineStart", element.get("line_start"))
            element.setdefault("lineEnd", element.get("line_end"))

            package_name = self._package_from_qualified_name(qn)
            if package_name:
                element.setdefault("packageName", package_name)

    def _build_python_fields(self, class_model: dict) -> list[dict]:
        fields = []

        for attribute in class_model.get("attributes", []):
            assigned_type = attribute.get("annotation") or attribute.get("assigned_type")
            resolved_type = self._normalize_type_name(assigned_type)
            fields.append({
                "name": attribute.get("name"),
                "type": assigned_type,
                "kind": "class_attribute",
                "qualifiedName": f"{class_model.get('qualified_name')}.{attribute.get('name')}",
                "qualified_name": f"{class_model.get('qualified_name')}.{attribute.get('name')}",
                "modifiers": [],
                "annotations": [],
                "resolvedType": resolved_type,
                "resolvedRawType": self._raw_type(resolved_type),
                "resolvedTypeArguments": self._type_arguments(resolved_type),
                "lineStart": attribute.get("line"),
                "lineEnd": attribute.get("line"),
            })

        for attribute in class_model.get("instance_attributes", []):
            assigned_type = (
                attribute.get("annotation")
                or attribute.get("resolved_type_qualified_name")
                or attribute.get("assigned_type")
                or attribute.get("value_type")
            )
            resolved_type = self._normalize_type_name(assigned_type)
            fields.append({
                "name": attribute.get("name"),
                "type": assigned_type,
                "kind": "instance_attribute",
                "qualifiedName": f"{class_model.get('qualified_name')}.{attribute.get('name')}",
                "qualified_name": f"{class_model.get('qualified_name')}.{attribute.get('name')}",
                "fullName": attribute.get("full_name"),
                "modifiers": [],
                "annotations": [],
                "resolvedType": resolved_type,
                "resolvedRawType": self._raw_type(resolved_type),
                "resolvedTypeArguments": self._type_arguments(resolved_type),
                "lineStart": attribute.get("line"),
                "lineEnd": attribute.get("line"),
            })

        return fields

    def _deduplicate_fields(self, fields: list[dict]) -> list[dict]:
        """Keep one structural field per qualifiedName/safeQualifiedName.

        Multiple assignments to the same instance attribute are behavior and are
        already represented by writes relationships.  For KDM we only want one
        StorableUnit per field.
        """
        merged: dict[str, dict] = {}
        order: list[str] = []
        for field in fields or []:
            key = field.get("qualifiedName") or field.get("qualified_name") or field.get("name")
            if not key:
                continue
            if key not in merged:
                merged[key] = dict(field)
                order.append(key)
                continue
            current = merged[key]
            for attr in ("type", "resolvedType", "resolvedRawType", "fullName"):
                if not current.get(attr) and field.get(attr):
                    current[attr] = field.get(attr)
            if not current.get("resolvedTypeArguments") and field.get("resolvedTypeArguments"):
                current["resolvedTypeArguments"] = field.get("resolvedTypeArguments")
            start_values = [value for value in [current.get("lineStart"), field.get("lineStart")] if value is not None]
            end_values = [value for value in [current.get("lineEnd"), field.get("lineEnd")] if value is not None]
            if start_values:
                current["lineStart"] = min(start_values)
            if end_values:
                current["lineEnd"] = max(end_values)
        return [merged[key] for key in order]

    def _normalize_callable(self, callable_model: dict, project_model: dict, file_model: dict):
        callable_model["kind"] = callable_model.get("method_kind") or callable_model.get("type")
        callable_model["qualifiedName"] = callable_model.get("qualified_name")
        callable_model["lineStart"] = callable_model.get("line_start")
        callable_model["lineEnd"] = callable_model.get("line_end")
        callable_model["returnType"] = callable_model.get("return_annotation")
        callable_model["resolvedReturnType"] = self._normalize_type_name(callable_model.get("return_annotation"))
        callable_model["resolvedRawReturnType"] = self._raw_type(callable_model.get("resolvedReturnType"))
        callable_model["resolvedReturnTypeArguments"] = self._type_arguments(callable_model.get("resolvedReturnType"))

        signature_parts = []
        for param in callable_model.get("parameters", []):
            self._normalize_parameter(param, project_model, file_model)
            if param.get("name") not in {"self", "cls"}:
                signature_parts.append(param.get("resolvedRawType") or param.get("type") or param.get("name"))
        callable_model["signatureText"] = f"{callable_model.get('name')}({','.join(signature_parts)})"

        for local in callable_model.get("local_variables", []):
            self._normalize_local_variable(local, project_model, file_model)

    def _normalize_parameter(self, parameter: dict, project_model: dict = None, file_model: dict = None):
        type_name = parameter.get("annotation")
        resolved = self._resolve_type_name(type_name, project_model or {"files": []}, file_model) if type_name else None
        parameter.setdefault("type", type_name)
        parameter.setdefault("resolvedType", resolved)
        parameter.setdefault("resolvedRawType", self._raw_type(resolved))
        parameter.setdefault("resolvedTypeArguments", self._type_arguments(resolved))
        parameter.setdefault("lineStart", parameter.get("line"))
        parameter.setdefault("lineEnd", parameter.get("line"))

    def _normalize_local_variable(self, variable: dict, project_model: dict = None, file_model: dict = None):
        type_name = variable.get("annotation")
        resolved_id = str(variable.get("resolved_type_id") or "")
        resolved_qn = variable.get("resolved_type_qualified_name")
        # A resolved function/method target is not a data type.  Example:
        # normalized_name = normalize_name(...) resolves to the function
        # normalize_name, but the variable type is still unknown unless a return
        # annotation/factory return type is available.
        if not type_name and resolved_qn and not resolved_id.startswith(("function:", "method:", "module:", "project:")):
            type_name = resolved_qn
        if not type_name:
            type_name = variable.get("value_type")
        # assigned_type is reliable for constructors and literals, but for
        # method calls it may contain the callee name rather than the returned
        # datatype, e.g. self.repository.find_name_by_id.
        if not type_name and variable.get("value_kind") in {"object_creation", "literal"}:
            type_name = variable.get("assigned_type")
        resolved = self._resolve_type_name(type_name, project_model or {"files": []}, file_model) if type_name else None
        variable.setdefault("type", type_name)
        variable.setdefault("resolvedType", resolved)
        variable.setdefault("resolvedRawType", self._raw_type(resolved))
        variable.setdefault("resolvedTypeArguments", self._type_arguments(resolved))
        variable.setdefault("lineStart", variable.get("line"))
        variable.setdefault("lineEnd", variable.get("line"))

    def _normalize_typed_node(self, node: dict):
        resolved = self._normalize_type_name(node.get("resolvedType") or node.get("type"))
        node["resolvedType"] = resolved
        node["resolvedRawType"] = self._raw_type(resolved)
        node["resolvedTypeArguments"] = self._type_arguments(resolved)

    def _build_packages(self, project_model: dict):
        package_map: dict[str, dict] = {}
        project_name = project_model.get("projectName")

        def add_package(qualified_name: str):
            if not qualified_name:
                return
            qualified_name = str(qualified_name).strip()
            if not qualified_name:
                return
            parts = [part for part in qualified_name.split(".") if part]
            for index in range(1, len(parts) + 1):
                qn = ".".join(parts[:index])
                if qn in package_map:
                    continue
                package_map[qn] = {
                    "name": parts[index - 1],
                    "qualifiedName": qn,
                    "parent": ".".join(parts[:index - 1]) if index > 1 else None,
                }

        def canonical_import_package(import_model: dict) -> str | None:
            # Internal imports may be written as services.user_service, mape.utils, etc.
            # Keep only the project-qualified/canonical module package so KDM does not
            # receive duplicate package trees.
            if import_model.get("classification") == "internal":
                return import_model.get("resolved_module_qualified_name") or self._package_from_qualified_name(import_model.get("target_qualified_name"))
            return import_model.get("module")

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue
            add_package(file_model.get("packageName"))
            for import_model in file_model.get("imports", []):
                module = canonical_import_package(import_model)
                if module:
                    add_package(module)

        # Remove non-canonical internal aliases such as services.*, repository.*,
        # mape.* when the corresponding project-qualified package exists or when
        # the first segment is known as an internal top-level package.
        if project_name:
            canonical = set(package_map)
            internal_roots = {
                qn[len(project_name) + 1:].split(".", 1)[0]
                for qn in canonical
                if qn.startswith(f"{project_name}.") and qn != project_name
            }
            to_remove = []
            for qn in canonical:
                if qn == project_name or qn.startswith(f"{project_name}."):
                    continue
                if f"{project_name}.{qn}" in canonical or qn.split(".", 1)[0] in internal_roots:
                    to_remove.append(qn)
            for qn in to_remove:
                package_map.pop(qn, None)

        project_model["packages"] = sorted(package_map.values(), key=lambda item: item["qualifiedName"])

    def _recalculate_summary(self, project_model: dict):
        """Refresh summary after common-schema normalization.

        The legacy summary is often computed before new relationships/packages
        are added.  Recomputing here keeps diagnostics consistent with the JSON
        actually consumed by the KDM generator.
        """
        summary = dict(project_model.get("summary") or {})
        relationships = project_model.get("relationships", []) or []
        elements = project_model.get("elements", []) or []
        summary["packages"] = len(project_model.get("packages", []) or [])
        summary["externalTypes"] = len(project_model.get("externalTypes", []) or [])
        summary["elements"] = len(elements)
        summary["relationships"] = len(relationships)

        by_type: dict[str, int] = {}
        for rel in relationships:
            rel_type = rel.get("type") or "unknown"
            by_type[rel_type] = by_type.get(rel_type, 0) + 1
        summary["relationshipsByType"] = dict(sorted(by_type.items()))

        by_kind: dict[str, int] = {}
        for element in elements:
            kind = element.get("kind") or element.get("type") or "unknown"
            by_kind[kind] = by_kind.get(kind, 0) + 1
        summary["elementsByKind"] = dict(sorted(by_kind.items()))

        project_model["summary"] = summary

    # ------------------------------------------------------------------
    # Safe identifiers and relationship metadata
    # ------------------------------------------------------------------

    def _add_safe_qualified_names(self, project_model: dict):
        """Add safeQualifiedName aliases without changing qualifiedName.

        Python modules may come from files such as ``hierarchical-cruise-control.py``.
        That name is valid as JSON text but awkward for XMI IDs and KDM references.
        The KDM generator can use safeQualifiedName whenever it needs a stable
        identifier, while preserving qualifiedName as the source-faithful name.
        """
        for package in project_model.get("packages", []) or []:
            qn = package.get("qualifiedName")
            if qn:
                package["safeQualifiedName"] = self._safe_name(qn)

        for external_type in project_model.get("externalTypes", []) or []:
            qn = external_type.get("qualifiedName")
            if qn:
                external_type["safeQualifiedName"] = self._safe_name(qn)

        for file_model in project_model.get("files", []) or []:
            self._set_safe_name(file_model)
            for class_model in file_model.get("classes", []) or []:
                self._set_safe_name(class_model)
                for field in class_model.get("fields", []) or []:
                    self._set_safe_name(field)
                for method in class_model.get("methods", []) or []:
                    self._set_safe_name(method)
                    for param in method.get("parameters", []) or []:
                        if method.get("qualifiedName") and param.get("name"):
                            param.setdefault("qualifiedName", f"{method.get('qualifiedName')}:parameter:{param.get('name')}")
                            param["safeQualifiedName"] = self._safe_name(param.get("qualifiedName"))
                    for local in method.get("local_variables", []) or []:
                        if method.get("qualifiedName") and local.get("name"):
                            local.setdefault("qualifiedName", f"{method.get('qualifiedName')}:local:{local.get('name')}")
                            local["safeQualifiedName"] = self._safe_name(local.get("qualifiedName"))
                for attr in class_model.get("attributes", []) or []:
                    if class_model.get("qualifiedName") and attr.get("name"):
                        attr.setdefault("qualifiedName", f"{class_model.get('qualifiedName')}.{attr.get('name')}")
                        attr["safeQualifiedName"] = self._safe_name(attr.get("qualifiedName"))
                for attr in class_model.get("instance_attributes", []) or []:
                    if class_model.get("qualifiedName") and attr.get("name"):
                        attr.setdefault("qualifiedName", f"{class_model.get('qualifiedName')}.{attr.get('name')}")
                        attr["safeQualifiedName"] = self._safe_name(attr.get("qualifiedName"))
            for function in file_model.get("functions", []) or []:
                self._set_safe_name(function)
                for param in function.get("parameters", []) or []:
                    if function.get("qualifiedName") and param.get("name"):
                        param.setdefault("qualifiedName", f"{function.get('qualifiedName')}:parameter:{param.get('name')}")
                        param["safeQualifiedName"] = self._safe_name(param.get("qualifiedName"))
                for local in function.get("local_variables", []) or []:
                    if function.get("qualifiedName") and local.get("name"):
                        local.setdefault("qualifiedName", f"{function.get('qualifiedName')}:local:{local.get('name')}")
                        local["safeQualifiedName"] = self._safe_name(local.get("qualifiedName"))

        for element in project_model.get("elements", []) or []:
            self._set_safe_name(element)

    def _set_safe_name(self, model: dict):
        qn = model.get("qualifiedName") or model.get("qualified_name")
        if qn:
            model.setdefault("qualifiedName", qn)
            model["safeQualifiedName"] = self._safe_name(qn)

    def _safe_name(self, value: str | None) -> str | None:
        if not value:
            return None
        # Keep dots as namespace separators but normalize every unsafe segment.
        return ".".join(
            re.sub(r"[^A-Za-z0-9_]", "_", part)
            for part in str(value).split(".")
        )

    def _enrich_relationship_metadata(self, project_model: dict):
        """Fill sourceFile, line and safe endpoints when they can be inferred."""
        index = self._build_location_index(project_model)
        project_name = project_model.get("projectName")

        for rel in project_model.get("relationships", []) or []:
            source = rel.get("source")
            target = rel.get("target")
            source_info = index.get(source) or index.get(self._strip_model_prefix(source))
            target_info = index.get(target) or index.get(self._strip_model_prefix(target))

            if "sourceFile" not in rel:
                if source_info and source_info.get("sourceFile"):
                    rel["sourceFile"] = source_info.get("sourceFile")
                elif rel.get("type") == "contains" and target_info and target_info.get("sourceFile"):
                    rel["sourceFile"] = target_info.get("sourceFile")

            if "line" not in rel:
                if source_info and source_info.get("lineStart") is not None:
                    rel["line"] = source_info.get("lineStart")
                elif target_info and target_info.get("lineStart") is not None:
                    rel["line"] = target_info.get("lineStart")
                elif rel.get("type") == "contains" and target and str(target).startswith("module:"):
                    rel["line"] = 1

            if source:
                rel["safeSource"] = self._safe_relationship_endpoint(source, project_name)
            if target:
                rel["safeTarget"] = self._safe_relationship_endpoint(target, project_name)

    def _build_location_index(self, project_model: dict) -> dict:
        index = {}

        def add(keys, source_file=None, line_start=None, line_end=None):
            info = {"sourceFile": source_file, "lineStart": line_start, "lineEnd": line_end}
            for key in keys:
                if not key:
                    continue
                previous = index.get(key)
                if not previous:
                    index[key] = info
                    continue
                # Do not let a flatter/less precise element record erase the
                # source file discovered from the hierarchical file model.
                merged = dict(previous)
                for field, value in info.items():
                    if merged.get(field) is None and value is not None:
                        merged[field] = value
                index[key] = merged

        for file_model in project_model.get("files", []) or []:
            if "error" in file_model:
                continue
            file_path = file_model.get("path")
            add(
                [file_model.get("id"), file_model.get("qualified_name"), file_model.get("qualifiedName")],
                file_path,
                file_model.get("lineStart") or file_model.get("line_start") or 1,
                file_model.get("lineEnd") or file_model.get("line_end"),
            )
            for import_model in file_model.get("imports", []) or []:
                pass
            for class_model in file_model.get("classes", []) or []:
                add(
                    [class_model.get("id"), class_model.get("qualified_name"), class_model.get("qualifiedName")],
                    file_path,
                    class_model.get("lineStart") or class_model.get("line_start"),
                    class_model.get("lineEnd") or class_model.get("line_end"),
                )
                for field in class_model.get("fields", []) or []:
                    add(
                        [field.get("id"), field.get("qualified_name"), field.get("qualifiedName")],
                        file_path,
                        field.get("lineStart") or field.get("line_start"),
                        field.get("lineEnd") or field.get("line_end"),
                    )
                for method in class_model.get("methods", []) or []:
                    add(
                        [method.get("id"), method.get("qualified_name"), method.get("qualifiedName")],
                        file_path,
                        method.get("lineStart") or method.get("line_start"),
                        method.get("lineEnd") or method.get("line_end"),
                    )
                    for param in method.get("parameters", []) or []:
                        add(
                            [param.get("qualifiedName"), f"{method.get('qualifiedName')}:parameter:{param.get('name')}"],
                            file_path,
                            param.get("lineStart") or param.get("line"),
                            param.get("lineEnd") or param.get("line"),
                        )
                    for local in method.get("local_variables", []) or []:
                        add(
                            [local.get("qualifiedName"), f"{method.get('qualifiedName')}:local:{local.get('name')}"] ,
                            file_path,
                            local.get("lineStart") or local.get("line"),
                            local.get("lineEnd") or local.get("line"),
                        )
            for function in file_model.get("functions", []) or []:
                add(
                    [function.get("id"), function.get("qualified_name"), function.get("qualifiedName")],
                    file_path,
                    function.get("lineStart") or function.get("line_start"),
                    function.get("lineEnd") or function.get("line_end"),
                )
                for param in function.get("parameters", []) or []:
                    add(
                        [param.get("qualifiedName"), f"{function.get('qualifiedName')}:parameter:{param.get('name')}"],
                        file_path,
                        param.get("lineStart") or param.get("line"),
                        param.get("lineEnd") or param.get("line"),
                    )
                for local in function.get("local_variables", []) or []:
                    add(
                        [local.get("qualifiedName"), f"{function.get('qualifiedName')}:local:{local.get('name')}"] ,
                        file_path,
                        local.get("lineStart") or local.get("line"),
                        local.get("lineEnd") or local.get("line"),
                    )

        for element in project_model.get("elements", []) or []:
            add(
                [element.get("id"), element.get("qualified_name"), element.get("qualifiedName")],
                element.get("sourceFile") or element.get("source_file"),
                element.get("lineStart") or element.get("line_start"),
                element.get("lineEnd") or element.get("line_end"),
            )
        return index

    def _strip_model_prefix(self, value: str | None) -> str | None:
        if not value or ":" not in str(value):
            return value
        prefix, rest = str(value).split(":", 1)
        if prefix in {"project", "module", "class", "function", "method", "field"}:
            return rest
        if prefix in {"class_or_external", "external"}:
            return rest
        return value

    def _safe_relationship_endpoint(self, endpoint: str, project_name: str | None) -> str:
        if endpoint is None:
            return None
        prefix = None
        value = str(endpoint)
        if ":" in value:
            possible_prefix, rest = value.split(":", 1)
            if possible_prefix in {"project", "module", "class", "function", "method", "field", "external", "unresolved", "class_or_external", "builtin", "builtin_type"}:
                prefix = possible_prefix
                value = rest
        safe = self._safe_name(value)
        return f"{prefix}:{safe}" if prefix else safe

    def _filter_invalid_common_relationships(self, project_model: dict):
        """Remove common relationships whose target is not a real type.

        Older normalizer runs may have produced uses_type edges from a local
        variable to a function returning an unknown value.  Those edges should
        not become KDM HasType relations.
        """
        filtered = []
        for rel in project_model.get("relationships", []) or []:
            if rel.get("type") == "uses_type":
                target = rel.get("target")
                if not self._is_valid_type(target):
                    continue
            filtered.append(rel)
        project_model["relationships"] = filtered

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    def _add_common_relationships(self, project_model: dict, internal_types: dict, interface_names: set[str]):
        existing = list(project_model.get("relationships", []))
        seen = {
            (rel.get("type"), rel.get("source"), rel.get("target"), rel.get("line"))
            for rel in existing
        }

        def add(rel_type: str, source: str, target: str, **metadata):
            if not source or not target:
                return
            key = (rel_type, source, target, metadata.get("line"))
            if key in seen:
                return
            seen.add(key)
            rel = {"type": rel_type, "source": source, "target": target}
            rel.update(metadata)
            project_model["relationships"].append(rel)

        # Legacy Python relationships (inherits, uses, instantiates) are kept for
        # backward compatibility. Equivalent common-schema relationships are
        # generated from the hierarchical model below to avoid ambiguous short
        # names and duplicated endpoints.

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue
            for class_model in file_model.get("classes", []):
                class_qn = class_model.get("qualified_name")

                for base in class_model.get("bases", []):
                    base_qn = self._resolve_type_name(base, project_model, file_model)
                    if self._is_interface_base(base, base_qn, interface_names):
                        add("implements", class_qn, base_qn, line=class_model.get("line_start"), base=base)
                    else:
                        add("extends", class_qn, base_qn, line=class_model.get("line_start"), base=base)

                for field in class_model.get("fields", []):
                    if self._is_valid_type(field.get("resolvedType")):
                        add("uses_type", field.get("qualifiedName"), field.get("resolvedType"), line=field.get("lineStart"), sourceFile=file_model.get("path"))

                for method in class_model.get("methods", []):
                    self._add_callable_common_relationships(add, method, class_model, file_model)

            for function in file_model.get("functions", []):
                self._add_callable_common_relationships(add, function, None, file_model)

    def _add_callable_common_relationships(self, add, callable_model: dict, class_model: dict | None, file_model: dict):
        callable_qn = callable_model.get("qualified_name")

        if self._is_valid_type(callable_model.get("resolvedReturnType")):
            add("uses_type", f"{callable_qn}:return", callable_model.get("resolvedReturnType"), line=callable_model.get("line_start"), sourceFile=file_model.get("path"))

        for param in callable_model.get("parameters", []):
            if param.get("name") in {"self", "cls"}:
                continue
            if self._is_valid_type(param.get("resolvedType")):
                add("uses_type", f"{callable_qn}:parameter:{param.get('name')}", param.get("resolvedType"), line=param.get("line"), sourceFile=file_model.get("path"))

        for local in callable_model.get("local_variables", []):
            if self._is_valid_type(local.get("resolvedType")):
                add("uses_type", f"{callable_qn}:local:{local.get('name')}", local.get("resolvedType"), line=local.get("line"), sourceFile=file_model.get("path"))

        variable_index = self._build_variable_index(callable_model, class_model)
        self._scan_body_for_data_relationships(add, callable_model.get("body", []), callable_qn, variable_index, file_model.get("path"))

    def _scan_body_for_data_relationships(self, add, body_nodes: list, callable_qn: str, variable_index: dict, source_file: str):
        for node in body_nodes:
            line = node.get("line_start")
            statement_type = node.get("statement_type")
            control_type = node.get("control_type")

            if statement_type in {"assignment", "annotated_assignment"}:
                targets = node.get("targets") or ([node.get("target")] if node.get("target") else [])
                for target in targets:
                    add("writes", callable_qn, self._resolve_variable_ref(target, variable_index, callable_qn), line=line, sourceFile=source_file)
                self._add_reads_from_text(add, callable_qn, node.get("value"), variable_index, line, source_file)

                if node.get("value_kind") == "object_creation":
                    target_type = self._constructor_target(node.get("value_call"), node.get("value_type"))
                    add("creates", callable_qn, target_type, line=line, sourceFile=source_file)

            elif statement_type == "raise":
                exception_type = self._exception_type_from_raise(node)
                add("throws", callable_qn, exception_type, line=line, sourceFile=source_file)
                add("creates", callable_qn, exception_type, line=line, sourceFile=source_file)

            elif statement_type == "return":
                self._add_reads_from_text(add, callable_qn, node.get("value"), variable_index, line, source_file)

            elif statement_type == "call":
                call = node.get("call") or node.get("value_call")
                if call and call.get("kind") == "constructor_call":
                    add("creates", callable_qn, self._constructor_target(call, None), line=line, sourceFile=source_file)
                self._add_reads_from_text(add, callable_qn, self._call_text(call), variable_index, line, source_file)

            if control_type:
                for text_field in ("condition", "iter", "target"):
                    self._add_reads_from_text(add, callable_qn, node.get(text_field), variable_index, line, source_file)

            # Calls nested in body model.
            for call_field in ("value_call", "call"):
                call = node.get(call_field)
                if call and call.get("kind") == "constructor_call":
                    add("creates", callable_qn, self._constructor_target(call, None), line=line, sourceFile=source_file)
            for call_list_field in ("value_calls", "condition_calls", "iter_calls", "exception_calls"):
                for call in node.get(call_list_field, []) or []:
                    if call.get("kind") == "constructor_call":
                        add("creates", callable_qn, self._constructor_target(call, None), line=call.get("line") or line, sourceFile=source_file)

            self._scan_body_for_data_relationships(add, node.get("body", []) or [], callable_qn, variable_index, source_file)
            self._scan_body_for_data_relationships(add, node.get("orelse", []) or [], callable_qn, variable_index, source_file)
            self._scan_body_for_data_relationships(add, node.get("finalbody", []) or [], callable_qn, variable_index, source_file)
            for handler in node.get("handlers", []) or []:
                exception = handler.get("exception")
                if exception:
                    add("uses_type", f"{callable_qn}:exception:{handler.get('line_start')}", self._normalize_type_name(exception), line=handler.get("line_start"), sourceFile=source_file)
                self._scan_body_for_data_relationships(add, handler.get("body", []) or [], callable_qn, variable_index, source_file)

    def _build_variable_index(self, callable_model: dict, class_model: dict | None) -> dict:
        index = {}
        callable_qn = callable_model.get("qualified_name")

        for param in callable_model.get("parameters", []):
            index[param.get("name")] = f"{callable_qn}:parameter:{param.get('name')}"
        for local in callable_model.get("local_variables", []):
            index[local.get("name")] = f"{callable_qn}:local:{local.get('name')}"
        if class_model:
            class_qn = class_model.get("qualified_name")
            for field in class_model.get("fields", []):
                index[field.get("name")] = field.get("qualifiedName")
                index[f"self.{field.get('name')}"] = field.get("qualifiedName")
        return index

    def _add_reads_from_text(self, add, callable_qn: str, text: Any, variable_index: dict, line: int | None, source_file: str):
        if not isinstance(text, str):
            return
        text = re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", "", text)
        for name in self._extract_identifiers(text):
            target = self._resolve_variable_ref(name, variable_index, callable_qn)
            if target:
                add("reads", callable_qn, target, line=line, sourceFile=source_file)

    def _extract_identifiers(self, text: str) -> list[str]:
        tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\b", text)
        result = []
        for token in tokens:
            if token in self.STOPWORDS:
                continue
            # For self.x.y keep self.x because x is the instance attribute.
            if token.startswith("self."):
                parts = token.split(".")
                if len(parts) >= 2:
                    result.append(".".join(parts[:2]))
                continue
            # For obj.method(...) only obj is a data read; the method name is
            # already captured by a calls relationship.
            result.append(token.split(".")[0])
        return result

    def _resolve_variable_ref(self, name: str, variable_index: dict, callable_qn: str):
        if not name:
            return None
        if name in variable_index:
            return variable_index[name]
        if name.startswith("self.") and name in variable_index:
            return variable_index[name]
        if name in self.STOPWORDS or name[0].isupper():
            return None
        return f"{callable_qn}:local_or_unresolved:{name}"

    # ------------------------------------------------------------------
    # External types
    # ------------------------------------------------------------------

    def _build_external_types(self, project_model: dict, internal_types: dict):
        external_map: dict[str, dict] = {}
        project_prefix = f"{project_model.get('projectName')}." if project_model.get("projectName") else None
        internal_top_packages = set()
        if project_model.get("projectName"):
            prefix = f"{project_model.get('projectName')}."
            for package in project_model.get("packages", []) or []:
                qn = package.get("qualifiedName")
                if qn and qn.startswith(prefix):
                    remainder = qn[len(prefix):].split(".", 1)[0]
                    if remainder:
                        internal_top_packages.add(remainder)
            for file_model in project_model.get("files", []) or []:
                qn = file_model.get("qualifiedName") or file_model.get("qualified_name")
                if qn and qn.startswith(prefix):
                    remainder = qn[len(prefix):].split(".", 1)[0]
                    if remainder:
                        internal_top_packages.add(remainder)

        def add_type(type_name: str):
            qn = self._normalize_type_name(type_name)
            if not qn or qn in internal_types or not self._is_valid_type(qn):
                return
            raw = self._raw_type(qn)
            if not raw or raw in internal_types or not self._is_valid_type(raw):
                return
            if project_prefix and raw.startswith(project_prefix):
                # Anything under the analysed project namespace is internal, even
                # when it is a function or module rather than a class.
                return
            if project_prefix and (project_prefix + raw in internal_types):
                return
            if project_prefix and raw.split(".", 1)[0] in internal_top_packages:
                return
            if ".constants." in raw or raw.endswith(".constants"):
                return
            if not self._is_plausible_external_type(raw):
                return
            external_map[raw] = {
                "name": raw.split(".")[-1],
                "qualifiedName": raw,
                "safeQualifiedName": self._safe_name(raw),
                "packageName": self._package_from_qualified_name(raw),
                "kind": self._infer_external_kind(raw),
                "external": True,
                "typeArguments": [],
            }

        for primitive in sorted(self.TYPE_ALIASES):
            add_type(primitive)

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue
            for import_model in file_model.get("imports", []):
                if import_model.get("classification") == "internal":
                    continue
                module = import_model.get("module")
                name = import_model.get("name")
                if name:
                    add_type(f"{module}.{name}" if module else name)
                elif module:
                    add_type(module)

            for class_model in file_model.get("classes", []):
                for base in class_model.get("bases", []):
                    add_type(base)
                for field in class_model.get("fields", []):
                    add_type(field.get("resolvedType"))
                for method in class_model.get("methods", []):
                    self._collect_callable_external_types(add_type, method)
            for function in file_model.get("functions", []):
                self._collect_callable_external_types(add_type, function)

        # Known external registry entries.
        for type_name in getattr(ExternalTypeRegistry, "EXTERNAL_TYPE_METHODS", {}).keys():
            add_type(type_name)
        for type_name in getattr(ExternalTypeRegistry, "FACTORY_RETURN_TYPES", {}).values():
            add_type(type_name)

        project_model["externalTypes"] = sorted(external_map.values(), key=lambda item: item["qualifiedName"])

    def _collect_callable_external_types(self, add_type, callable_model: dict):
        add_type(callable_model.get("resolvedReturnType"))
        for param in callable_model.get("parameters", []):
            add_type(param.get("resolvedType"))
        for local in callable_model.get("local_variables", []):
            add_type(local.get("resolvedType"))
        self._collect_body_external_types(add_type, callable_model.get("body", []))

    def _collect_body_external_types(self, add_type, body_nodes: list):
        for node in body_nodes:
            add_type(node.get("value_type"))
            if node.get("statement_type") == "raise":
                add_type(self._exception_type_from_raise(node))
            for call_field in ("value_call", "call"):
                call = node.get(call_field)
                if call and call.get("kind") == "constructor_call":
                    add_type(self._constructor_target(call, None))
            for call_list_field in ("value_calls", "condition_calls", "iter_calls", "exception_calls"):
                for call in node.get(call_list_field, []) or []:
                    if call.get("kind") == "constructor_call":
                        add_type(self._constructor_target(call, None))
            for handler in node.get("handlers", []) or []:
                add_type(handler.get("exception"))
                self._collect_body_external_types(add_type, handler.get("body", []) or [])
            self._collect_body_external_types(add_type, node.get("body", []) or [])
            self._collect_body_external_types(add_type, node.get("orelse", []) or [])
            self._collect_body_external_types(add_type, node.get("finalbody", []) or [])

    # ------------------------------------------------------------------
    # Interface detection and type helpers
    # ------------------------------------------------------------------

    def _collect_internal_types(self, project_model: dict) -> dict[str, dict]:
        internal = {}

        def add(qn, model):
            if not qn:
                return
            internal[qn] = model
            short = str(qn).split(".")[-1]
            if short:
                internal.setdefault(short, model)

        for file_model in project_model.get("files", []):
            add(file_model.get("qualified_name") or file_model.get("qualifiedName"), file_model)
            for class_model in file_model.get("classes", []):
                add(class_model.get("qualified_name") or class_model.get("qualifiedName"), class_model)
                for method in class_model.get("methods", []):
                    add(method.get("qualified_name") or method.get("qualifiedName"), method)
            for function in file_model.get("functions", []):
                add(function.get("qualified_name") or function.get("qualifiedName"), function)
        for element in project_model.get("elements", []):
            add(element.get("qualified_name") or element.get("qualifiedName"), element)
        return internal

    def _collect_internal_model_kinds(self, project_model: dict) -> dict[str, str]:
        kinds: dict[str, str] = {}

        def add(qn, model):
            if not qn:
                return
            kind = model.get("kind") or model.get("type") or model.get("method_kind")
            if kind:
                kinds[str(qn)] = kind

        for file_model in project_model.get("files", []):
            add(file_model.get("qualified_name") or file_model.get("qualifiedName"), file_model)
            for class_model in file_model.get("classes", []):
                add(class_model.get("qualified_name") or class_model.get("qualifiedName"), class_model)
                for method in class_model.get("methods", []):
                    add(method.get("qualified_name") or method.get("qualifiedName"), method)
            for function in file_model.get("functions", []):
                add(function.get("qualified_name") or function.get("qualifiedName"), function)
        for element in project_model.get("elements", []):
            add(element.get("qualified_name") or element.get("qualifiedName"), element)
        return kinds

    def _detect_interfaces(self, project_model: dict) -> set[str]:
        interfaces = set()
        for file_model in project_model.get("files", []):
            for class_model in file_model.get("classes", []):
                qn = class_model.get("qualified_name")
                bases = set(class_model.get("bases", []) or [])
                if bases & self.INTERFACE_BASES:
                    interfaces.add(qn)
                    continue
                methods = class_model.get("methods", [])
                if methods and all(self._is_abstract_like_method(method) for method in methods):
                    interfaces.add(qn)
        return interfaces

    def _is_abstract_like_method(self, method: dict) -> bool:
        if method.get("name") in {"__init__", "__repr__", "__str__"}:
            return False
        decorators = set(method.get("decorators", []) or [])
        if any(decorator.endswith("abstractmethod") for decorator in decorators):
            return True
        body = method.get("body", []) or []
        if not body:
            return True
        if len(body) == 1:
            node = body[0]
            if node.get("statement_type") in {"pass", "raise"}:
                exception = node.get("exception") or ""
                return node.get("statement_type") == "pass" or "NotImplemented" in exception
            if node.get("statement_type") == "expression" and node.get("expression") in {"...", "Ellipsis"}:
                return True
        return False

    def _is_interface_base(self, base: str, base_qn: str, interface_names: set[str]) -> bool:
        return base in self.INTERFACE_BASES or base_qn in interface_names or base in {qn.split(".")[-1] for qn in interface_names}

    def _resolve_type_name(self, type_name: str, project_model: dict, file_model: dict | None = None) -> str:
        if not type_name:
            return None
        normalized = self._normalize_type_name(type_name)
        if "." in normalized:
            return normalized
        # Search internal classes by short name.
        for current_file in project_model.get("files", []):
            for class_model in current_file.get("classes", []):
                if class_model.get("name") == normalized:
                    return class_model.get("qualified_name")
        return normalized

    def _normalize_type_name(self, type_name: str) -> str | None:
        if not type_name:
            return None
        type_name = str(type_name).strip()
        if not type_name:
            return None
        if type_name.startswith("builtin_type:"):
            type_name = type_name.split(":", 1)[1].split(".", 1)[0]
        elif type_name.startswith("builtin:"):
            type_name = type_name.split(":", 1)[1]
        elif type_name.startswith("class_or_external:"):
            type_name = type_name.split(":", 1)[1]
        # Normalize PEP 604 unions approximately by preserving display but normalizing parts.
        if "|" in type_name:
            parts = [self._normalize_type_name(part.strip()) or part.strip() for part in type_name.split("|")]
            return " | ".join(parts)
        # Normalize generics like dict[int, str].
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_\.]*)(?:\[(.*)\])$", type_name)
        if match:
            raw = self._normalize_type_name(match.group(1)) or match.group(1)
            args = [self._normalize_type_name(arg.strip()) or arg.strip() for arg in self._split_type_args(match.group(2))]
            return f"{raw}[{', '.join(args)}]"
        return self.TYPE_ALIASES.get(type_name, type_name)

    def _raw_type(self, type_name: str) -> str | None:
        if not type_name:
            return None
        return re.split(r"\[|\s\|\s", type_name, maxsplit=1)[0]

    def _type_arguments(self, type_name: str) -> list[str]:
        if not type_name or "[" not in type_name or not type_name.endswith("]"):
            return []
        inside = type_name[type_name.find("[") + 1:-1]
        return [arg.strip() for arg in self._split_type_args(inside) if arg.strip()]

    def _split_type_args(self, args: str) -> list[str]:
        result = []
        depth = 0
        current = []
        for char in args:
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
            if char == "," and depth == 0:
                result.append("".join(current))
                current = []
            else:
                current.append(char)
        if current:
            result.append("".join(current))
        return result

    def _is_valid_type(self, type_name: str) -> bool:
        if not type_name:
            return False
        raw = self._raw_type(type_name) or type_name
        raw = str(raw).strip()
        if not raw or raw in self.AST_PSEUDO_TYPES:
            return False
        if raw in {"None", "builtins.None", "builtins.NoneType"}:
            return False
        if ":" in raw:
            return False
        if raw.startswith("<") or raw.endswith(">"):
            return False
        internal_kind = getattr(self, "_internal_model_kinds", {}).get(raw)
        if internal_kind in {"function", "method", "module", "project", "statement", "control_structure", "exception_handler"}:
            return False
        return True

    def _package_from_qualified_name(self, qualified_name: str) -> str | None:
        if not qualified_name or "." not in qualified_name:
            return None
        return qualified_name.rsplit(".", 1)[0]

    def _is_plausible_external_type(self, qualified_name: str) -> bool:
        """Heuristic guard for externalTypes.

        Python imports may refer to modules or functions, not only classes.  For
        KDM externalTypes we keep builtins/typing aliases and names whose last
        segment looks like a type (CamelCase, ALLCAPS, or known exception).
        This avoids emitting external classes such as asyncio.create_task,
        dataclasses.field, Lambda or project helper functions.
        """
        if not qualified_name:
            return False
        raw = self._raw_type(qualified_name) or qualified_name
        last = raw.split(".")[-1]
        if raw.startswith("builtins.") or raw.startswith("typing."):
            return True
        if raw in {"abc.ABC", "enum.Enum", "enum.Flag", "enum.IntEnum"}:
            return True
        if last in {"ABC", "Protocol"}:
            return True
        if last.endswith("Error") or last.endswith("Exception") or last in {"KeyboardInterrupt", "SystemExit"}:
            return True
        if "." not in raw:
            return False
        if last.startswith("_"):
            return False
        return bool(re.match(r"^[A-Z][A-Za-z0-9_]*$", last) or re.match(r"^[A-Z0-9_]{2,}$", last))

    def _infer_external_kind(self, qualified_name: str) -> str:
        short = qualified_name.split(".")[-1]
        if short in {"Protocol"}:
            return "interface"
        if short in {"Deprecated"}:
            return "annotation"
        return "class"

    def _source_to_qualified_name(self, source: str, project_model: dict) -> str:
        return self._id_to_qualified_name(source, project_model) or source

    def _target_to_qualified_name(self, target: str, project_model: dict) -> str:
        if not target:
            return None
        target = target.replace("class_or_external:", "").replace("external:", "")
        resolved = self._id_to_qualified_name(target, project_model)
        if resolved:
            return resolved
        for file_model in project_model.get("files", []):
            for class_model in file_model.get("classes", []):
                if class_model.get("name") == target:
                    return class_model.get("qualified_name")
        return self._normalize_type_name(target)

    def _id_to_qualified_name(self, element_id: str, project_model: dict) -> str | None:
        if not element_id:
            return None
        for file_model in project_model.get("files", []):
            if file_model.get("id") == element_id:
                return file_model.get("qualified_name")
            for class_model in file_model.get("classes", []):
                if class_model.get("id") == element_id:
                    return class_model.get("qualified_name")
                for method in class_model.get("methods", []):
                    if method.get("id") == element_id:
                        return method.get("qualified_name")
            for function in file_model.get("functions", []):
                if function.get("id") == element_id:
                    return function.get("qualified_name")
        return None

    def _constructor_target(self, call: dict | None, fallback_type: str | None) -> str | None:
        if call:
            target = call.get("target_id") or call.get("resolved_target") or call.get("class_name") or call.get("name")
            if target:
                target = str(target).replace("class:", "").replace("external:", "")
                if target.endswith(".__init__"):
                    target = target[: -len(".__init__")]
                return self._normalize_type_name(target)
        return self._normalize_type_name(fallback_type)

    def _exception_type_from_raise(self, node: dict) -> str | None:
        exception = node.get("exception")
        if not exception:
            return None
        name = exception.split("(", 1)[0].strip()
        return self._normalize_type_name(name)

    def _expression_text(self, value) -> str:
        """Return a stable textual representation for values found in call arguments.

        Some Python body extractors store arguments as plain strings, while others
        store richer dictionaries such as {"name": "x"}, {"value": "x"}, or
        call/expression descriptors.  The common-schema normalizer only needs a
        readable string so it can scan reads without crashing.
        """
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, dict):
            for key in (
                "value",
                "name",
                "id",
                "qualifiedName",
                "qualified_name",
                "target_id",
                "resolved_target",
                "type",
                "kind",
            ):
                item = value.get(key)
                if item is not None and not isinstance(item, (dict, list, tuple)):
                    return str(item)
            if "call" in value:
                return self._call_text(value.get("call")) or ""
            if "value_call" in value:
                return self._call_text(value.get("value_call")) or ""
            return " ".join(
                self._expression_text(item)
                for item in value.values()
                if item is not None
            ).strip()
        if isinstance(value, (list, tuple, set)):
            return ", ".join(self._expression_text(item) for item in value)
        return str(value)

    def _call_text(self, call: dict | None) -> str | None:
        if not call:
            return None
        args = ", ".join(
            self._expression_text(arg)
            for arg in (call.get("arguments", []) or [])
        )
        scope = self._expression_text(call.get("scope")) if call.get("scope") is not None else None
        name = call.get("name") or call.get("method_name") or call.get("methodName") or call.get("target_id") or call.get("resolved_target") or "<call>"
        if scope:
            return f"{scope}.{name}({args})"
        return f"{name}({args})"
