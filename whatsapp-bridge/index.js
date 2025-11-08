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

// CONFIGURATION: Authorized WhatsApp identifiers from environment variables
// AUTHORIZED_NUMBER: Your phone number for direct chats (format: 32489965845@c.us)
// AUTHORIZED_LID: Your internal WhatsApp ID for groups (format: 98765432109@lid)
// Set in docker-compose.yml as environment variables
const AUTHORIZED_NUMBER = process.env.AUTHORIZED_NUMBER || 'YOUR_NUMBER_HERE@c.us';
const AUTHORIZED_LID = process.env.AUTHORIZED_LID || 'YOUR_LID_HERE@lid';

// Conversation context storage: stores recent messages per group
// Format: { 'groupId': [{ sender: 'name', message: 'text', timestamp: Date }] }
const groupContexts = new Map();
const MAX_CONTEXT_MESSAGES = 15; // Store last 15 messages per group
const MAX_MESSAGE_LENGTH = 500; // Truncate individual messages (500 chars ≈ 150-200 tokens)
const MAX_CONTEXT_TO_SEND = 5; // Send only 5 messages to AI (total ~750-1000 tokens for context)
const MAX_GROUPS = 50; // Limit number of groups to track (memory protection)

// Rate limiting per user
const userLastRequest = new Map(); // { userId: timestamp }
const RATE_LIMIT_SECONDS = 2; // Min seconds between requests from same user

// Message handler
client.on('message', async (message) => {
    // Get chat info
    const chat = await message.getChat();
    
    // Ignore system/notification messages
    if (message.type !== 'chat') {
        return;
    }
    
    // Get sender's phone number (unique identifier)
    const senderNumber = message.from.includes('@g.us') 
        ? message.author  // In groups, use message.author
        : message.from;   // In direct chats, use message.from
    
    // CONTEXT STORAGE: Store all group messages for context (before authorization check)
    if (chat.isGroup) {
        const groupId = message.from; // Group chat ID
        const contact = await message.getContact();
        const senderName = contact.pushname || contact.name || senderNumber;
        
        // PROTECTION 1: Limit number of groups tracked (memory protection)
        if (!groupContexts.has(groupId) && groupContexts.size >= MAX_GROUPS) {
            console.log(`⚠️ Max groups (${MAX_GROUPS}) reached, not tracking new group: ${chat.name}`);
            // Don't track new groups if we've hit the limit
            // Existing groups continue to work
        } else {
            // Initialize context array for this group if it doesn't exist
            if (!groupContexts.has(groupId)) {
                groupContexts.set(groupId, []);
            }
            
            // PROTECTION 2: Truncate long messages
            let truncatedMessage = message.body;
            if (message.body.length > MAX_MESSAGE_LENGTH) {
                truncatedMessage = message.body.substring(0, MAX_MESSAGE_LENGTH) + '... [truncated]';
                console.log(`✂️ Truncated long message (${message.body.length} chars -> ${MAX_MESSAGE_LENGTH})`);
            }
            
            // Add message to context
            const contextEntry = {
                sender: senderName,
                message: truncatedMessage,
                timestamp: new Date(),
                isAuthorizedUser: (senderNumber === AUTHORIZED_NUMBER) || (senderNumber === AUTHORIZED_LID)
            };
            
            const groupContext = groupContexts.get(groupId);
            groupContext.push(contextEntry);
            
            // Keep only the last MAX_CONTEXT_MESSAGES
            if (groupContext.length > MAX_CONTEXT_MESSAGES) {
                groupContext.shift(); // Remove oldest message
            }
            
            console.log(`📝 Stored context: [${chat.name}] ${senderName}: ${truncatedMessage.substring(0, 50)}...`);
        }
    }
    
    // Check if sender is authorized (either phone number OR internal LID)
    const isAuthorized = (senderNumber === AUTHORIZED_NUMBER) || (senderNumber === AUTHORIZED_LID);
    
    // Debug logging for groups (only for authorized user)
    if (chat.isGroup && isAuthorized) {
        console.log(`\n🔍 Authorized message in group:`);
        console.log(`   Group: ${chat.name || 'UNNAMED'}`);
        console.log(`   Sender: ${senderNumber}`);
        console.log(`   Message: "${message.body}"`);
    }
    
    if (!isAuthorized) {
        // Message stored in context but won't trigger AI response
        return;
    }
    
    if (chat.isGroup) {
        console.log(`   ✅ Authorized user confirmed`);
    }
    
    // If it's a group chat, only respond if message starts with "Prometheus"
    if (chat.isGroup) {
        if (!message.body.startsWith('Prometheus')) {
            console.log(`   ❌ Missing "Prometheus" trigger - ignoring`);
            return;
        }
        console.log(`   ✅ "Prometheus" trigger found - processing`);
        // Remove "Prometheus" from the message before processing
        message.body = message.body.substring('Prometheus'.length).trim();
    }
    
    // Ignore messages from self
    if (message.fromMe) {
        return;
    }
    
    // PROTECTION 3: Rate limiting (prevent spam)
    const now = Date.now();
    const lastRequestTime = userLastRequest.get(senderNumber);
    
    if (lastRequestTime) {
        const secondsSinceLastRequest = (now - lastRequestTime) / 1000;
        
        if (secondsSinceLastRequest < RATE_LIMIT_SECONDS) {
            const waitTime = Math.ceil(RATE_LIMIT_SECONDS - secondsSinceLastRequest);
            console.log(`⏱️ Rate limit: User must wait ${waitTime} seconds`);
            await message.reply(`⏱️ Please wait ${waitTime} seconds before sending another request.`);
            return;
        }
    }
    
    // Update last request time
    userLastRequest.set(senderNumber, now);
    
    // PROTECTION 4: Truncate user's question if too long
    let userQuestion = message.body;
    if (userQuestion.length > MAX_MESSAGE_LENGTH) {
        userQuestion = userQuestion.substring(0, MAX_MESSAGE_LENGTH) + '... [truncated]';
        console.log(`✂️ Truncated user question (${message.body.length} chars -> ${MAX_MESSAGE_LENGTH})`);
    }
    
    // Log the message
    console.log(`\n📨 Authorized User: ${userQuestion.substring(0, 100)}...`);
    
    try {
        // Show typing indicator
        chat.sendStateTyping();
        
        // Prepare the message with context if in a group
        let finalMessage = userQuestion;
        
        if (chat.isGroup) {
            const groupId = message.from;
            const groupContext = groupContexts.get(groupId);
            
            if (groupContext && groupContext.length > 0) {
                // Build context string from recent messages (excluding the current one)
                const contextMessages = groupContext
                    .slice(0, -1) // Exclude the current "Prometheus" message
                    .filter(ctx => !ctx.message.startsWith('Prometheus')) // Exclude other Prometheus triggers
                    .slice(-MAX_CONTEXT_TO_SEND) // Last N messages (configurable)
                    .map(ctx => `${ctx.sender}: ${ctx.message}`)
                    .join('\n');
                
                if (contextMessages) {
                    finalMessage = `CONTEXT: The following are recent messages from a group chat. Use them ONLY if relevant to answer my question below. If my question is unrelated to this context, ignore the context completely and answer my question directly.

--- Recent Group Messages ---
${contextMessages}
--- End of Context ---

MY QUESTION (this is what you should answer): ${userQuestion}`;
                    console.log(`📚 Including ${groupContext.length} messages as context`);
                }
            }
        }
        
        // Call Ollama API
        const response = await axios.post(`${OLLAMA_API_URL}/chat`, {
            message: finalMessage,
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

