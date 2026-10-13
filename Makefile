VENV ?= .venv
PY := $(VENV)/bin/python
HEAVY := ^(torch|transformers|sentence-transformers|langchain-huggingface|huggingface-hub)

.PHONY: venv test golden
venv:
	uv venv --python 3.11 $(VENV)
	grep -vE '$(HEAVY)' requirements.txt | grep -vE '^\s*(#|$$)' > $(VENV)/req-light.txt
	# pydantic 2.12.1이 의존하는 pydantic-core 2.41.3은 PyPI에서 yanked라 uv는 명시해야 설치한다 (pip은 그대로 설치됨)
	uv pip install --python $(PY) -r $(VENV)/req-light.txt -r requirements-dev.txt pydantic-core==2.41.3

test:
	PYTHONHASHSEED=0 $(PY) -m pytest

golden:
	PYTHONHASHSEED=0 UPDATE_GOLDEN=1 $(PY) -m pytest
