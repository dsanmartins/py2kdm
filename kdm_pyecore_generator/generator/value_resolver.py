class ValueResolver:
    def __init__(self, factory, code_model):
        self.factory = factory
        # Container where literal Value elements will be stored.  In earlier
        # versions this was always the project CodeModel, which polluted the
        # main project model with a synthetic CompilationUnit named
        # ``python_literal_values``.  The caller can now pass PythonBuiltins or
        # another external/helper CodeModel instead.
        self.code_model = code_model

        self.values_unit = None
        self.value_index = {}

    def resolve_value(self, raw_value):
        if raw_value is None:
            return None

        key = str(raw_value)

        if key in self.value_index:
            return self.value_index[key]

        unit = self._get_or_create_values_unit()

        value_element = self.factory.create_value(
            name=key,
            value=raw_value,
        )

        unit.codeElement.append(value_element)
        self.value_index[key] = value_element

        return value_element

    def _get_or_create_values_unit(self):
        if self.values_unit is not None:
            return self.values_unit

        self.values_unit = self.factory.create_compilation_unit(
            "python_literal_values"
        )
        self.code_model.codeElement.append(self.values_unit)

        return self.values_unit
