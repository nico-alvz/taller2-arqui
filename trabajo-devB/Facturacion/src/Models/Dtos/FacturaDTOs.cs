using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Facturacion.src.Models.Dtos
{
    public class CrearFacturaDTO
    {
        public string UserId { get; set; }
        public decimal Monto { get; set; }
        public string Estado { get; set; }
        public DateTime FechaEmision { get; set; } = DateTime.UtcNow;
        public DateTime FechaPago { get; set; }
    }

    public class EditarFacturaDTO
    {
        public string Estado { get; set; }
        public DateTime FechaPago { get; set; }
    }
}