const express = require('express');
const amqp = require('amqplib');
const nodemailer = require('nodemailer');
const app = express();
app.use(express.json());

const transport = nodemailer.createTransport({
  host: process.env.SMTP_HOST,
  auth: { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS }
});

async function consume() {
  if (!process.env.AMQP_URL) return;
  const conn = await amqp.connect(process.env.AMQP_URL);
  const ch = await conn.createChannel();
  await ch.assertExchange('billing.events', 'fanout', { durable: false });
  const q = await ch.assertQueue('', { exclusive: true });
  await ch.bindQueue(q.queue, 'billing.events', '');
  ch.consume(q.queue, async msg => {
    const data = JSON.parse(msg.content.toString());
    await transport.sendMail({ to: data.email, subject: 'Invoice paid', text: 'Thanks for your payment' });
    ch.ack(msg);
  });
}
consume().catch(console.error);

app.post('/email/send', async (req, res) => {
  const { to, subject, text } = req.body;
  await transport.sendMail({ to, subject, text });
  res.json({ detail: 'email sent' });
});

app.get('/healthz', (req, res) => {
  res.json({ status: 'ok' });
});

app.listen(8003, '0.0.0.0');
