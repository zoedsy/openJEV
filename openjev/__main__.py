import argparse


def main():
    parser = argparse.ArgumentParser(description="openJEV · local typed AI decisions")
    commands = parser.add_subparsers(dest="command")
    serve = commands.add_parser("serve", help="Start the API and playground")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8766)
    commands.add_parser("download", help="Download and verify the pinned open model")
    args = parser.parse_args()
    if args.command == "download":
        from .config import Settings
        from .engine import LocalNLI
        engine = LocalNLI(Settings.from_env())
        print(f"Downloading {engine.model_id}@{engine.revision}", flush=True)
        engine.load()
        print("Model ready. Start with: python -m openjev serve", flush=True)
    else:
        import uvicorn
        print(f"\n  openJEV → http://{getattr(args, 'host', '127.0.0.1')}:{getattr(args, 'port', 8766)}\n", flush=True)
        uvicorn.run("openjev.app:create_app", factory=True,
                    host=getattr(args, "host", "127.0.0.1"), port=getattr(args, "port", 8766))


if __name__ == "__main__":
    main()
