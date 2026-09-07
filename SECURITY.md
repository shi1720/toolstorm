# Security policy

The current supported development line is `0.1.x`.

Please use the repository's **Security → Report a vulnerability** page for a sensitive report. Include the affected version, a minimal local reproduction, the expected boundary, and the observed violation. Do not place real credentials, private traces, or exploit payloads against third-party systems in public issues.

Security-relevant boundaries include secret capture, arbitrary code execution from a cassette, live-tool fallback during replay, and contract false positives caused by inconsistent evidence.

ToolStorm is test instrumentation. It is not a process sandbox, network isolation layer, transaction manager, or production safety mechanism. Wrapped live tools still execute in capture mode unless a pre-call rule skips them. Use isolated fixtures and test credentials. Default redaction is not a complete secret or PII detector.

The hosted lab accepts only bounded built-in scenario configurations. It has no arbitrary-code endpoint or secret-bearing server environment. Its Python runtime is copied unmodified from a pinned npm dependency and served as same-origin assets in a browser worker. First-load availability still requires a connection to the deployed site.
