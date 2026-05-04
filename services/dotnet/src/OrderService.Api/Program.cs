using System.ComponentModel.DataAnnotations;
using System.Net.Mime;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using MediatR;
using Prometheus;
using Serilog;
using Serilog.Events;
using Serilog.Formatting.Json;
using OrderService.Api.Fault;
using OrderService.Api.Features.Orders;
using OrderService.Api.Kafka;
using OrderService.Api.Metrics;
using OrderService.Api.Models;

Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Override("Microsoft", LogEventLevel.Warning)
    .Enrich.FromLogContext()
    .WriteTo.Console(new JsonFormatter())
    .CreateBootstrapLogger();

try
{
    var builder = WebApplication.CreateBuilder(args);

    builder.Host.UseSerilog((ctx, services, config) => config
        .ReadFrom.Configuration(ctx.Configuration)
        .ReadFrom.Services(services)
        .Enrich.FromLogContext()
        .WriteTo.Console(new JsonFormatter()));

    var kafkaSettings = builder.Configuration.GetSection("Kafka").Get<KafkaSettings>()
        ?? new KafkaSettings();
    var faultSettings = builder.Configuration.GetSection("Fault").Get<FaultSettings>()
        ?? new FaultSettings();

    builder.Services.AddSingleton(kafkaSettings);
    builder.Services.AddSingleton(faultSettings);

    builder.Services.AddMediatR(cfg =>
        cfg.RegisterServicesFromAssembly(typeof(Program).Assembly));

    builder.Services.AddSingleton<KafkaProducerService>();
    builder.Services.AddHostedService(sp => sp.GetRequiredService<KafkaProducerService>());
    builder.Services.AddSingleton<IKafkaProducerService>(sp =>
        sp.GetRequiredService<KafkaProducerService>());

    builder.Services.AddSingleton<KafkaConsumerService>();
    builder.Services.AddHostedService(sp => sp.GetRequiredService<KafkaConsumerService>());

    builder.Services.AddSingleton<IOrderMetrics, OrderMetrics>();
    builder.Services.AddProblemDetails();

    var app = builder.Build();

    app.UseExceptionHandler(exApp => exApp.Run(async ctx =>
    {
        ctx.Response.ContentType = MediaTypeNames.Application.Json;

        var feature = ctx.Features.Get<IExceptionHandlerFeature>();
        var ex = feature?.Error;

        (ctx.Response.StatusCode, var title) = ex switch
        {
            OrderProcessingException => (StatusCodes.Status422UnprocessableEntity, "Order processing failed"),
            _ => (StatusCodes.Status500InternalServerError, "An unexpected error occurred")
        };

        var pd = new ProblemDetails
        {
            Status = ctx.Response.StatusCode,
            Title = title,
            Detail = ex?.Message,
            Instance = ctx.Request.Path,
        };

        await ctx.Response.WriteAsJsonAsync(pd, ctx.RequestAborted);
    }));

    app.UseHttpMetrics();

    app.MapPost("/orders", async (Order order, IMediator mediator) =>
    {
        var validationCtx = new ValidationContext(order);
        var validationResults = new List<ValidationResult>();

        if (!Validator.TryValidateObject(order, validationCtx, validationResults, validateAllProperties: true))
        {
            var errors = validationResults
                .GroupBy(r => r.MemberNames.FirstOrDefault() ?? string.Empty)
                .ToDictionary(
                    g => g.Key,
                    g => g.Select(r => r.ErrorMessage ?? "Invalid value").ToArray());
            return Results.ValidationProblem(errors);
        }

        var itemErrors = new Dictionary<string, string[]>();
        for (var i = 0; i < order.Items.Count; i++)
        {
            var itemCtx = new ValidationContext(order.Items[i]);
            var itemResults = new List<ValidationResult>();
            if (!Validator.TryValidateObject(order.Items[i], itemCtx, itemResults, validateAllProperties: true))
            {
                foreach (var r in itemResults)
                    foreach (var member in r.MemberNames)
                        itemErrors[$"Items[{i}].{member}"] = [r.ErrorMessage ?? "Invalid value"];
            }
        }

        if (itemErrors.Count > 0)
            return Results.ValidationProblem(itemErrors);

        var result = await mediator.Send(new PlaceOrderCommand(order));
        return Results.Accepted($"/orders/{result.OrderId}", new { result.OrderId, result.Status });
    });

    app.MapGet("/health", () => Results.Ok(new
    {
        status = "ok",
        timestamp = DateTimeOffset.UtcNow,
    }));

    app.MapMetrics();

    await app.RunAsync();
    return 0;
}
catch (Exception ex) when (ex is not OperationCanceledException
                        && ex.GetType().Name != "StopTheHostException")
{
    Log.Fatal(ex, "Application terminated unexpectedly");
    return 1;
}
finally
{
    await Log.CloseAndFlushAsync();
}
