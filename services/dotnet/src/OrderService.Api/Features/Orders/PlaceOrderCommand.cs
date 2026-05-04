using MediatR;
using OrderService.Api.Models;

namespace OrderService.Api.Features.Orders;

public sealed record PlaceOrderCommand(Order Order) : IRequest<PlaceOrderResult>;

public sealed record PlaceOrderResult(
    string OrderId,
    string Status,
    DateTimeOffset AcceptedAt);
