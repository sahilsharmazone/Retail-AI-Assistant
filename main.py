"""
main.py — CLI entry point for the Retail AI Assistant.

Interactive REPL where you type natural language queries and the agent
responds using structured tool calling.
"""

from dotenv import load_dotenv


def main():
    # Load environment variables
    load_dotenv()

    # Import after dotenv so env vars are available
    from agent import RetailAgent

    print("=" * 60)
    print("  🛍️  Retail AI Assistant")
    print("  Personal Shopper + Customer Support")
    print("=" * 60)
    print()
    print("Type your question below. Examples:")
    print('  • "I need a modest evening gown under $300 in size 8"')
    print('  • "Order O0044 — can I return this dress?"')
    print('  • Type "reset" to clear conversation history')
    print('  • Type "exit" or "quit" to leave')
    print()

    agent = RetailAgent()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye! 👋")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("\nGoodbye! 👋")
            break

        if user_input.lower() == "reset":
            agent.reset()
            print("🔄 Conversation reset.\n")
            continue

        print()  # spacing before tool calls
        try:
            response = agent.chat(user_input)
            print(f"\nAssistant: {response}\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()
