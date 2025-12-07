const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const axios = require('axios');

// Configuration
const OLLAMA_API_URL = process.env.OLLAMA_API_URL || 'http://ollama:8000';
const TTS_API_URL = process.env.TTS_API_URL || 'http://piper-tts:5000';
const PORT = process.env.PORT || 3000;

// TTS (Text-to-Speech) trigger keyword
// When message starts with "speak" (after "Prometheus" in groups), AI response is also spoken
// Examples:
//   Group: "Prometheus speak what time is it?" → AI responds via text AND speaker
//   Private: "speak hello" → AI responds via text AND speaker
const TTS_TRIGGER = 'speak';

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
const MAX_CONTEXT_MESSAGES = 25; // Store last 15 messages per group
const MAX_MESSAGE_LENGTH = 500; // Truncate individual messages (500 chars ≈ 150-200 tokens)
const MAX_CONTEXT_TO_SEND = 20; // Send only 5 messages to AI (total ~3000 tokens for context)
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
    
    // CONTEXT STORAGE: Store messages for context (both groups and private chats)
    const chatId = message.from; // Chat ID (group or private)
    
    // Get sender name (with fallback if getContact() fails due to WhatsApp Web updates)
    let senderName = senderNumber;
    try {
        const contact = await message.getContact();
        senderName = contact.pushname || contact.name || senderNumber;
    } catch (contactError) {
        // getContact() can fail when WhatsApp Web updates break whatsapp-web.js
        console.log(`⚠️ Could not get contact info: ${contactError.message}`);
        senderName = chat.name || senderNumber; // Fallback to chat name or number
    }
    
    // Determine if we should store context
    const shouldStoreContext = chat.isGroup || (!chat.isGroup && (senderNumber === AUTHORIZED_NUMBER || senderNumber === AUTHORIZED_LID));
    
    if (shouldStoreContext) {
        // PROTECTION 1: Limit number of chats tracked (memory protection)
        if (!groupContexts.has(chatId) && groupContexts.size >= MAX_GROUPS) {
            console.log(`⚠️ Max chats (${MAX_GROUPS}) reached, not tracking new chat: ${chat.name || 'Private'}`);
        } else {
            // Initialize context array for this chat if it doesn't exist
            if (!groupContexts.has(chatId)) {
                groupContexts.set(chatId, []);
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
            
            const chatContext = groupContexts.get(chatId);
            chatContext.push(contextEntry);
            
            // Keep only the last MAX_CONTEXT_MESSAGES
            if (chatContext.length > MAX_CONTEXT_MESSAGES) {
                chatContext.shift(); // Remove oldest message
            }
            
            const chatLabel = chat.isGroup ? `[${chat.name}]` : '[Private Chat]';
            console.log(`📝 Stored context: ${chatLabel} ${senderName}: ${truncatedMessage.substring(0, 50)}...`);
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
        
        // DEBUG COMMAND: Check stored context
        if (message.body.toLowerCase() === 'prometheus debug context') {
            const groupId = message.from;
            const groupContext = groupContexts.get(groupId);
            
            if (groupContext && groupContext.length > 0) {
                let debugMsg = `🔍 *Context Debug*\n\nStored ${groupContext.length} messages:\n\n`;
                groupContext.forEach((ctx, idx) => {
                    debugMsg += `${idx + 1}. [${ctx.sender}]: ${ctx.message.substring(0, 100)}${ctx.message.length > 100 ? '...' : ''}\n\n`;
                });
                await message.reply(debugMsg);
            } else {
                await message.reply('⚠️ No context stored for this group yet.');
            }
            return;
        }
        
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
    
    // Check for TTS trigger ("speak" keyword)
    // If message starts with "speak", we'll also send the AI response to the speaker
    let shouldSpeak = false;
    if (userQuestion.toLowerCase().startsWith(TTS_TRIGGER)) {
        shouldSpeak = true;
        // Remove "speak" from the message
        userQuestion = userQuestion.substring(TTS_TRIGGER.length).trim();
        console.log(`🔊 TTS trigger detected - AI response will be spoken`);
        
        // If nothing left after removing "speak", use a default greeting
        if (!userQuestion) {
            userQuestion = 'say hello';
        }
    }
    
    // Log the message
    console.log(`\n📨 Authorized User: ${userQuestion.substring(0, 100)}...`);
    console.log(`   🔊 Speak mode: ${shouldSpeak ? 'ON' : 'OFF'}`);
    
    try {
        // Show typing indicator
        chat.sendStateTyping();
        
        // Get chat ID and context (will be reused throughout)
        const chatId = message.from;
        let chatContext = groupContexts.get(chatId);
        
        // Prepare the message with context (for both groups and private chats)
        let finalMessage = userQuestion;
        
        if (chatContext && chatContext.length > 0) {
            const chatLabel = chat.isGroup ? 'Group' : 'Private Chat';
            
            console.log(`\n🔍 Context Debug:`);
            console.log(`   Chat Type: ${chatLabel}`);
            console.log(`   Chat ID: ${chatId}`);
            console.log(`   Total messages in context: ${chatContext.length}`);
            
            // Log all stored messages for debugging
            console.log(`   📝 All stored messages:`);
            chatContext.forEach((ctx, idx) => {
                console.log(`      ${idx}: [${ctx.sender}] ${ctx.message.substring(0, 60)}...`);
            });
            
            // Build context string from recent messages
            // For groups: Filter out YOUR trigger messages but KEEP AI responses
            // For private chats: Keep everything (no "Prometheus" triggers to filter)
            const relevantMessages = chatContext.filter(ctx => {
                // Keep AI responses
                if (ctx.isAI) return true;
                // For groups: filter out only YOUR "Prometheus" triggers (not other people's)
                if (chat.isGroup && ctx.message.startsWith('Prometheus') && ctx.isAuthorizedUser) {
                    console.log(`      ❌ Filtered out your trigger: "${ctx.message.substring(0, 40)}..."`);
                    return false; // Filter out your own triggers only
                }
                // Keep everything else (including other people's messages about Prometheus)
                return true;
            });
            
            console.log(`   📊 After filtering: ${relevantMessages.length} messages (from ${chatContext.length} total)`);
            
            // Take last N messages
            const recentMessages = relevantMessages.slice(-MAX_CONTEXT_TO_SEND);
            
            console.log(`   📤 Sending to AI: ${recentMessages.length} messages`);
            recentMessages.forEach((ctx, idx) => {
                const label = ctx.isAI ? '🤖' : '👤';
                console.log(`      ${label} [${ctx.sender}]: ${ctx.message.substring(0, 50)}...`);
            });
            
            const contextMessages = recentMessages
                .map(ctx => `${ctx.sender}: ${ctx.message}`)
                .join('\n');
            
            if (contextMessages) {
                const contextType = chat.isGroup ? 'group chat' : 'conversation';
                finalMessage = `CONTEXT: The following are recent messages from our ${contextType}. Use them ONLY if relevant to answer my question below. If my question is unrelated to this context, ignore the context completely and answer my question directly.

--- Recent Messages ---
${contextMessages}
--- End of Context ---

MY QUESTION (this is what you should answer): ${userQuestion}`;
                console.log(`   ✅ Context prepared successfully\n`);
                console.log(`📤 Full message being sent to AI:\n${finalMessage}\n`);
            } else {
                console.log(`   ⚠️ No context available after filtering\n`);
            }
        } else {
            console.log(`   ⚠️ No context stored for this chat yet\n`);
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
        
        // If TTS was triggered, speak the response through the speaker
        if (shouldSpeak) {
            try {
                // Remove emojis from text before sending to TTS
                // Emojis don't sound good when read aloud
                const textForSpeech = aiResponse
                    .replace(/[\u{1F600}-\u{1F64F}]/gu, '')  // Emoticons
                    .replace(/[\u{1F300}-\u{1F5FF}]/gu, '')  // Misc symbols & pictographs
                    .replace(/[\u{1F680}-\u{1F6FF}]/gu, '')  // Transport & map symbols
                    .replace(/[\u{1F700}-\u{1F77F}]/gu, '')  // Alchemical symbols
                    .replace(/[\u{1F780}-\u{1F7FF}]/gu, '')  // Geometric shapes extended
                    .replace(/[\u{1F800}-\u{1F8FF}]/gu, '')  // Supplemental arrows-C
                    .replace(/[\u{1F900}-\u{1F9FF}]/gu, '')  // Supplemental symbols & pictographs
                    .replace(/[\u{1FA00}-\u{1FA6F}]/gu, '')  // Chess symbols
                    .replace(/[\u{1FA70}-\u{1FAFF}]/gu, '')  // Symbols & pictographs extended-A
                    .replace(/[\u{2600}-\u{26FF}]/gu, '')    // Misc symbols
                    .replace(/[\u{2700}-\u{27BF}]/gu, '')    // Dingbats
                    .replace(/\s+/g, ' ')                     // Collapse multiple spaces
                    .trim();
                
                console.log(`🔊 Sending to TTS service: ${TTS_API_URL}/speak`);
                console.log(`🔊 Text (emojis removed): ${textForSpeech.substring(0, 100)}...`);
                
                const ttsResponse = await axios.post(`${TTS_API_URL}/speak`, {
                    text: textForSpeech,
                    play_audio: true
                }, {
                    timeout: 60000 // 1 minute timeout for TTS
                });
                
                if (ttsResponse.data.success) {
                    console.log(`🔊 TTS completed in ${ttsResponse.data.duration_ms?.toFixed(0)}ms`);
                } else {
                    console.log(`⚠️ TTS service returned failure`);
                }
            } catch (ttsError) {
                console.error(`❌ TTS Error: ${ttsError.message}`);
                // Don't fail the whole message, just log the TTS error
                // The text response was already sent successfully
            }
        }
        
        // STORE AI RESPONSE IN CONTEXT (for both groups and private chats)
        // Re-fetch context in case it was created during processing
        chatContext = groupContexts.get(chatId);
        
        if (chatContext) {
            // Truncate AI response if too long
            let truncatedResponse = aiResponse;
            if (aiResponse.length > MAX_MESSAGE_LENGTH) {
                truncatedResponse = aiResponse.substring(0, MAX_MESSAGE_LENGTH) + '... [truncated]';
            }
            
            // Add AI response to context
            const aiContextEntry = {
                sender: 'Prometheus',
                message: truncatedResponse,
                timestamp: new Date(),
                isAuthorizedUser: false,
                isAI: true // Mark as AI response
            };
            
            chatContext.push(aiContextEntry);
            
            // Keep only the last MAX_CONTEXT_MESSAGES
            if (chatContext.length > MAX_CONTEXT_MESSAGES) {
                chatContext.shift();
            }
            
            const chatLabel = chat.isGroup ? `[${chat.name}]` : '[Private Chat]';
            console.log(`💾 Stored AI response in context ${chatLabel}: ${truncatedResponse.substring(0, 50)}...`);
        }
        
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

