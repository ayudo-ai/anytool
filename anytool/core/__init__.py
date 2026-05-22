"""
anytool.core — v2 engine.

Spec-first. Pass-through execution. Zero wrappers.

    from anytool.core import Engine

    engine = Engine(registry_path="registry/")
    result = await engine.execute("docusign_create_envelope", body={...}, auth_tokens=tokens)
"""
