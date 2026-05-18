class ClassifierResolver:
    def __init__(self, root_package):
        self.root_package = root_package
        self.cache = {}

    def find(self, classifier_name: str):
        if classifier_name in self.cache:
            return self.cache[classifier_name]

        classifier = self._find_recursive(self.root_package, classifier_name)

        if classifier is None:
            raise ValueError(f"Classifier not found in KDM metamodel: {classifier_name}")

        self.cache[classifier_name] = classifier
        return classifier

    def _find_recursive(self, pkg, classifier_name: str):
        for classifier in pkg.eClassifiers:
            if classifier.name == classifier_name:
                return classifier

        for subpkg in pkg.eSubpackages:
            result = self._find_recursive(subpkg, classifier_name)
            if result is not None:
                return result

        return None
