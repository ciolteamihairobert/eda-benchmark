# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS build
WORKDIR /src

# Restore dependencies in a separate layer for cache efficiency
COPY src/OrderService.Api/OrderService.Api.csproj src/OrderService.Api/
RUN dotnet restore src/OrderService.Api/OrderService.Api.csproj

COPY . .
RUN dotnet publish src/OrderService.Api/OrderService.Api.csproj \
    -c Release --no-restore -o /app/publish

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine AS runtime
WORKDIR /app

RUN addgroup -S app 2>/dev/null || true && adduser -S app -G app 2>/dev/null || true

COPY --from=build --chown=app:app /app/publish .

USER app
EXPOSE 8080
ENV ASPNETCORE_URLS=http://+:8080

ENTRYPOINT ["dotnet", "OrderService.Api.dll"]
