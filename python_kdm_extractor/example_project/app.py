from services.user_service import UserService


def main():
    service = UserService()

    user_data = {
        "user_id": 1,
        "name": " irene "
    }

    user = service.create_user(user_data)
    service.process_users()
    service.retry_save(user)

    exported = service.export_user(user)
    print(exported)


if __name__ == "__main__":
    main()
