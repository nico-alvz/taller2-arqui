'use strict';
// EmailService: escucha eventos de facturas y envía correos automáticamente

const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const amqp = require('amqplib');
const nodemailer = require('nodemailer');
const path = require('path');
require('dotenv').config();

// Cargar proto
const PROTO_PATH = path.join(__dirname, 'proto', 'email.proto');
const packageDef = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true
});
const emailProto = grpc.loadPackageDefinition(packageDef).email;

// Configurar transporter de nodemailer
const transporter = nodemailer.createTransport({
  host: process.env.SMTP_HOST,
  port: parseInt(process.env.SMTP_PORT),
  secure: false,
  auth: {
    user: process.env.SMTP_USER,
    pass: process.env.SMTP_PASS
  }
});

// Implementación del RPC SendInvoiceUpdate
async function sendInvoiceUpdate(call, callback) {
  const { invoice_id, email, status } = call.request;
  // Construir cuerpo del correo
  const mailOptions = {
    from: process.env.SMTP_USER,
    to: email,
    subject: `Actualización de factura ${invoice_id}`,
    text: `Tu factura ${invoice_id} ahora tiene el estado: ${status}`
  };
  try {
    await transporter.sendMail(mailOptions);
    console.log(`Correo enviado a ${email} sobre factura ${invoice_id}`);
    callback(null, {}); // Empty
  } catch (err) {
    console.error('Error enviando correo:', err);
    callback({ code: grpc.status.INTERNAL, message: 'Error interno al enviar correo' });
  }
}

// Iniciar servidor gRPC
function startGrpcServer() {
  const server = new grpc.Server();
  server.addService(emailProto.EmailService.service, { SendInvoiceUpdate: sendInvoiceUpdate });
  const port = process.env.GRPC_PORT || '50053';
  server.bindAsync(`0.0.0.0:${port}`, grpc.ServerCredentials.createInsecure(), () => {
    server.start();
    console.log(`EmailService gRPC escuchando en puerto ${port}`);
  });
}

// Consumidor de RabbitMQ para eventos de facturas
async function startRabbitConsumer() {
  const conn = await amqp.connect(process.env.AMQP_URL);
  const ch = await conn.createChannel();
  const exchange = 'invoices';
  await ch.assertExchange(exchange, 'fanout', { durable: true });
  const q = await ch.assertQueue('', { exclusive: true });
  await ch.bindQueue(q.queue, exchange, '');
  console.log('Esperando eventos de facturas en RabbitMQ...');
  ch.consume(q.queue, async (msg) => {
    if (msg !== null) {
      try {
        const event = JSON.parse(msg.content.toString());
        if (event.type === 'invoice.updated') {
          // Llamar RPC internamente
          const client = new emailProto.EmailService(
            `localhost:${process.env.GRPC_PORT}`, grpc.credentials.createInsecure()
          );
          client.SendInvoiceUpdate({
            invoice_id: event.id,
            email: event.user_email,
            status: event.status
          }, (err) => {
            if (err) console.error('RPC error:', err);
            else ch.ack(msg);
          });
        } else {
          ch.ack(msg);
        }
      } catch (e) {
        console.error('Error procesando evento:', e);
        ch.nack(msg, false, false);
      }
    }
  });
}

// Inicialización
async function main() {
  startGrpcServer();
  await startRabbitConsumer();
}

main().catch(err => {
  console.error('Fallo al arrancar EmailService:', err);
  process.exit(1);
});