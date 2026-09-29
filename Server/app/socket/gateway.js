import { getIO } from "./socket.js";

/*
|--------------------------------------------------------------------------
| SOCKET GATEWAY (UNIVERSAL)
|--------------------------------------------------------------------------
| This is the ONLY file allowed to emit events
|--------------------------------------------------------------------------
*/

class SocketGateway {

  /*
  |--------------------------------------------------------------------------
  | Emit to a ROOM
  |--------------------------------------------------------------------------
  | workspace:123
  | admin
  | user:456
  */

  static toRoom(room, event, payload = {}) {
    const io = getIO();
    io.to(room).emit(event, payload);
  }

  /*
  |--------------------------------------------------------------------------
  | Emit to WORKSPACE (wrapper)
  |--------------------------------------------------------------------------
  */

  static workspace(workspaceId, event, payload = {}) {
    this.toRoom(`workspace:${workspaceId}`, event, {
      workspaceId,
      ...payload,
    });
    console.log(`Emitted event '${event}' to workspace ${workspaceId} with payload:`, payload);
  }

  /*
  |--------------------------------------------------------------------------
  | Emit to USER
  |--------------------------------------------------------------------------
  */

  static user(userId, event, payload = {}) {
    const io = getIO();
    io.to(`user:${userId}`).emit(event, payload);
  }

  /*
  |--------------------------------------------------------------------------
  | ADMIN PANEL EVENTS
  |--------------------------------------------------------------------------
  */

  static admin(event, payload = {}) {
    const io = getIO();
    io.to("admin").emit(event, payload);
  }

  /*
  |--------------------------------------------------------------------------
  | GLOBAL BROADCAST
  |--------------------------------------------------------------------------
  */

  static broadcast(event, payload = {}) {
    const io = getIO();
    io.emit(event, payload);
  }
}

export default SocketGateway;