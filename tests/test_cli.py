from pathlib import Path

from ai_news_digest.cli import build_parser


def test_cli_parser_accepts_input_and_dry_run() -> None:
    parser = build_parser()

    args = parser.parse_args(["--input", "input/latest_digest.json", "--dry-run"])

    assert args.input == "input/latest_digest.json"
    assert args.dry_run is True
    assert args.mode == "render"


def test_cli_parser_accepts_api_mode() -> None:
    parser = build_parser()

    args = parser.parse_args(["--mode", "api", "--input", "input/generated.json"])

    assert args.mode == "api"
    assert args.input == "input/generated.json"
