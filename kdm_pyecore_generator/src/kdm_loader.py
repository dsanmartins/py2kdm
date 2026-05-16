from pyecore.resources import ResourceSet, URI


class KDMLoader:
    def __init__(self, ecore_path: str):
        self.ecore_path = ecore_path
        self.resource_set = ResourceSet()
        self.root_package = None

    def load(self):
        resource = self.resource_set.get_resource(URI(self.ecore_path))
        self.root_package = resource.contents[0]

        self.resource_set.metamodel_registry[self.root_package.nsURI] = self.root_package

        return self.resource_set, self.root_package
