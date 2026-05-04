using System.ComponentModel.DataAnnotations;

namespace OrderService.Api.Models;

public record Order : IValidatableObject
{
    [Required]
    public string OrderId { get; init; } = string.Empty;

    [Required]
    public string CustomerId { get; init; } = string.Empty;

    [Required, MinLength(1)]
    public List<OrderItem> Items { get; init; } = [];

    public DateTimeOffset Timestamp { get; init; } = DateTimeOffset.UtcNow;

    public IEnumerable<ValidationResult> Validate(ValidationContext validationContext)
    {
        if (Items is { Count: 0 })
            yield return new ValidationResult(
                "Items must contain at least one item.",
                new[] { nameof(Items) });
    }
}
