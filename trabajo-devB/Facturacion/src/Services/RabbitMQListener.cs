using System.Text;
using System.Text.Json;
using Facturacion.src.Data;
using Microsoft.EntityFrameworkCore.Metadata;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;

namespace Facturacion.src.Services
{
    public class RabbitMQListener : BackgroundService
    {
        private readonly ILogger<RabbitMQListener> _logger;
        private readonly FacturaDbContext _context;
        private IConnection _connection;
        private IModel _channel;

        public RabbitMQListener(ILogger<RabbitMQListener> logger,FacturaDbContext context)
        {
            _logger = logger;
            _context = context;

            var factory = new ConnectionFactory() { HostName = "localhost" };
            _connection = factory.CreateConnection();
            _channel = _connection.CreateModel();

            _channel.QueueDeclare(queue: "billing_queue",
                                 durable: true,
                                 exclusive: false,
                                 autoDelete: false,
                                 arguments: null);
        }

        protected override Task ExecuteAsync(CancellationToken stoppingToken)
        {
            var consumer = new EventingBasicConsumer(_channel);
            consumer.Received += (model, ea) =>
            {
                var body = ea.Body.ToArray();
                var message = Encoding.UTF8.GetString(body);
                _logger.LogInformation("Received message: {Message}", message);

                // Deserialize and process the billing logic
                try
                {
                    var order = JsonSerializer.Deserialize<BillingOrderDto>(message);
                    if (order != null)
                    {
                        var billing = new BillingRecord
                        {
                            OrderId = order.OrderId,
                            TotalAmount = order.TotalAmount,
                            CustomerId = order.CustomerId
                        };

                        _db.BillingRecords.Add(billing);
                        await _db.SaveChangesAsync(stoppingToken);

                        _logger.LogInformation("Billing saved for OrderId: {0}", order.OrderId);
                    }
                    _logger.LogInformation("Processed billing for OrderId: {0}", order?.OrderId);
                    _channel.BasicAck(deliveryTag: ea.DeliveryTag, multiple: false);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Billing processing failed");
                    // Optionally reject the message
                    _channel.BasicNack(ea.DeliveryTag, false, requeue: false);
                }
            };

            _channel.BasicConsume(queue: "billing_queue",
                                  autoAck: false,
                                  consumer: consumer);

            return Task.CompletedTask;
        }

        public override void Dispose()
        {
            _channel?.Close();
            _connection?.Close();
            base.Dispose();
        }
    }
}