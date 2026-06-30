# Makefile for the LinkML target schema.
#
# Source of truth:  src/schemas/target_schema.yaml
# Generated artifacts (committed):
#   project/pydantic/target_schema.py          (pydantic v2 models)
#   project/jsonschema/target_schema.schema.json
#
# Requires the `linkml` package:  pip install -e ".[linkml]"

SCHEMA       := src/schemas/target_schema.yaml
PYDANTIC_OUT := project/pydantic/target_schema.py
JSONSCHEMA_OUT := project/jsonschema/target_schema.schema.json
EXAMPLES_OUT := examples/output

.PHONY: all gen gen-pydantic gen-json-schema lint test-examples test-pytest test clean

all: gen test

# ---- generation ---------------------------------------------------------
gen: gen-pydantic gen-json-schema  ## regenerate all artifacts from the schema

gen-pydantic: $(SCHEMA)  ## generate pydantic v2 models
	gen-pydantic $(SCHEMA) > $(PYDANTIC_OUT)

gen-json-schema: $(SCHEMA)  ## generate JSON Schema
	gen-json-schema --inline $(SCHEMA) > $(JSONSCHEMA_OUT)

# ---- validation ---------------------------------------------------------
lint: $(SCHEMA)  ## lint the schema itself
	linkml-lint $(SCHEMA)

test-examples: $(SCHEMA)  ## examples/valid must pass, examples/invalid must fail
	mkdir -p $(EXAMPLES_OUT)
	linkml-run-examples \
		--schema $(SCHEMA) \
		--input-directory examples/valid \
		--counter-example-input-directory examples/invalid \
		--output-directory $(EXAMPLES_OUT)

test-pytest:  ## run the pytest wrapper around example validation
	pytest tests/test_target_schema_examples.py -o addopts=""

test: lint test-examples test-pytest  ## run all schema checks

clean:
	rm -rf $(EXAMPLES_OUT)
