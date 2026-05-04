using MediatR;
using OrderService.Api.Models;

namespace OrderService.Api.Features.Orders;

public sealed record OrderPlacedEvent(
    Order Order,
    DateTimeOffset AcceptedAt) : INotification;
