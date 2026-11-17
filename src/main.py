import argparse
import sys

try:
    from config.config import load_config
except ImportError:
    from src.config.config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load node configuration from a YAML file.")
    parser.add_argument(
        "config",
        nargs="?",
        default="config.yaml",
        help="Path to the YAML configuration file (default: config.yaml)",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except (OSError, TypeError, ValueError) as exc:
        print(f"Error loading config: {exc}", file=sys.stderr)
        return 1

    print(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
