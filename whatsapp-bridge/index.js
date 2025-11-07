const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const axios = require('axios');

// Configuration
const OLLAMA_API_URL = process.env.OLLAMA_API_URL || 'http://ollama:8000';
const PORT = process.env.PORT || 3000;

// Initialize Express for health check and QR display
const app = express();

let qrCodeData = null;
let isReady = false;
let clientStatus = 'initializing';

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({
        status: clientStatus,
        ready: isReady,
        timestamp: new Date().toISOString()
    });
});


// QR code endpoint (for web viewing)
app.get('/qr', (req, res) => {
    if (qrCodeData) {
        res.send(`
            <html>
            <head><title>WhatsApp QR Code</title></head>
            <body style="display: flex; justify-content: center; align-items: center; height: 100vh; flex-direction: column; font-family: Arial;">
                <h1>Scan this QR code with WhatsApp</h1>
                <img src="${qrCodeData}" alt="QR Code" style="width: 400px; height: 400px;"/>
                <p>Open WhatsApp on your phone → Settings → Linked Devices → Link a Device</p>
                <p style="color: #666;">Status: ${clientStatus}</p>
            </body>
            </html>
        `);
    } else if (isReady) {
        res.send(`
            <html>
            <body style="display: flex; justify-content: center; align-items: center; height: 100vh; flex-direction: column; font-family: Arial;">
                <h1>✅ WhatsApp Connected!</h1>
                <p>Your bot is ready to receive messages.</p>
            </body>
            </html>
        `);
    } else {
        res.send(`
            <html>
            <body style="display: flex; justify-content: center; align-items: center; height: 100vh; flex-direction: column; font-family: Arial;">
                <h1>⏳ Initializing WhatsApp...</h1>
                <p>Please wait, QR code will appear soon.</p>
                <p style="color: #666;">Status: ${clientStatus}</p>
            </body>
            </html>
        `);
    }
});

// Start Express server
app.listen(PORT, () => {
    console.log(`WhatsApp Bridge running on port ${PORT}`);
    console.log(`View QR code at: http://localhost:${PORT}/qr`);
});

// Initialize WhatsApp client
console.log('Initializing WhatsApp client...');

// Use system Chromium (installed via apt)
// Path is set in Dockerfile via PUPPETEER_EXECUTABLE_PATH
const executablePath = process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium';

console.log('Using Chromium from:', executablePath);

const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: '/data'
    }),
    puppeteer: {
        headless: true,
        executablePath: executablePath,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu'
        ]
    }
});

// QR code generation
client.on('qr', (qr) => {
    console.log('QR code received! Scan with WhatsApp:');
    qrcode.generate(qr, { small: true });
    
    // Generate data URL for web display
    const QRCode = require('qrcode');
    QRCode.toDataURL(qr, (err, url) => {
        if (!err) {
            qrCodeData = url;
            clientStatus = 'waiting_for_scan';
        }
    });
    
    console.log(`\nOr visit: http://localhost:${PORT}/qr`);
});

// Client ready
client.on('ready', () => {
    console.log('✅ WhatsApp client is ready!');
    isReady = true;
    clientStatus = 'connected';
    qrCodeData = null;
});

// Authentication
client.on('authenticated', () => {
    console.log('✅ Authenticated with WhatsApp');
    clientStatus = 'authenticated';
});

// Disconnection
client.on('disconnected', (reason) => {
    console.log('❌ WhatsApp disconnected:', reason);
    isReady = false;
    clientStatus = 'disconnected';
});

// Message handler
client.on('message', async (message) => {
    // Get chat info
    const chat = await message.getChat();
    
    // Ignore system/notification messages
    if (message.type !== 'chat') {
        return;
    }
    
    // ONLY respond to messages from "Alan Kurt"
    if (chat.name !== 'Alan Kurt') {
        return;
    }
    
    // Ignore messages from self
    if (message.fromMe) {
        return;
    }
    
    // Log the message
    console.log(`\n📨 Alan Kurt: ${message.body}`);
    
    try {
        // Show typing indicator
        chat.sendStateTyping();
        
        // Call Ollama API
        const response = await axios.post(`${OLLAMA_API_URL}/chat`, {
            message: message.body,
            temperature: 0.7,
            max_tokens: 500
        }, {
            timeout: 120000 // 2 minutes timeout
        });
        
        const aiResponse = response.data.response;
        console.log(`🤖 AI Response: ${aiResponse}`);
        
        // Send reply
        await message.reply(aiResponse);
        
    } catch (error) {
        console.error('❌ Error processing message:', error.message);
        
        let errorMessage = '❌ Sorry, I encountered an error. Please try again.';
        
        if (error.code === 'ETIMEDOUT' || error.code === 'ECONNABORTED') {
            errorMessage = '⏱️ Sorry, the response took too long. Please try a simpler question.';
        } else if (error.response) {
            errorMessage = `❌ Error: ${error.response.status} - ${error.response.statusText}`;
        }
        
        await message.reply(errorMessage);
    }
});

// Add after the Express health endpoint (around line 60)
app.post('/send-message', async (req, res) => {
    try {
        const { message } = req.body;
        
        // Find Alan Kurt's chat
        const chats = await client.getChats();
        const alanChat = chats.find(chat => chat.name === 'Alan Kurt');
        
        if (!alanChat) {
            return res.status(404).json({ error: 'Alan Kurt chat not found' });
        }
        
        // Send message
        await alanChat.sendMessage(message);
        console.log(`📤 Sent proactive message to Alan Kurt: ${message}`);
        
        res.json({ success: true, message: 'Message sent' });
    } catch (error) {
        console.error('Error sending message:', error);
        res.status(500).json({ error: error.message });
    }
});

// Initialize client
console.log('Starting WhatsApp client...');
client.initialize();

// Graceful shutdown
process.on('SIGINT', async () => {
    console.log('\n🛑 Shutting down gracefully...');
    await client.destroy();
    process.exit(0);
});

