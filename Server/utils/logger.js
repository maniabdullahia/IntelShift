import fs from 'fs';
import chalk from 'chalk';
import ora from 'ora';

class Logger {
  constructor(options = {}) {
    this.logToFile = options.logToFile || false;
    this.filePath = options.filePath || 'app.log';
  }

  getColor(level) {
    switch (level) {
      case 'info': return chalk.green;
      case 'error': return chalk.red;
      case 'warn': return chalk.yellow;
      case 'debug': return chalk.cyan;
      case 'pending': return chalk.blue;
      case 'success': return chalk.greenBright;
      case 'fail': return chalk.redBright;
      default: return chalk.white;
    }
  }

  format(level, message, meta = {}) {
    const time = new Date().toISOString();
    return { time, level, message, ...meta };
  }

  write(level, message, meta = {}) {
    const logObj = this.format(level, message, meta);
    const color = this.getColor(level);

    // Console output
    const consoleMsg = `${chalk.gray(logObj.time)} ${color(level.toUpperCase())} ${message}`;
    console.log(consoleMsg);

    // File output
    if (this.logToFile) {
      fs.appendFile(this.filePath, JSON.stringify(logObj) + '\n', () => {});
    }
  }

  info(msg, meta) { this.write('info', msg, meta); }
  warn(msg, meta) { this.write('warn', msg, meta); }
  error(msg, meta) { this.write('error', msg, meta); }
  debug(msg, meta) { this.write('debug', msg, meta); }

  // 🔹 Async helper
  async trackPromise(promise, description = 'Processing') {
    const spinner = ora({ text: `${description}...`, color: 'blue' }).start();
    this.write('pending', `${description} started`);

    try {
      const result = await promise;
      spinner.succeed(`${description} resolved`);
      this.write('success', `${description} resolved`);
      return result;
    } catch (err) {
      spinner.fail(`${description} rejected`);
      this.write('fail', `${description} rejected`, { error: err.message });
      throw err;
    }
  }
}

export default Logger;