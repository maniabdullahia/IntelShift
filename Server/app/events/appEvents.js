import EventEmitter from "events";

class AppEvents extends EventEmitter {}

const appEvents = new AppEvents();

export default appEvents;