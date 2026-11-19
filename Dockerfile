FROM python:3.12-slim
WORKDIR /app
COPY server.py system.py protocol.py ./
COPY web ./web
RUN useradd --create-home app && mkdir /app/data && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8000"]

