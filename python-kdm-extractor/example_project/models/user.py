class BaseEntity:
    entity_type = "base"

    def to_dict(self):
        return {
            "entity_type": self.entity_type
        }


class User(BaseEntity):
    entity_type = "user"

    def __init__(self, user_id: int, name: str, active: bool = True):
        self.user_id = user_id
        self.name = name
        self.active = active
        self.roles = []
        self.pending_tasks = 0

    def add_role(self, role: str):
        if role not in self.roles:
            self.roles.append(role)

    def deactivate(self):
        self.active = False

    def has_role(self, role: str):
        return role in self.roles

    def to_dict(self):
        data = super().to_dict()
        data["user_id"] = self.user_id
        data["name"] = self.name
        data["active"] = self.active
        data["roles"] = self.roles
        return data
