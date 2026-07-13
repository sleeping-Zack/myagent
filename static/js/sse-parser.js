(function (root, factory) {
  const Parser = factory();
  if (typeof module === 'object' && module.exports) module.exports = Parser;
  root.SSEFrameParser = Parser;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  class SSEFrameParser {
    constructor(onEvent) {
      this.buffer = '';
      this.onEvent = onEvent;
    }

    push(chunk) {
      this.buffer += chunk;
      let boundary = this.buffer.match(/\r?\n\r?\n/);
      while (boundary && boundary.index !== undefined) {
        const frame = this.buffer.slice(0, boundary.index);
        this.buffer = this.buffer.slice(boundary.index + boundary[0].length);
        this.parseFrame(frame);
        boundary = this.buffer.match(/\r?\n\r?\n/);
      }
    }

    finish() {
      if (this.buffer.trim()) this.parseFrame(this.buffer);
      this.buffer = '';
    }

    parseFrame(frame) {
      let eventType = 'message';
      const dataLines = [];
      for (const line of frame.replace(/\r\n/g, '\n').split('\n')) {
        if (!line || line.startsWith(':')) continue;
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trimStart());
        }
      }
      if (dataLines.length) this.onEvent(eventType, dataLines.join('\n'));
    }
  }

  return SSEFrameParser;
});
