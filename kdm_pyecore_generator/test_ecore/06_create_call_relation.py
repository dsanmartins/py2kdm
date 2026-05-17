from pathlib import Path
from pyecore.resources import ResourceSet, URI


KDM_ECORE_PATH = "metamodels/kdm_1_4.ecore"
OUTPUT_PATH = "output/example_project_call_relation.kdm.xmi"


def find_classifier(pkg, classifier_name: str):
    for classifier in pkg.eClassifiers:
        if classifier.name == classifier_name:
            return classifier

    for subpkg in pkg.eSubpackages:
        result = find_classifier(subpkg, classifier_name)
        if result is not None:
            return result

    return None


def load_kdm_metamodel(ecore_path: str):
    rset = ResourceSet()
    resource = rset.get_resource(URI(ecore_path))
    kdm_root = resource.contents[0]
    rset.metamodel_registry[kdm_root.nsURI] = kdm_root
    return rset, kdm_root


def print_features(eclass):
    print(f"\nFeatures of {eclass.name}:")
    for feature in eclass.eAllStructuralFeatures():
        print("-", feature.name)


def has_feature(obj, feature_name: str):
    return feature_name in [f.name for f in obj.eClass.eAllStructuralFeatures()]


def main():
    Path("output").mkdir(exist_ok=True)

    rset, kdm_root = load_kdm_metamodel(KDM_ECORE_PATH)

    Segment = find_classifier(kdm_root, "Segment")
    CodeModel = find_classifier(kdm_root, "CodeModel")
    CompilationUnit = find_classifier(kdm_root, "CompilationUnit")
    ClassUnit = find_classifier(kdm_root, "ClassUnit")
    MethodUnit = find_classifier(kdm_root, "MethodUnit")
    CallableUnit = find_classifier(kdm_root, "CallableUnit")
    ParameterUnit = find_classifier(kdm_root, "ParameterUnit")
    StorableUnit = find_classifier(kdm_root, "StorableUnit")
    ActionElement = find_classifier(kdm_root, "ActionElement")
    Calls = find_classifier(kdm_root, "Calls")

    print_features(ActionElement)
    print_features(Calls)

    segment = Segment()
    segment.name = "example_project"

    code_model = CodeModel()
    code_model.name = "example_project_CodeModel"
    segment.model.append(code_model)

    compilation_unit = CompilationUnit()
    compilation_unit.name = "app.py"
    code_model.codeElement.append(compilation_unit)

    # Función global: main
    main_function = CallableUnit()
    main_function.name = "main"
    compilation_unit.codeElement.append(main_function)

    service_var = StorableUnit()
    service_var.name = "service"
    main_function.codeElement.append(service_var)

    # Clase: UserService
    class_unit = ClassUnit()
    class_unit.name = "UserService"
    compilation_unit.codeElement.append(class_unit)

    # Método destino: create_user
    method_unit = MethodUnit()
    method_unit.name = "create_user"
    class_unit.codeElement.append(method_unit)

    param_self = ParameterUnit()
    param_self.name = "self"
    method_unit.codeElement.append(param_self)

    param_user_data = ParameterUnit()
    param_user_data.name = "user_data"
    method_unit.codeElement.append(param_user_data)

    user_var = StorableUnit()
    user_var.name = "user"
    method_unit.codeElement.append(user_var)

    # Acción de llamada dentro de main
    call_action = ActionElement()
    call_action.name = "service.create_user"

    if has_feature(call_action, "kind"):
        call_action.kind = "method_call"

    main_function.codeElement.append(call_action)

    # Relación Calls desde ActionElement hacia MethodUnit
    calls_relation = Calls()

    if has_feature(calls_relation, "to"):
        calls_relation.to = method_unit
    else:
        raise ValueError("La clase Calls no tiene la referencia 'to'.")

    call_action.actionRelation.append(calls_relation)

    output_resource = rset.create_resource(URI(OUTPUT_PATH))
    output_resource.append(segment)
    output_resource.save()

    print(f"\nModelo KDM con ActionElement + Calls generado en: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
