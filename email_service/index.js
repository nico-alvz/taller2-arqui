const express = require('express');
const app = express();
app.use(express.json());
app.post('/email/send', (req, res) => {
  res.json({detail: 'email queued'});
});
app.get('/healthz', (req, res) => {
  res.json({status: 'ok'});
});
app.listen(8003, '0.0.0.0');
