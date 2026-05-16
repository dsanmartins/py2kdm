class KDMFactory:
    def __init__(self, resolver):
        self.resolver = resolver

        # KDM framework
        self.Segment = resolver.find("Segment")

        # Code package
        self.CodeModel = resolver.find("CodeModel")
        self.CompilationUnit = resolver.find("CompilationUnit")
        self.ClassUnit = resolver.find("ClassUnit")
        self.MethodUnit = resolver.find("MethodUnit")
        self.CallableUnit = resolver.find("CallableUnit")
        self.ParameterUnit = resolver.find("ParameterUnit")
        self.StorableUnit = resolver.find("StorableUnit")

        # Action package
        self.ActionElement = resolver.find("ActionElement")
        self.ActionRelationship = resolver.find("ActionRelationship")
        self.Calls = resolver.find("Calls")
        self.Creates = resolver.find("Creates")
        self.Reads = resolver.find("Reads")
        self.Writes = resolver.find("Writes")
        self.Throws = resolver.find("Throws")
        self.ExceptionFlow = resolver.find("ExceptionFlow")
        self.ExitFlow = resolver.find("ExitFlow")
        self.TryUnit = resolver.find("TryUnit")
        self.CatchUnit = resolver.find("CatchUnit")
        self.FinallyUnit = resolver.find("FinallyUnit")


        # Code relationships
        self.Extends = resolver.find("Extends")
        self.Imports = resolver.find("Imports")

        # KDM annotations
        self.Attribute = resolver.find("Attribute")

        # Source package
        self.SourceRef = resolver.find("SourceRef")
        self.SourceRegion = resolver.find("SourceRegion")

        self.HasType = resolver.find("HasType")
        self.Value = resolver.find("Value")
        self.HasValue = resolver.find("HasValue")

        self.BooleanType = resolver.find("BooleanType")
        self.IntegerType = resolver.find("IntegerType")
        self.StringType = resolver.find("StringType")
        self.FloatType = resolver.find("FloatType")
        self.VoidType = resolver.find("VoidType")
        self.Datatype = resolver.find("Datatype")
        self.InventoryModel = resolver.find("InventoryModel")
        self.SourceFile = resolver.find("SourceFile")


    # ------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------

    def has_feature(self, obj, feature_name: str):
        return feature_name in [
            feature.name for feature in obj.eClass.eAllStructuralFeatures()
        ]

    # ------------------------------------------------------------
    # KDM framework elements
    # ------------------------------------------------------------

    def create_segment(self, name: str):
        segment = self.Segment()
        segment.name = name
        return segment

    # ------------------------------------------------------------
    # Code model elements
    # ------------------------------------------------------------

    def create_code_model(self, name: str):
        model = self.CodeModel()
        model.name = name
        return model

    def create_compilation_unit(self, name: str):
        unit = self.CompilationUnit()
        unit.name = name
        return unit

    def create_class_unit(self, name: str):
        unit = self.ClassUnit()
        unit.name = name
        return unit

    def create_method_unit(self, name: str):
        unit = self.MethodUnit()
        unit.name = name
        return unit

    def create_callable_unit(self, name: str):
        unit = self.CallableUnit()
        unit.name = name
        return unit

    def create_parameter_unit(self, name: str):
        unit = self.ParameterUnit()
        unit.name = name
        return unit

    def create_storable_unit(self, name: str):
        unit = self.StorableUnit()
        unit.name = name
        return unit

    # ------------------------------------------------------------
    # Action elements and relations
    # ------------------------------------------------------------

    def create_action_element(self, name: str, kind: str = None):
        action = self.ActionElement()
        action.name = name

        if kind is not None and self.has_feature(action, "kind"):
            action.kind = kind

        return action

    def create_action_relationship(self, target, kind: str):
        relation = self.ActionRelationship()

        if not self.has_feature(relation, "to"):
            raise ValueError("ActionRelationship does not have feature 'to'.")

        relation.to = target

        if self.has_feature(relation, "kind"):
            relation.kind = kind
        else:
            self.add_attribute(relation, "kind", kind)

        return relation

    def create_calls_relation(self, target):
        relation = self.Calls()

        if not self.has_feature(relation, "to"):
            raise ValueError("Calls relation does not have feature 'to'.")

        relation.to = target
        return relation

    def create_creates_relation(self, target):
        relation = self.Creates()

        if not self.has_feature(relation, "to"):
            raise ValueError("Creates relation does not have feature 'to'.")

        relation.to = target
        return relation

    # ------------------------------------------------------------
    # Code relations
    # ------------------------------------------------------------

    def create_extends_relation(self, target):
        relation = self.Extends()

        if not self.has_feature(relation, "to"):
            raise ValueError("Extends relation does not have feature 'to'.")

        relation.to = target
        return relation

    def create_imports_relation(self, target):
        relation = self.Imports()

        if not self.has_feature(relation, "to"):
            raise ValueError("Imports relation does not have feature 'to'.")

        relation.to = target
        return relation

    # ------------------------------------------------------------
    # KDM attributes
    # ------------------------------------------------------------

    def create_attribute(self, tag: str, value):
        attribute = self.Attribute()
        attribute.tag = str(tag)

        if value is None:
            attribute.value = ""
        else:
            attribute.value = str(value)

        return attribute

    def add_attribute(self, element, tag: str, value):
        """
        Adds a kdm::Attribute to an element if the element supports attributes.
        None values are ignored.
        """

        if value is None:
            return

        if not self.has_feature(element, "attribute"):
            return

        attribute = self.create_attribute(tag, value)
        element.attribute.append(attribute)

    def add_attributes_from_dict(self, element, metadata: dict):
        """
        Adds several kdm::Attribute elements from a dictionary.
        Values equal to None are ignored.
        """

        for tag, value in metadata.items():
            self.add_attribute(element, tag, value)

    # ------------------------------------------------------------
    # Source traceability
    # ------------------------------------------------------------

    def create_source_ref(self, language: str = None, snippet: str = None):
        source_ref = self.SourceRef()

        if language is not None and self.has_feature(source_ref, "language"):
            source_ref.language = language

        if snippet is not None and self.has_feature(source_ref, "snippet"):
            source_ref.snippet = snippet

        return source_ref

    def create_source_region(
        self,
        path: str = None,
        language: str = None,
        start_line=None,
        end_line=None,
        start_position=None,
        end_position=None,
        file_item=None,
    ):
        region = self.SourceRegion()

        if path is not None and self.has_feature(region, "path"):
            region.path = path

        if file_item is not None and self.has_feature(region, "file"):
            region.file = file_item

        if language is not None and self.has_feature(region, "language"):
            region.language = language

        if start_line is not None and self.has_feature(region, "startLine"):
            region.startLine = int(start_line)

        if end_line is not None and self.has_feature(region, "endLine"):
            region.endLine = int(end_line)

        if start_position is not None and self.has_feature(region, "startPosition"):
            region.startPosition = int(start_position)

        if end_position is not None and self.has_feature(region, "endPosition"):
            region.endPosition = int(end_position)

        return region

    def add_source_region(
        self,
        element,
        path: str = None,
        language: str = None,
        start_line=None,
        end_line=None,
        start_position=None,
        end_position=None,
        snippet: str = None,
        file_item=None,
    ):
        if start_line is None and end_line is None and path is None and file_item is None:
            return

        if start_line is not None and end_line is None:
            end_line = start_line

        if end_line is not None and start_line is None:
            start_line = end_line

        if not self.has_feature(element, "source"):
            return

        source_ref = self.create_source_ref(
            language=language,
            snippet=snippet,
        )

        region = self.create_source_region(
            path=path,
            language=language,
            start_line=start_line,
            end_line=end_line,
            start_position=start_position,
            end_position=end_position,
            file_item=file_item,
        )

        source_ref.region.append(region)
        element.source.append(source_ref)

    def create_has_type_relation(self, target):
        relation = self.HasType()

        if not self.has_feature(relation, "to"):
            raise ValueError("HasType relation does not have feature 'to'.")

        relation.to = target
        return relation


    def create_boolean_type(self, name: str = "bool"):
        datatype = self.BooleanType()
        datatype.name = name
        return datatype


    def create_integer_type(self, name: str = "int"):
        datatype = self.IntegerType()
        datatype.name = name
        return datatype


    def create_string_type(self, name: str = "str"):
        datatype = self.StringType()
        datatype.name = name
        return datatype


    def create_float_type(self, name: str = "float"):
        datatype = self.FloatType()
        datatype.name = name
        return datatype


    def create_void_type(self, name: str = "None"):
        datatype = self.VoidType()
        datatype.name = name
        return datatype


    def create_generic_datatype(self, name: str):
        datatype = self.Datatype()
        datatype.name = name
        return datatype

    def create_inventory_model(self, name: str):
        model = self.InventoryModel()
        model.name = name
        return model


    def create_source_file(
        self,
        name: str,
        path: str,
        language: str = None,
        encoding: str = "UTF-8",
        format_: str = "text",
    ):
        source_file = self.SourceFile()
        source_file.name = name
        source_file.path = path

        if format_ is not None and self.has_feature(source_file, "format"):
            source_file.format = format_

        if language is not None and self.has_feature(source_file, "language"):
            source_file.language = language

        if encoding is not None and self.has_feature(source_file, "encoding"):
            source_file.encoding = encoding

        return source_file

    def create_value(self, name: str = None, value=None):
        value_element = self.Value()

        if name is not None and self.has_feature(value_element, "name"):
            value_element.name = str(name)

        if value is not None and self.has_feature(value_element, "value"):
            value_element.value = str(value)

        return value_element


    def create_has_value_relation(self, target):
        relation = self.HasValue()

        if not self.has_feature(relation, "to"):
            raise ValueError("HasValue relation does not have feature 'to'.")

        relation.to = target
        return relation

    def create_reads_relation(self, target):
        relation = self.Reads()

        if not self.has_feature(relation, "to"):
            raise ValueError("Reads relation does not have feature 'to'.")

        relation.to = target
        return relation


    def create_writes_relation(self, target):
        relation = self.Writes()

        if not self.has_feature(relation, "to"):
            raise ValueError("Writes relation does not have feature 'to'.")

        relation.to = target
        return relation


    def create_throws_relation(self, target):
        relation = self.Throws()

        if not self.has_feature(relation, "to"):
            raise ValueError("Throws relation does not have feature 'to'.")

        relation.to = target

        return relation
