import { Server } from "socket.io";
import registerSocketHandlers from "./handlers.js";

let io;

function initializeSocket(httpServer) {
    io = new Server(httpServer, {
        cors: {
            origin: ["https://intelshift.ai", "https://admin.intelshift.ai", "https://app.intelshift.ai", "http://localhost:5173", "http://localhost:5174"],
            methods: ["GET", "POST"],
            credentials: true,
        },
    });

    io.on("connection", (socket) => {
        console.log("🟢 New client connected:", socket.id);

        registerSocketHandlers(io, socket);
    });

    return io;
}

export default initializeSocket;

// 👇 optional but VERY useful
export const getIO = () => {
    if (!io) throw new Error("Socket not initialized");
    return io;
};