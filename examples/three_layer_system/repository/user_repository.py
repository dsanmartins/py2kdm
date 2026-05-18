import json
from pathlib import Path

from models.user import User


class RepositoryError(Exception):
    pass


class UserRepository:
    storage_file = "users.json"

    def __init__(self):
        self.users = []
        self.path = Path(self.storage_file)

    def save(self, user: User):
        if user is None:
            raise RepositoryError("Cannot save null user")

        self.users.append(user)
        self._write_to_disk(user)
        return True

    def find_by_id(self, user_id: int):
        for user in self.users:
            if user.user_id == user_id:
                return user

        return None

    def find_active_users(self):
        active_users = []

        for user in self.users:
            if user.active:
                active_users.append(user)
            else:
                continue

        return active_users

    def _write_to_disk(self, user: User):
        try:
            with open(self.path, "a", encoding="utf-8") as file:
                json.dump(user.to_dict(), file)
                file.write("\n")
        except OSError as error:
            raise RepositoryError(str(error))
        finally:
            print("Write operation finished")

    def count(self):
        return len(self.users)
