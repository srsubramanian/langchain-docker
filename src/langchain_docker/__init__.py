def greet(name: str = "World") -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"


def main() -> None:
    """Entry point for the langchain-docker application."""
    print(greet())
    print("Welcome to LangChain Docker!")


if __name__ == "__main__":
    main()
