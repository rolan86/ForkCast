#!/usr/bin/env bash
# Install OASIS engine dependencies for ForkCast.
#
# camel-oasis pins pytest==8.2.0 as a runtime dep, which conflicts with dev
# dependencies. We install it with --no-deps and then manually install its
# actual runtime requirements.
set -euo pipefail

echo "Installing camel-oasis (no-deps to avoid pytest conflict)..."
uv pip install --no-deps camel-oasis

echo "Installing camel-ai..."
uv pip install "camel-ai>=0.2.78"

echo "Installing remaining OASIS runtime dependencies..."
uv pip install igraph pandas neo4j cairocffi prance openapi-spec-validator \
    requests-oauthlib slack-sdk unstructured

echo ""
echo "Verifying OASIS import..."
if uv run python -c "import oasis; print('OK: oasis imported successfully')"; then
    echo "OASIS engine is ready."
else
    echo "ERROR: oasis import failed. You may need to install additional dependencies."
    exit 1
fi
