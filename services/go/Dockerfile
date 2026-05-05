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
FROM gcr.io/distroless/static-debian12 AS runtime
WORKDIR /app

COPY --from=build /app/server .

USER nonroot:nonroot
EXPOSE 8081
ENTRYPOINT ["/app/server"]
