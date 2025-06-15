using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace VideosMS.src.Data
{
    public class VideoDbContext
    {
        private readonly IMongoCollection<Video> _videos;

        public VideoDbContext(IConfiguration configuration)
        {
            var client = new MongoClient(config["MongoDb:ConnectionString"]);
            var database = client.GetDatabase(config["MongoDb:Database"]);
            _videos = database.GetCollection<Video>("Videos");
        }

        public IMongoCollection<Video> Videos => _videos;
    }
}