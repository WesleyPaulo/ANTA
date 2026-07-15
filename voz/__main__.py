"""Entrypoint: `python -m voz` abre o instalador; `python -m voz run` roda o assistente."""
import sys


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        # TODO(claude-code): carregar config, montar Pipeline, iniciar loop de toggle
        print("runtime ainda nao implementado — ver voz/core/pipeline.py")
        return
    from voz.installer.app import main as installer
    installer()


if __name__ == "__main__":
    main()
