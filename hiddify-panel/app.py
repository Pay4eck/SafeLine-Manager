#!/opt/hiddify-manager/.venv313/bin/python

if __name__ == "__main__":
    from pathlib import Path
    import sys

    # The installed Panel remains the compatibility runtime.  SafeLine owns a
    # thin presentation layer in the Manager root, one directory above here.
    manager_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(manager_root))

    import bjoern
    from safeline.branding import create_app

    bjoern.run(wsgi_app=create_app(), host="127.0.0.1", port=9000)
