"""Compatibility entry point for the integrated pilot packager."""

import sys

if __name__ == "__main__":
    sys.dont_write_bytecode = True
    from build_recommendation_catalog import main

    sys.argv[1:1] = ["--site"]
    main()
