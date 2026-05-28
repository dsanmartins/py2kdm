class TypeResolver:
    def __init__(self, factory, id_index, external_builder, code_model, language="unknown"):
        self.factory = factory
        self.id_index = id_index
        self.external_builder = external_builder
        self.code_model = code_model
        self.language = str(language or "unknown").lower()

        self.builtin_types_unit = None
        self.type_index = {}

    def resolve_type(self, type_id: str, qualified_name: str = None):
        if not type_id:
            return None

        # 1. Internal type already created in the KDM structure.
        # Only valid if the target is a Datatype, e.g. ClassUnit.
        if type_id in self.id_index:
            candidate = self.id_index[type_id]

            if self._is_datatype(candidate):
                return candidate

            # If the resolved target is not a Datatype, do not use it
            # as the target of HasType.
            return None

        # 2. Builtin language types
        if type_id.startswith("builtin_type:"):
            type_name = type_id.replace("builtin_type:", "")
            return self.get_or_create_builtin_type(type_name)

        # 3. External types
        if type_id.startswith("external_type:"):
            external_name = type_id.replace("external_type:", "")
            return self.get_or_create_external_type(external_name)

        # 4. Fallback using qualified_name
        if qualified_name:
            return self.get_or_create_generic_type(qualified_name)

        return None

    def _is_datatype(self, kdm_element):
        """
        Returns True if the KDM element is an instance of Datatype
        or of a subclass of Datatype, such as ClassUnit, StringType,
        IntegerType, BooleanType, etc.
        """

        eclass = kdm_element.eClass

        if eclass.name == "Datatype":
            return True

        for super_type in eclass.eAllSuperTypes():
            if super_type.name == "Datatype":
                return True

        return False

    def _find_internal_type_by_name(self, type_name: str):
        if not type_name:
            return None

        raw_name = str(type_name).replace("external_type:", "").strip()

        while raw_name.endswith("[]"):
            raw_name = raw_name[:-2]

        if "<" in raw_name:
            raw_name = raw_name.split("<", 1)[0]

        raw_name = raw_name.rstrip(">")
        simple_name = raw_name.rsplit(".", 1)[-1]

        for candidate in self.id_index.values():
            if not self._is_datatype(candidate):
                continue

            candidate_name = getattr(candidate, "name", None)
            if candidate_name == raw_name or candidate_name == simple_name:
                return candidate

            for attribute in getattr(candidate, "attribute", []) or []:
                if getattr(attribute, "tag", None) not in {"qualified_name", "qualifiedName"}:
                    continue
                value = getattr(attribute, "value", None)
                if value == raw_name or (isinstance(value, str) and value.endswith(f".{simple_name}")):
                    return candidate

        return None

    def get_or_create_builtin_type(self, type_name: str):
        key = f"builtin_type:{type_name}"

        if key in self.type_index:
            return self.type_index[key]

        unit = self._get_or_create_builtin_types_unit()

        if type_name in {"bool", "Boolean", "boolean"}:
            datatype = self.factory.create_boolean_type("bool")
        elif type_name in {"int", "Integer", "integer"}:
            datatype = self.factory.create_integer_type("int")
        elif type_name in {"str", "String", "string"}:
            datatype = self.factory.create_string_type("str")
        elif type_name in {"float", "Float", "double"}:
            datatype = self.factory.create_float_type("float")
        elif type_name in {"None", "NoneType", "void"}:
            datatype = self.factory.create_void_type("None")
        else:
            datatype = self.factory.create_generic_datatype(type_name)

        unit.codeElement.append(datatype)
        self.type_index[key] = datatype
        return datatype

    def get_or_create_external_type(self, qualified_name: str):
        # Java extractors sometimes label unresolved project classes as
        # external_type:<SimpleName>. Before creating an external ClassUnit,
        # try to resolve the name against already-created internal ClassUnit,
        # InterfaceUnit or Datatype elements.
        if self.language == "java":
            internal = self._find_internal_type_by_name(qualified_name)
            if internal is not None:
                return internal

        parts = qualified_name.split(".")

        if len(parts) > 1:
            library_name = ".".join(parts[:-1]) if self.language == "java" else parts[0]
            class_name = parts[-1]
        else:
            library_name = "external"
            class_name = qualified_name

        return self.external_builder.get_or_create_external_class(
            library_name=library_name,
            class_name=class_name,
        )

    def get_or_create_generic_type(self, qualified_name: str):
        if self.language == "java":
            internal = self._find_internal_type_by_name(qualified_name)
            if internal is not None:
                return internal

        key = f"generic_type:{qualified_name}"

        if key in self.type_index:
            return self.type_index[key]

        unit = self._get_or_create_builtin_types_unit()

        type_name = qualified_name.split(".")[-1]
        datatype = self.factory.create_generic_datatype(type_name)

        unit.codeElement.append(datatype)
        self.type_index[key] = datatype
        return datatype

    def _get_or_create_builtin_types_unit(self):
        if self.builtin_types_unit is not None:
            return self.builtin_types_unit

        unit_name = "java_builtins_types" if self.language == "java" else "python_builtins_types"
        self.builtin_types_unit = self.factory.create_compilation_unit(unit_name)
        self.code_model.codeElement.append(self.builtin_types_unit)

        return self.builtin_types_unit
