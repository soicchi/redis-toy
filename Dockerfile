FROM --platform=linux/amd64 python:3.11.6 as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM --platform=linux/amd64 python:3.11.6-slim as runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
EXPOSE 3000
CMD ["python", "main.py"]