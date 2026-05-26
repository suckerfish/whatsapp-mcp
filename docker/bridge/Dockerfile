# syntax=docker/dockerfile:1

# --- builder ---
FROM golang:1.24-alpine AS builder

RUN apk add --no-cache gcc musl-dev

WORKDIR /src
COPY whatsapp-bridge/go.mod whatsapp-bridge/go.sum ./
RUN go mod download

COPY whatsapp-bridge/ ./
ENV CGO_ENABLED=1
RUN go build -o /whatsapp-bridge .

# --- runtime ---
FROM alpine:latest

RUN apk add --no-cache ca-certificates sqlite-libs

WORKDIR /app
COPY --from=builder /whatsapp-bridge /app/whatsapp-bridge
COPY docker/bridge/healthcheck.sh /app/healthcheck.sh
RUN chmod +x /app/healthcheck.sh && mkdir -p /app/store

EXPOSE 8080

ENV WHATSAPP_BRIDGE_PORT=8080
ENV WHATSAPP_BRIDGE_BIND=0.0.0.0

ENTRYPOINT ["/app/whatsapp-bridge"]
