import argparse
import sys

try:
    from backend.services.ollama_cli_service import (
        OllamaCliError,
        get_ollama_exe,
        get_ollama_model,
        query_ollama_cli,
    )
except ImportError:
    from services.ollama_cli_service import (
        OllamaCliError,
        get_ollama_exe,
        get_ollama_model,
        query_ollama_cli,
    )


EXIT_WORDS = {"sair", "exit", "quit", "q"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Chat local com Mistral usando 'ollama run' via subprocess."
    )
    parser.add_argument(
        "--model",
        default=get_ollama_model(),
        help="Modelo Ollama usado no chat.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Timeout de cada resposta em segundos.",
    )
    parser.add_argument(
        "--history-turns",
        type=int,
        default=4,
        help="Quantidade de turnos anteriores mantidos no prompt.",
    )
    return parser.parse_args()


def build_chat_prompt(history: list[tuple[str, str]], question: str) -> str:
    previous_turns = "\n".join(
        f"Usuario: {user_text}\nMistral: {assistant_text}"
        for user_text, assistant_text in history
    )

    prompt = (
        "Voce e um assistente medico local para um prototipo IoT. "
        "Responda em portugues do Brasil, com objetividade e seguranca. "
        "Nao invente diagnosticos e oriente procurar atendimento medico "
        "em sinais de gravidade.\n\n"
    )

    if previous_turns:
        prompt += f"Historico recente:\n{previous_turns}\n\n"

    return f"{prompt}Usuario: {question}\nMistral:"


def main() -> int:
    args = parse_args()
    history: list[tuple[str, str]] = []

    print(f"Chat Mistral via: {get_ollama_exe()} run {args.model}")
    print("Digite 'sair' para encerrar.")

    while True:
        try:
            question = input("Voce: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not question:
            continue

        if question.lower() in EXIT_WORDS:
            return 0

        prompt = build_chat_prompt(history, question)

        try:
            answer = query_ollama_cli(
                prompt,
                model=args.model,
                timeout_seconds=args.timeout,
            )
        except OllamaCliError as exc:
            print(f"Erro ao consultar Mistral: {exc}", file=sys.stderr)
            continue

        print(f"Mistral: {answer}")
        history.append((question, answer))
        if args.history_turns > 0:
            history = history[-args.history_turns :]


if __name__ == "__main__":
    raise SystemExit(main())
