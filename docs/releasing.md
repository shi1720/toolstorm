# Release procedure

A release should identify the exact source tested by CI and distribute installable artifacts from that source.

1. Update the version in `pyproject.toml`, `src/toolstorm/__init__.py`, and `package.json` (including the root entry in `package-lock.json`). Update tagged install commands and the changelog. The website reads its version from the package manifest; the demo reads the Python package version.
2. Run `python scripts/bundle_engine.py`. Commit the generated source bundle, catalog, and recorded example. CI rejects generated files that differ from the Python source and checks Python/website version agreement.
3. Run the Python suite, lint, type checks, cross-runtime comparison, and website build. Push the release source and require a green CI run, including fresh distribution installs and built-site browser tests.
4. Build the wheel and source distribution with `python -m build --outdir artifacts/python`. Run `python scripts/smoke_distribution.py artifacts/python` from a directory containing only the intended release artifacts. The script installs outside the checkout without runtime dependencies and checks the public CLI, package version, pytest entry-point metadata, and reference behavior.
5. Tag the verified commit, attach the wheel and source distribution to a GitHub release, and include SHA-256 checksums. Keep beta status until the API and usage evidence justify a stable release. This project is distributed through GitHub; it is not currently published to PyPI.
6. Publish the website from that same source. The current site uses Sites with its project recorded in `.openai/hosting.json`. Build and package the deployment output, push the exact source state to the Site's configured source repository, save a version with its full commit SHA, and deploy the saved version. Credentials belong in short-lived tool memory or per-command authentication, never in Git, configuration, logs, or archives.
7. Verify the public page, runtime startup, one failing policy, and the corrected policy. Check that the displayed release version matches the package. Retain the prior saved deployment version for rollback if the publication fails acceptance.

Do not reuse a tag for changed code. If an artifact has already been published, create a new version for corrections. Tests establish the documented behaviors; they do not establish production adoption or guarantee arbitrary agent safety.
