using Facturacion.src.Data;
using Facturacion.src.Services;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

var connectionString = builder.Configuration.GetConnectionString("MariaDb");
builder.Services.AddDbContext<FacturaDbContext>(options =>
    options.UseMySql(connectionString, ServerVersion.AutoDetect(connectionString)));


builder.Services.AddControllers();
builder.Services.AddHostedService<RabbitMQListener>();

var app = builder.Build();
app.MapControllers();

app.UseHttpsRedirection();

app.Run();