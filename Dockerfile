FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN python -m ensurepip --upgrade \
    && python -m pip install --no-cache-dir "poetry>=2.2.1,<3"

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY app ./app
COPY scripts ./scripts

# Fail the image build immediately if a vertical slice was omitted from the
# Docker build context or an import path is broken. This catches the class of
# failure that previously only appeared after uvicorn started.
RUN poetry run python -m compileall -q app scripts \
    && poetry run python -c "import app.main; from app.domains.agents.repository import AgentRepository"

EXPOSE 8001
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
