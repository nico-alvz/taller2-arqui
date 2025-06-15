using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace Videos.src.Models
{
    public class Video
    {
        [BsonId]
        public int Id { get; set; }
        public string Titulo { get; set; }
        public string Descripcion { get; set; }
        public string Genero { get; set; }
        public bool Borrado { get; set; } = false;
    }
}