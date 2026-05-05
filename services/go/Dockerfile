# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM golang:1.22-alpine AS build
WORKDIR /src

# Restore modules in a separate layer for cache efficiency
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-s -w" \
    -o /app/server \
    ./cmd/server

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM alpine:3.19 AS runtime
RUN apk add --no-cache wget ca-certificates && \
    addgroup -S app && adduser -S app -G app
WORKDIR /app

COPY --from=build /app/server .

USER app
EXPOSE 8081
ENTRYPOINT ["/app/server"]
