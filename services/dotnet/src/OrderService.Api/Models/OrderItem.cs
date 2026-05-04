using System.ComponentModel.DataAnnotations;

namespace OrderService.Api.Models;

public record OrderItem
{
    [Required]
    public string Sku { get; init; } = string.Empty;

    [Range(1, 1000)]
    public int Quantity { get; init; }

    [Range(0.01, 999999)]
    public decimal Price { get; init; }
}
