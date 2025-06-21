using System.ComponentModel.DataAnnotations;

namespace Facturacion.src.Models
{
    public class Factura
    {
        [Key]
        public int Id { get; set; }
        public string UserId { get; set; }
        public decimal Monto { get; set; }
        public string Estado { get; set; }
        public DateTime FechaEmision { get; set; } = DateTime.UtcNow;
        public DateTime FechaPago { get; set; }
        public bool Borrado { get; set; } = false;
    }
}