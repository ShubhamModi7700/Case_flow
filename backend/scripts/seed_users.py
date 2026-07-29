from app.seed import create_users


def main() -> None:
    print("Starting user seed...")

    create_users()

    print("User seed completed successfully.")


if __name__ == "__main__":
    main()