import jingleplayer_gui_pyside6


def main():
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--build-smoke-test":
        from jingleplayer_build_smoke import run
        return run(sys.argv[2])
    return jingleplayer_gui_pyside6.main()


if __name__ == "__main__":
    raise SystemExit(main())
