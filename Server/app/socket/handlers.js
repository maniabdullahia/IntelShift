function registerSocketHandlers(io, socket) {

  /*
  |--------------------------------------------------------------------------
  | WORKSPACE ROOM
  |--------------------------------------------------------------------------
  */

  socket.on("workspace:join", (workspaceId) => {
    console.log(`🔵 Socket ${socket.id} joining workspace room: workspace:${workspaceId}`);
    socket.join(`workspace:${workspaceId}`);
  });

  socket.on("workspace:leave", (workspaceId) => {
    socket.leave(`workspace:${workspaceId}`);
  });

  /*
  |--------------------------------------------------------------------------
  | ADMIN ROOM
  |--------------------------------------------------------------------------
  */

  socket.on("admin:join", () => {
    socket.join("admin");
  });

  /*
  |--------------------------------------------------------------------------
  | USER ROOM (IMPORTANT for notifications)
  |--------------------------------------------------------------------------
  */

  socket.on("user:join", (userId) => {
    socket.join(`user:${userId}`);
  });

  /*
  |--------------------------------------------------------------------------
  | DISCONNECT
  |--------------------------------------------------------------------------
  */

  socket.on("disconnect", () => {
    console.log("🔴 Disconnected:", socket.id);
  });
}

export default registerSocketHandlers;