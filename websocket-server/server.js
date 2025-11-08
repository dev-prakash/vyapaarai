const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const jwt = require('jsonwebtoken');
const redis = require('redis');
const cors = require('cors');
const helmet = require('helmet');
const { v4: uuidv4 } = require('uuid');
require('dotenv').config();

const app = express();
const server = http.createServer(app);

// Security middleware
app.use(helmet());
app.use(cors({
  origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000', 'https://www.vyapaarai.com'],
  credentials: true
}));
app.use(express.json());

// Redis client for session storage
const redisClient = redis.createClient({
  url: process.env.REDIS_URL || 'redis://localhost:6379'
});

redisClient.on('error', (err) => {
  console.error('Redis Client Error:', err);
});

redisClient.connect().then(() => {
  console.log('Connected to Redis');
}).catch(err => {
  console.error('Redis connection failed:', err);
});

// Socket.IO setup
const io = socketIo(server, {
  cors: {
    origin: process.env.ALLOWED_ORIGINS?.split(',') || ['http://localhost:3000', 'https://www.vyapaarai.com'],
    methods: ['GET', 'POST'],
    credentials: true
  }
});

// JWT verification middleware
const verifyToken = (socket, next) => {
  const token = socket.handshake.auth.token;
  
  if (!token) {
    return next(new Error('Authentication error: No token provided'));
  }

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET || 'your-secret-key');
    socket.userId = decoded.user_id;
    socket.storeId = decoded.store_id;
    next();
  } catch (err) {
    next(new Error('Authentication error: Invalid token'));
  }
};

// Apply authentication middleware
io.use(verifyToken);

// Store active sessions
const activeSessions = new Map();

// Socket connection handling
io.on('connection', (socket) => {
  console.log(`User connected: ${socket.userId} from store: ${socket.storeId}`);
  
  // Create scan session
  socket.on('create_scan_session', async (sessionData, callback) => {
    try {
      const sessionId = `scan_${Date.now()}_${uuidv4().substr(0, 8)}`;
      const session = {
        sessionId,
        storeId: socket.storeId,
        userId: socket.userId,
        expiresAt: new Date(Date.now() + 10 * 60 * 1000).toISOString(), // 10 minutes
        status: 'waiting',
        createdAt: new Date().toISOString()
      };

      // Store in Redis
      await redisClient.setEx(
        `scan_session:${sessionId}`, 
        600, // 10 minutes TTL
        JSON.stringify(session)
      );

      // Store in memory for quick access
      activeSessions.set(sessionId, session);

      // Join session room
      socket.join(`session:${sessionId}`);

      callback({ success: true, session });
      console.log(`Scan session created: ${sessionId}`);
    } catch (error) {
      console.error('Error creating scan session:', error);
      callback({ success: false, error: 'Failed to create scan session' });
    }
  });

  // Send barcode from mobile
  socket.on('scan_barcode', async (data, callback) => {
    try {
      const { sessionId, barcode, timestamp } = data;
      
      // Get session from Redis
      const sessionData = await redisClient.get(`scan_session:${sessionId}`);
      if (!sessionData) {
        callback({ success: false, error: 'Session not found or expired' });
        return;
      }

      const session = JSON.parse(sessionData);
      
      // Update session with barcode
      session.barcode = barcode;
      session.timestamp = timestamp;
      session.status = 'completed';

      // Update in Redis
      await redisClient.setEx(
        `scan_session:${sessionId}`,
        60, // 1 minute TTL after completion
        JSON.stringify(session)
      );

      // Update in memory
      activeSessions.set(sessionId, session);

      // Emit to all clients in the session room
      io.to(`session:${sessionId}`).emit('barcode_scanned', {
        sessionId,
        barcode,
        timestamp
      });

      callback({ success: true });
      console.log(`Barcode scanned: ${barcode} for session: ${sessionId}`);
    } catch (error) {
      console.error('Error processing barcode scan:', error);
      callback({ success: false, error: 'Failed to process barcode scan' });
    }
  });

  // Get session status
  socket.on('get_session_status', async (sessionId, callback) => {
    try {
      const sessionData = await redisClient.get(`scan_session:${sessionId}`);
      if (!sessionData) {
        callback({ success: false, error: 'Session not found' });
        return;
      }

      const session = JSON.parse(sessionData);
      callback({ success: true, session });
    } catch (error) {
      console.error('Error getting session status:', error);
      callback({ success: false, error: 'Failed to get session status' });
    }
  });

  // Cleanup expired sessions
  socket.on('cleanup_expired_sessions', async () => {
    try {
      const now = new Date();
      const expiredSessions = [];

      for (const [sessionId, session] of activeSessions.entries()) {
        if (new Date(session.expiresAt) < now) {
          expiredSessions.push(sessionId);
        }
      }

      for (const sessionId of expiredSessions) {
        await redisClient.del(`scan_session:${sessionId}`);
        activeSessions.delete(sessionId);
        io.to(`session:${sessionId}`).emit('session_expired', { sessionId });
      }

      console.log(`Cleaned up ${expiredSessions.length} expired sessions`);
    } catch (error) {
      console.error('Error cleaning up sessions:', error);
    }
  });

  // Handle disconnection
  socket.on('disconnect', () => {
    console.log(`User disconnected: ${socket.userId}`);
  });
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    timestamp: new Date().toISOString(),
    activeSessions: activeSessions.size,
    redisConnected: redisClient.isReady
  });
});

// API endpoint for session creation (for non-WebSocket clients)
app.post('/api/scan-session', async (req, res) => {
  try {
    const { storeId, userId } = req.body;
    const sessionId = `scan_${Date.now()}_${uuidv4().substr(0, 8)}`;
    
    const session = {
      sessionId,
      storeId,
      userId,
      expiresAt: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
      status: 'waiting',
      createdAt: new Date().toISOString()
    };

    await redisClient.setEx(`scan_session:${sessionId}`, 600, JSON.stringify(session));
    activeSessions.set(sessionId, session);

    res.json({ success: true, session });
  } catch (error) {
    console.error('Error creating scan session via API:', error);
    res.status(500).json({ success: false, error: 'Failed to create scan session' });
  }
});

// API endpoint for barcode submission (for non-WebSocket clients)
app.post('/api/scan-barcode', async (req, res) => {
  try {
    const { sessionId, barcode } = req.body;
    
    const sessionData = await redisClient.get(`scan_session:${sessionId}`);
    if (!sessionData) {
      return res.status(404).json({ success: false, error: 'Session not found' });
    }

    const session = JSON.parse(sessionData);
    session.barcode = barcode;
    session.timestamp = new Date().toISOString();
    session.status = 'completed';

    await redisClient.setEx(`scan_session:${sessionId}`, 60, JSON.stringify(session));
    activeSessions.set(sessionId, session);

    // Emit to WebSocket clients
    io.to(`session:${sessionId}`).emit('barcode_scanned', {
      sessionId,
      barcode,
      timestamp: session.timestamp
    });

    res.json({ success: true });
  } catch (error) {
    console.error('Error processing barcode via API:', error);
    res.status(500).json({ success: false, error: 'Failed to process barcode' });
  }
});

// Periodic cleanup of expired sessions
setInterval(async () => {
  try {
    const now = new Date();
    const expiredSessions = [];

    for (const [sessionId, session] of activeSessions.entries()) {
      if (new Date(session.expiresAt) < now) {
        expiredSessions.push(sessionId);
      }
    }

    for (const sessionId of expiredSessions) {
      await redisClient.del(`scan_session:${sessionId}`);
      activeSessions.delete(sessionId);
      io.to(`session:${sessionId}`).emit('session_expired', { sessionId });
    }

    if (expiredSessions.length > 0) {
      console.log(`Auto-cleaned up ${expiredSessions.length} expired sessions`);
    }
  } catch (error) {
    console.error('Error in periodic cleanup:', error);
  }
}, 60000); // Run every minute

const PORT = process.env.PORT || 3001;
server.listen(PORT, () => {
  console.log(`WebSocket server running on port ${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
});

