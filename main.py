from core.runner import cli_run

if __name__ == "__main__":
    import sys, argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("src"); parser.add_argument("dst")
    parser.add_argument("-t", "--types", nargs="+", required=True)
    parser.add_argument("-r", "--recursive", action="store_true")
    parser.add_argument("--preserve", action="store_true", default=True)
    args = parser.parse_args()
    cli_run(args.src, args.dst, args.types, args.recursive, args.preserve)
