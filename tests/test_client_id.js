const assert = require('assert');
const createClientMessageId = require('../static/js/client-id.js');

const nativeId = '123e4567-e89b-42d3-a456-426614174000';
assert.strictEqual(createClientMessageId({
  randomUUID: () => nativeId,
}), nativeId);

const fallbackId = createClientMessageId({
  getRandomValues: bytes => {
    bytes.forEach((_, index) => { bytes[index] = index; });
    return bytes;
  },
});

assert.strictEqual(fallbackId, '00010203-0405-4607-8809-0a0b0c0d0e0f');
assert.match(fallbackId, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);

console.log('client_id_ok');
