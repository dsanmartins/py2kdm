import logging
import json

from models.user import User
from repository.user_repository import UserRepository, RepositoryError
from utils.validators import (
    is_valid_user_data,
    normalize_name,
    validate_positive_id
)


class BaseService:
    service_kind = "base-service"

    def log_action(self, action: str):
        print(action)


class UserService(BaseService):
    service_kind = "user-service"

    def __init__(self):
        self.repository = UserRepository()
        self.logger = logging.getLogger("UserService")
        self.max_attempts = 3

    def create_user(self, user_data: dict):
        if not is_valid_user_data(user_data):
            raise ValueError("Invalid user data")

        validate_positive_id(user_data["user_id"])

        normalized_name = normalize_name(user_data["name"])

        user = User(
            user_data["user_id"],
            normalized_name,
            active=True
        )

        self.repository.save(user)
        self.log_action("User created")
        print(user.name)

        return user

    def process_users(self):
        active_users = self.repository.find_active_users()

        for user in active_users:
            if user.active:
                for role in user.roles:
                    if role == "admin":
                        self.logger.info("Admin user found")
                    else:
                        print(role)
            else:
                continue

        return active_users

    def retry_save(self, user: User):
        attempts = 0

        while attempts < self.max_attempts:
            try:
                self.repository.save(user)
                break
            except RepositoryError as error:
                self.logger.warning(str(error))
                attempts = attempts + 1
            finally:
                print("Retry cycle finished")

        return attempts

    def export_user(self, user: User):
        user_dict = user.to_dict()
        return json.dumps(user_dict)

    @staticmethod
    def build_guest_user():
        return User(0, "Guest", active=False)

    @classmethod
    def from_repository(cls, repository: UserRepository):
        service = cls()
        service.repository = repository
        return service
