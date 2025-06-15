using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Facturacion.src.Models;
using Microsoft.EntityFrameworkCore;

namespace Facturacion.src.Data
{
    public class FacturaDbContext : DbContext
    {
        public FacturaDbContext(DbContextOptions<FacturaDbContext> options) : base(options) { }

        public DbSet<Factura> RegistroFactura { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            modelBuilder.Entity<Factura>().ToTable("Facturas");
        }
    }
}