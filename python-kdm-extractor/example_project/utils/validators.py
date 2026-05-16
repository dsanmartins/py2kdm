def is_valid_name(name: str):
    if name is None:
        return False

    if len(name.strip()) == 0:
        return False

    return True


def is_valid_user_data(user_data: dict):
    required_fields = ["user_id", "name"]

    for field in required_fields:
        if field not in user_data:
            return False

    return is_valid_name(user_data.get("name"))


def normalize_name(name: str):
    return name.strip().title()


def validate_positive_id(user_id: int):
    if user_id <= 0:
        raise ValueError("The user id must be positive")

    return True
