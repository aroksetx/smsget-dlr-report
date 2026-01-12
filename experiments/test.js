const smpp = require('smpp');

const session = new smpp.Session({ host: '52.57.134.177', port: 2775 });

session.bind_transceiver({
  system_id: 'teamclussender',
  password: 'xrQrb9iP'
}, () => {
  console.log('BOUND');

  session.deliver_sm({
    source_addr: '447700900123',
    destination_addr: '447700900999',
    esm_class: 0x00,
    data_coding: 0,
    short_message: 'Test OTP 1234'
  }, () => {
    console.log('deliver_sm sent');
    session.unbind();
  });
});