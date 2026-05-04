namespace OrderService.Api.Fault;

public sealed class FaultSettings
{
    public int DelayMs { get; set; } = 0;
    public double FailRate { get; set; } = 0.0;
}
