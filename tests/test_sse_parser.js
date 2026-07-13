const assert = require('assert');
const SSEFrameParser = require('../static/js/sse-parser.js');

const events = [];
const parser = new SSEFrameParser((type, data) => events.push({ type, data }));

for (const fragment of [
  'event: me',
  'ta\r',
  '\ndata: {"conversation_id":"abc"}\r',
  '\n\r',
  '\nevent: token\n',
  'data: {"content":"你',
  '好"}\n\n',
]) {
  parser.push(fragment);
}
parser.finish();

assert.deepStrictEqual(events, [
  { type: 'meta', data: '{"conversation_id":"abc"}' },
  { type: 'token', data: '{"content":"你好"}' },
]);

console.log('sse_parser_ok');
